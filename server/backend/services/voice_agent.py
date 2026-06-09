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
from core.mqtt_protocol import PayloadBuilder
from models.calendar import EventSource


logger = get_logger(__name__, "voice_agent")

async def find_match_by_llm(user_intent: str, events: list) -> str:
    # neu khong co su kien nao thi bo qua
    if not events:
        return None
        
    # rut gon du lieu de tiet kiem token
    event_list = [{"id": str(e.id), "summary": e.summary, "time": e.start_time.strftime('%H:%M %d/%m')} for e in events]
    
    sys_prompt = f"""
    Ban la cong cu doi chieu du lieu. Nguoi dung muon thao tac voi su kien co y nghia la: '{user_intent}'.
    Duoi day la danh sach cac su kien dang co:
    {json.dumps(event_list, ensure_ascii=False)}
    
    Nhiem vu: Tim su kien KHOP NHAT voi y dinh cua nguoi dung dua tren ngu nghia (Semantic matching). "da bong" co the khop voi "thi dau bong da".
    Tra ve DUY NHAT mot chuoi JSON co dinh dang sau:
    {{
        "matched_id": "ID cua su kien khop nhat, hoac null neu khong co su kien nao lien quan"
    }}
    """
    
    try:
        match_data = await llm_api.chat(sys_prompt, "Hay tim ID khop nhat")
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
                ep_list = [f"- {ep.name} (ep_id: '{ep.ep_id}', trang thai: {ep.reported_state}, lenh ho tro: {ep.supported_cmds})" for ep in endpoints]
                device_context = "THIẾT BỊ NGOẠI VI ĐANG CÓ:\n" + "\n".join(ep_list)

        pending_state = self._session_context.get(device_id)
        context_str = f"LUU Y: He thong dang cho xac nhan hanh dong {pending_state['action']} voi du lieu: {pending_state['params']}." if pending_state else ""
        
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
        
        require_confirmation = False

        try:
            if intent == "CALENDAR" and action == "CREATE":
                if "start_time" in params and "end_time" in params:
                    st = params["start_time"]
                    et = params["end_time"]
                    async with AsyncSessionLocal() as db:
                        collisions = await crud_calendar.check_collision(db, st, et)
                        if collisions:
                            conflict_titles = ", ".join([c.summary for c in collisions])
                            spoken_text = f"Khung giờ này trùng với {conflict_titles}. Huynh có muốn ghi đè không"
                
                self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                require_confirmation = True
                
            elif intent == "CALENDAR" and action in ["UPDATE", "DELETE"]:
                summary_kw = params.get("summary", "").lower()
                st_str = params.get("start_time")
                et_str = params.get("end_time")

                if summary_kw:
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
                        if matched_id:
                            spoken_text = f"Đệ đã tìm thấy sự kiện {matched_event.summary}. Huynh xác nhận {action.lower()} chứ?"
                        else:
                            spoken_text = f"Đệ đã khóa sự kiện. Huynh xác nhận {action.lower()} chứ?"
                        self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                        require_confirmation = True
                    else:
                        spoken_text = f"Đệ đã rà soát nhưng không tìm thấy lịch nào liên quan đến '{summary_kw}' trong khung giờ này cả."
                        require_confirmation = False
                else:
                    self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                    require_confirmation = True

            elif intent == "CALENDAR" and action == "FIND_SLOT":
                duration = int(params.get("duration_minutes", 60))
                st_str = params.get("start_time")
                et_str = params.get("end_time")
                
                if st_str and et_str:
                    try:
                        st = datetime.fromisoformat(st_str)
                        et = datetime.fromisoformat(et_str)
                        async with AsyncSessionLocal() as db:
                            slots = await crud_calendar.find_free_slots(db, st, et, duration)
                        
                        if slots:
                            top_slots = slots[:3]
                            slots_str = ", ".join([f"Từ {s['start'].strftime('%H:%M %d/%m')} đến {s['end'].strftime('%H:%M %d/%m')}" for s in top_slots])
                            
                            react_prompt = f"Đề xuất ngắn gọn 1 trong các giờ sau cho sự kiện '{params.get('summary', 'mới')}': {slots_str}. Trả về json y hệt schema của bạn, với thông tin params và câu hỏi người dùng"
                            react_data = await llm_api.chat(react_prompt, "Chọn giờ giúp tôi")
                            spoken_text = react_data.get("spoken_response", spoken_text)
                            
                            merged_params = params.copy()
                            merged_params.update(react_data.get("parameters", {}))
                            
                            self._session_context[device_id] = {
                                "intent": "CALENDAR",
                                "action": "CREATE",
                                "params": merged_params
                            }
                            require_confirmation = True
                        else:
                            spoken_text = "Không tìm thấy khung giờ nào trống và phù hợp cả."
                            require_confirmation = False
                    except Exception as e:
                        logger.error(f"[{device_id}] Loi parse datetime o FIND_SLOT: {e}")
                        spoken_text = "Đệ không hiểu rõ khoảng thời gian huynh muốn tìm, huynh nhắc lại nhé."
                        require_confirmation = False
                else:
                    self._session_context[device_id] = {
                        "intent": intent,
                        "action": action,
                        "params": params
                    }
                    require_confirmation = True
                    
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
                        events = await crud_calendar.get_events_in_range(db, st, et)
                    
                    if events:
                        agenda = ", ".join([f"{e.summary} lúc {e.start_time.strftime('%H:%M')}" for e in events])
                        react_prompt = f"Dữ liệu từ DB: {agenda}. Hãy đóng vai trò là một người trợ lí và trả về lịch trình này thật tự nhiên. Trả về đúng schema JSON mặc định."
                        react_data = await llm_api.chat(react_prompt, "Đọc lịch giúp tôi")
                        spoken_text = react_data.get("spoken_response", f"Thưa huynh có các lịch sau: {agenda}")
                    else:
                        spoken_text = "Thưa huynh, trong khoảng thời gian này huynh không có lịch nào cả."
                        
                except Exception as e:
                    logger.error(f"[{device_id}] Loi parse datetime o READ: {e}")
                    spoken_text = "Đệ chưa rõ huynh muốn xem lịch của khoảng thời gian nào."
                    
                require_confirmation = False
                
            elif intent == "DEVICE" and action in ["TURN_ON", "TURN_OFF"]:
                self._session_context[device_id] = {"intent": intent, "action": action, "params": params}
                require_confirmation = True

            elif action == "CONFIRM" and pending_state:
                await self._execute_transaction(device_id, pending_state)
                self._session_context.pop(device_id, None)
                spoken_text = "Đã chốt xong lệnh và xử lí thao tác"
            elif action == "CANCEL":
                self._session_context.pop(device_id, None)
                spoken_text = "Đã hủy thao tác đang chờ "

        except Exception as e:
            logger.error(f"[{device_id}] Loi DB/Logic Agent: {e}", exc_info=True)
            spoken_text = "Có lỗi khi hệ thống xử lí dữ liệu, thử lại nhé"
            require_confirmation = False

        return spoken_text, require_confirmation

    async def _execute_transaction(self, device_id: str, state: dict):
        intent = state["intent"]
        action = state["action"]
        params = state["params"]
        
        if intent == "CALENDAR":
            async with AsyncSessionLocal() as db:
                sync_needed = False
                if action == "CREATE":
                    event_in = CalendarEventCreate(**params)
                    await crud_calendar.create_event(db, event_in)
                    sync_needed = True
                elif action == "UPDATE":
                    if "id" in params:
                        event_upd = CalendarEventUpdate(**params)
                        await crud_calendar.update_event(db, params["id"], event_upd)
                        sync_needed = True
                    else:
                        logger.error(f"[{device_id}] LOI: LLM khong truyen ID de UPDATE!")
                elif action == "DELETE":
                    if "id" in params:
                        await crud_calendar.delete_event(db, params["id"])
                        sync_needed = True
                    else:
                        logger.error(f"[{device_id}] LOI: LLM khong truyen ID de DELETE!")
                        
                if sync_needed:
                    await push_sync_to_device(device_id)

        if intent == "DEVICE":
            ep_id = params.get("device_id")
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
                    
                    # Bắn lệnh không cần chờ (Fire & Forget)
                    publish_message(target_topic, payload, qos=2)
                    logger.info(f"[{device_id}] Đã ra lệnh {action} cho {ep_id}")
                    
                    
            else:
                logger.error(f"[{device_id}] Thiếu tham số, không thể điều khiển thiết bị!")
voice_agent = VoiceAgentService()