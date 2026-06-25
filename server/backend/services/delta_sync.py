from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_

from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.calendar import CalendarEvent
from models.shadow import DeviceEventShadow
from schemas.calendar import EventLiteESP32
from models.calendar import EventSource

#Khoi tao logger chuan theo module core
logger = get_logger(__name__, "scheduler.log")

class DeltaSyncService:
    def __init__(self):
        pass

    async def calculate_delta(self, device_id: str) -> dict:
        """
        So khop lich giua DB va Shadow.
        Chi quet su kien trong 48h toi.
        """
        #Moc thoi gian quy chuan (UTC)
        now = datetime.now(timezone.utc)
        time_limit = now + timedelta(hours=48)

        async with AsyncSessionLocal() as session:
            #Lay cac su kien hop le trong 48h (Khong bi huy)
            stmt_active = select(CalendarEvent).where(
                and_(
                    CalendarEvent.start_time >= now,
                    CalendarEvent.start_time <= time_limit,
                    CalendarEvent.is_cancelled == False
                )
            )
            result_active = await session.execute(stmt_active)
            active_events = result_active.scalars().all()
            
            # chuyen sang dict
            active_dict = {ev.id: ev for ev in active_events}


            #Lay tat ca su kien ESP32 dang giu
            stmt_shadow = select(DeviceEventShadow).where(
                DeviceEventShadow.device_id == device_id
            )
            result_shadow = await session.execute(stmt_shadow)
            shadow_records = result_shadow.scalars().all()
            
            shadow_dict = {sh.event_id: sh for sh in shadow_records}


            add_list = []
            upd_list = []
            del_list = []

            #Quet tim ADD va UPD
            for ev_id, ev in active_dict.items():
                if ev_id not in shadow_dict:
                    #Them moi: DB co, Shadow khong co
                    add_list.append(ev)
                else:
                    #Cap nhat: DB co, Shadow co nhung DB moi hon
                    shadow_rec = shadow_dict[ev_id]
                    if ev.updated_at > shadow_rec.synced_at:
                        upd_list.append(ev)

            #Quet tim DEL
            for sh_event_id in shadow_dict.keys():
                if sh_event_id not in active_dict:
                    #Xoa: Shadow co, DB khong co hoac da bi huy
                    del_list.append(sh_event_id)


            payload_data = {
                "add": [self._minify_event(ev) for ev in add_list],
                "upd": [self._minify_event(ev) for ev in upd_list],
                "del": del_list  #Chi can list ID de xoa tren Flash
            }
            
            #Ghi log ket qua tinh toan
            logger.info(f"[{device_id}] Delta Sync | ADD: {len(add_list)} | UPD: {len(upd_list)} | DEL: {len(del_list)}")
            
            return payload_data

    def _minify_event(self, ev: CalendarEvent) -> dict:
        """Ep kieu su kien DB sang EventLiteESP32 (Tiet kiem RAM)"""
        
        # Anh xa tu EventSource (DB) sang Action Code (ESP32)
        action_map = {
            EventSource.HUST_CTT: "CLASS",   # Lich hoc tren truong -> Hien thi icon/chuong lop hoc
            EventSource.GOOGLE: "MEET",      # Lich Google -> Hien thi icon hop hoac nhac viec
            EventSource.VOICE_AI: "VOICE",   # Lich tu giong noi -> Hien thi icon AI/Mic
            EventSource.LOCAL: "ALARM",      # Lich tao thu cong -> Hien thi icon bao thuc
            EventSource.DEVICE_TIMER: "DEVICE_CMD"
        }
        
        # Lay ma hanh dong, mac dinh la ALARM neu khong khop
        esp32_action = action_map.get(ev.source, "ALARM")

        lite = EventLiteESP32(
            id=ev.id,
            t=int(ev.start_time.timestamp()),
            a=esp32_action,
            msg=ev.summary[:64] # Cat chu de tranh tran vung nho
        )
        return lite.model_dump()

delta_sync_service = DeltaSyncService()