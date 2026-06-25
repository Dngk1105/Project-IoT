import uuid
import json
from datetime import datetime, timedelta
from core.logger import get_logger
from core.database import AsyncSessionLocal
from integrations.llm_client import llm_api
from core.prompts.system_prompts import get_assistant_prompt
from core.scheduler import push_sync_to_device
from schemas.calendar import CalendarEventCreate, CalendarEventUpdate
import crud.calendar as crud_calendar
from models.shadow import EndpointStateShadow
from sqlalchemy import select
from core.mqtt_client import publish_message
from core.mqtt_protocol import MqttTopics, PayloadBuilder
from models.calendar import EventSource


logger = get_logger(__name__, "voice_agent")

async def find_match_by_llm(user_intent: str, events: list) -> str:
    # neu khong co su kien nao thi bo qua
    if not events:
        return None
        
    # rut gon du lieu de tiet kiem token
    event_list = [{"id": str(e.id), "summary": e.summary, "time": e.start_time.strftime('%H:%M %d/%m')} for e in events]
    
    sys_prompt = f"""
    Bạn là công cụ đối chiếu dữ liệu. Người dùng muốn thao tác với sự kiện có ý nghĩa là: '{user_intent}'.
    Dưới đây là danh sách sự kiện đang có:
    {json.dumps(event_list, ensure_ascii=False)}
    
    Nhiệm vụ: Tìm sự kiện KHỚP NHẤT với ý định của người dùng dựa trên ngữ nghĩa (Sematic matching). "đá bóng" có thể khớp với "thi đấu bóng đá".
    Trả về DUY NHẤT một chuỗi JSON có định dạng sau:
    {{
        "matched_id": "ID của sự kiện khớp nhất, hoặc null nếu không có sự kiện liên quan"
    }}
    """
    
    try:
        match_data = await llm_api.chat(sys_prompt, "Hãy tìm ID khớp nhất")
        return match_data.get("matched_id")
    except Exception as e:
        logger.error(f"Loi LLM khi tim id: {e}")
        return None

class VoiceAgentService: 
    def __init__(self):
        self._session_context = {}

    async def process_user_intent(self, device_id: str, user_text: str) -> tuple[str, bool]:
        #Them context trang thai va lenh dieu khien cho AI
        device_context = ""
        async with AsyncSessionLocal() as db:
            stmt = select(EndpointStateShadow).where(EndpointStateShadow.device_id == device_id)
            result = await db.execute(stmt)
            endpoints = result.scalars().all()
            
            if endpoints:
                ep_list = [f"- {ep.name} (ep_id: '{ep.ep_id}', trạng thái: {ep.reported_state}, lệnh hỗ trợ: {ep.supported_cmds})" for ep in endpoints]
                device_context = "THIẾT BỊ NGOẠI VI ĐANG CÓ:\n" + "\n".join(ep_list)

        pending_state = self._session_context.get(device_id)
        context_str = f"LƯU ý: hệ thống đang chờ xác nhận hành động: {pending_state['action']} với dữ liệu: {pending_state['params']}." if pending_state else ""
        
        full_context = f"{context_str}\n\n{device_context}"
        
        sys_prompt = get_assistant_prompt(
            current_time=datetime.now().astimezone().isoformat(),
            context=full_context
        )
        
        ai_data = await llm_api.chat(sys_prompt, user_text)
        
        intent = ai_data.get("intent", "CHAT")
        action = ai_data.get("action", "NONE")
        params = ai_data.get("parameters", {})
        spoken_text = ai_data.get("spoken_response", "Đệ không hiểu câu hỏi của huynh")
        
        logger.info(f"[{device_id}] Intent: {intent} | Action: {action} | Params: {params}")
        
        keep_mic_open = False

        try:
            if intent == "CALENDAR" and action == "CREATE":
                if not params.get("start_time"):
                    keep_mic_open = True
                else:
                    st = params["start_time"]
                    et = params.get("end_time")
                    #Neu khong co end time thi tu dong suy ra
                    if not et:
                        from datetime import timedelta
                        st_dt = datetime.fromisoformat(st)
                        et = (st_dt + timedelta(minutes=15)).isoformat()
                        
                    async with AsyncSessionLocal() as db:
                        collisions = await crud_calendar.check_collision(db, st, et)
                        if collisions:
                            conflict_titles = ", ".join([c.summary for c in collisions])
                            spoken_text = f"Khung giờ này trùng với {conflict_titles}. Huynh có muốn ghi đè không"
            
                    self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                    keep_mic_open = True
                
            elif intent == "CALENDAR" and action in ["UPDATE", "DELETE"]:
                summary_kw = params.get("summary", "").lower()
                #Khong co summary thi can hoi lai
                if not summary_kw:
                    keep_mic_open = True
                else:
                    st_str = params.get("start_time")
                    et_str = params.get("end_time")

                    if st_str: 
                        st = datetime.fromisoformat(st_str)
                        if et_str:
                            et = datetime.fromisoformat(et_str)
                        else:
                            from datetime import timedelta
                            et = st + timedelta(days=1)
                    else:
                        st = datetime.now().astimezone()
                        from datetime import timedelta
                        et = st + timedelta(days=30)
                        
                    async with AsyncSessionLocal() as db:
                        events = await crud_calendar.get_events_in_range(db, st, et)
                        
                    matched_id = await find_match_by_llm(summary_kw, events)
                    
                    if matched_id:
                        params["id"] = matched_id
                        matched_event = next((e for e in events if str(e.id) == matched_id), None)
                        spoken_text = f"Đệ đã tìm thấy sự kiện {matched_event.summary}. Huynh xác nhận {action.lower()} chứ?"
                        self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                        keep_mic_open = True
                    else:
                        spoken_text = f"Đệ đã rà soát nhưng không tìm thấy lịch nào liên quan đến '{summary_kw}' trong khung giờ này cả."
                        keep_mic_open = False

            elif intent == "CALENDAR" and action == "FIND_SLOT":
                duration = int(params.get("duration_minutes", 60))
                st_str = params.get("start_time")
                et_str = params.get("end_time")
                
                if st_str and et_str:
                    try:
                        st = datetime.fromisoformat(st_str)
                        et = datetime.fromisoformat(et_str)
                        
                        # làm tròn thời gian bắt đầu lên 5p 
                        from datetime import timedelta
                        discard = timedelta(minutes=st.minute % 5, seconds=st.second, microseconds=st.microsecond)
                        st -= discard
                        if discard >= timedelta(seconds=1):
                            st += timedelta(minutes=5)
                        
                        async with AsyncSessionLocal() as db:
                            slots = await crud_calendar.find_free_slots(db, st, et, duration)
                        
                        if slots:
                            top_slots = slots[:3]
                            slots_str = ", ".join([f"Từ {s['start'].strftime('%H:%M %d/%m')} đến {s['end'].strftime('%H:%M %d/%m')}" for s in top_slots])
                                                        
                            spoken_text = f"Đệ thấy có các giờ trống bắt đầu từ: {slots_str}. Huynh muốn chốt giờ nào?"
                            
                            # Chuyển intent sang CREATE để đưa vào luồng xác nhận chuẩn
                            # bo trong phan start time
                            self._session_context[device_id] = {
                                "intent": "CALENDAR",
                                "action": "CREATE",
                                "params": {
                                    "summary": params.get("summary", "Sự kiện mới"),
                                    "available_slots": slots_str,
                                    "duration_minutes": duration
                                }
                            }
                            keep_mic_open = True
                        else:
                            spoken_text = "Không tìm thấy khung giờ nào trống và phù hợp cả."
                            keep_mic_open = False
                            
                    except Exception as e:
                        logger.error(f"[{device_id}] Loi parse datetime o FIND_SLOT: {e}")
                        spoken_text = "Đệ không hiểu rõ khoảng thời gian huynh muốn tìm, huynh nhắc lại nhé."
                        keep_mic_open = False
                else:
                    # VÁ LỖI: Không lưu State nếu thiếu thời gian tham chiếu.
                    # Để AI giao tiếp (CHAT) hỏi lại người dùng.
                    keep_mic_open = True
                    
            elif intent == "CALENDAR" and action == "READ":
                st_str = params.get("start_time")
                et_str = params.get("end_time")
                
                try:
                    if st_str:
                        st = datetime.fromisoformat(st_str)
                    else:
                        st = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                        
                    if et_str:
                        et = datetime.fromisoformat(et_str)
                    else:
                        from datetime import timedelta
                        et = st + timedelta(days=1)
                        
                    async with AsyncSessionLocal() as db:
                        events = await crud_calendar.get_events_in_range_ordered(db, st, et)
                    
                    if events:
                        # format lại chuỗi
                        agenda = ", ".join([f"{e.summary} lúc {e.start_time.strftime('%H:%M')}" for e in events])
                        react_prompt = f"Dữ liệu lịch trình từ DB (đã sắp xếp): {agenda}. Hãy đóng vai trò là trợ lý ảo, đọc lại danh sách này thật tự nhiên, ngắn gọn. Bắt buộc trả về chuỗi JSON đúng schema hệ thống với action='NONE'."
                        react_data = await llm_api.chat(react_prompt, "Đọc lịch giúp tôi")
                        spoken_text = react_data.get("spoken_response", f"Thưa huynh có các lịch sau: {agenda}")
                    else:
                        spoken_text = "Thưa huynh, trong khoảng thời gian này huynh không có lịch nào cả."
                        
                except Exception as e:
                    logger.error(f"[{device_id}] Loi parse datetime o READ: {e}")
                    spoken_text = "Đệ chưa rõ huynh muốn xem lịch của khoảng thời gian nào."
                    
                keep_mic_open = False
                
            elif intent == "DEVICE" and action in ["TURN_ON", "TURN_OFF"]:
                self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                keep_mic_open = True

            elif action == "CONFIRM" and pending_state:
                await self._execute_transaction(device_id, pending_state)
                self._session_context.pop(device_id, None)
                keep_mic_open = False
                spoken_text = "Đã chốt xong lệnh và xử lí thao tác"
            elif action == "CANCEL":
                self._session_context.pop(device_id, None)
                keep_mic_open = False
                spoken_text = "Đã hủy thao tác đang chờ "

        except Exception as e:
            logger.error(f"[{device_id}] Loi DB/Logic Agent: {e}", exc_info=True)
            spoken_text = "Có lỗi khi hệ thống xử lí dữ liệu, thử lại nhé"
            keep_mic_open = False

        return spoken_text, keep_mic_open

    async def _execute_transaction(self, device_id: str, state: dict):
        intent = state["intent"]
        action = state["action"]
        params = state["params"]
        
        if intent == "CALENDAR":
            async with AsyncSessionLocal() as db:
                sync_needed = False
                if action == "CREATE":
                    if not params.get("start_time") or not params.get("end_time"):
                        logger.error(f"[{device_id}] Transaction bi chan: Thieu thoi gian")
                        return
                    
                    event_in = CalendarEventCreate(**params)
                    await crud_calendar.create_event(db, event_in)
                    sync_needed = True
                elif action == "UPDATE":
                    if "id" in params:
                        update_fields = {}
                        if "new_summary" in params: update_fields["summary"] = params["new_summary"]
                        if "new_start_time" in params: update_fields["start_time"] = params["new_start_time"]
                        if "new_end_time" in params: update_fields["end_time"] = params["new_end_time"]
                        if "new_location" in params: update_fields["location"] = params["new_location"]
                        if "is_cancelled" in params: update_fields["is_cancelled"] = params["is_cancelled"]
                        
                        #Nếu LLM phân tích ra thẳng trường db gốc
                        for field in ["summary", "start_time", "end_time", "is_cancelled", "location"]:
                            if field in params and field not in update_fields:
                                update_fields[field] = params[field]
                        
                        event_upd = CalendarEventUpdate(**update_fields)
                        await crud_calendar.update_event(db, params["id"], event_upd)
                        sync_needed = True
                    else:
                        logger.error(f"[{device_id}] LỖI: LLM không truyền ID để UPDATE")
                elif action == "DELETE":
                    if "id" in params:
                        await crud_calendar.delete_event(db, params["id"])
                        sync_needed = True
                    else:
                        logger.error(f"[{device_id}] LỖI: LLM không truyền ID để DELETE")
                        
                if sync_needed:
                    await push_sync_to_device(device_id, db)

        if intent == "DEVICE":
            ep_id = params.get("ep_id")
            start_time_str = params.get("start_time")
            if ep_id and action in ["TURN_ON", "TURN_OFF"]:
                
                # Neu co hen gio thi luu vao database
                if start_time_str:
                    st = datetime.fromisoformat(start_time_str)
                    
                    # Ép payload MQTT vào trường summary của lịch
                    cmd_payload = json.dumps({"ep_id": ep_id, "action": action})
                    
                    event_in = CalendarEventCreate(
                        summary=cmd_payload,
                        start_time=st,
                        end_time=st + timedelta(minutes=1), # Lệnh chỉ trigger ở 1 khoảnh khắc
                        rrule=params.get("rrule")
                    )
                    
                    async with AsyncSessionLocal() as db:
                        await crud_calendar.create_event(db, event_in, source=EventSource.DEVICE_TIMER)                        
                        await push_sync_to_device(device_id)
                        
                    logger.info(f"[{device_id}] Hen gio thuc hien {action} cho {ep_id} lúc {st}")
                else:
                    cmd_data = {
                        "ep_id": ep_id,
                        "action": action
                    }
                    
                    target_topic = f"iot_schedule/{device_id}/shadow/update"
                    payload = PayloadBuilder.build_json(cmd_data)
                    corr_id = f"sync_{uuid.uuid4().hex[:8]}"
                    resp_topic = MqttTopics.ack(device_id, "shadow_response")
                    
                    # Bắn lệnh không cần chờ (Fire & Forget)
                    publish_message(
                        topic=target_topic,
                        payload=payload,
                        qos=2,
                        response_topic = resp_topic,
                        correlation_data = corr_id.encode('utf-8'),
                        message_expiry_interval = 3600
                    )
                    logger.info(f"[{device_id}] Đã ra lệnh {action} cho {ep_id}")
                    
                    
            else:
                logger.error(f"[{device_id}] Thiếu tham số, không thể điều khiển thiết bị!")
                
    def clear_session(self, device_id: str):
        """Dọn dẹp phiên làm việc trên RAM để tránh kẹt State"""
        if device_id in self._session_context:
            self._session_context.pop(device_id, None)
            logger.info(f"[{device_id}] Đã xóa bộ nhớ đệm (Session Context)")
voice_agent = VoiceAgentService()