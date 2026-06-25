from typing import Callable

from sqlalchemy import select, delete
from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.shadow import DeviceEventShadow
from models.calendar import CalendarEvent
from services.device_manager import DeviceManagerService

logger = get_logger(__name__, "ack_manager.log")

#Luu correlation id -> event id
PENDING_ACKS = {}


class AckManagerService:
    def __init__(self):
        pass

    async def process_ack(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        # {"status": "success", "correlation_id": "..."}
        status = payload.get("status", "").lower()
        correlation_id = payload.get("correlation_id", "")
        
        if action == "sync_response":
            if status == "success":
                logger.info(f"[{device_id}] Ghi tkb thanh cong vao Flash (Correlation: {correlation_id})")
                
                sync_payload = PENDING_ACKS.pop(correlation_id, None)
                
                if sync_payload:
                    await self._update_shadow_db(device_id, sync_payload)
                else:
                    logger.warning(f"[{device_id}] nhan ACK nhung khong thay Correlation ID {correlation_id} trong cache")
            else:
                error_reason = payload.get("reason", "UNKNOWN_ERR")
                logger.error(f"[{device_id}] Lỗi khi ghi Lịch học vào Flash! | Lý do: {error_reason}")
        elif action == "shadow_response":
            logger.info(f"[{device_id}] Câp nhật trạng thái Device Shadow")
            device_service = DeviceManagerService()
            await device_service.process_device_shadow(device_id, action, payload, publish_cb)
                
        else:
            logger.info(f"Nhận ACK từ [{device_id}] cho tác vụ {action}: {payload}")
            
    async def _update_shadow_db(self, device_id: str, sync_payload: list):
        """Hàm ghi/cập nhật mốc thời gian đồng bộ vào bảng DeviceEventShadow"""
        async with AsyncSessionLocal() as session:
            try:
                upsert_ids = sync_payload.get("upsert_ids", [])
                delete_ids = sync_payload.get("delete_ids", [])
                
                for event_id in upsert_ids:
                    event = await session.get(CalendarEvent, event_id)
                    if not event:
                        continue
                    shadow_entry = DeviceEventShadow(
                        device_id=device_id,
                        event_id=event_id,
                        synced_at=event.updated_at
                    )
                    await session.merge(shadow_entry)
                
                if delete_ids:
                    stmt = delete(DeviceEventShadow).where(
                        DeviceEventShadow.device_id == device_id,
                        DeviceEventShadow.event_id.in_(delete_ids)
                    )
                    await session.execute(stmt)
                
                await session.commit()
                logger.info(f"[{device_id}] Da cap nhat Shadow DB: UPSERT {len(upsert_ids)} | DELETE {len(delete_ids)}.")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"[{device_id}] Lỗi nghiêm trọng khi cập nhật Shadow DB: {e}", exc_info=True)

ack_manager_service = AckManagerService()