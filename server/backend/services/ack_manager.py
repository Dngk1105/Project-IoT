from typing import Callable

from sqlalchemy import select
from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.shadow import DeviceEventShadow

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
                
                if correlation_id in PENDING_ACKS:
                    synced_ids = PENDING_ACKS.pop(correlation_id, [])
                
                if synced_ids:
                    await self._update_shadow_db(device_id, synced_ids)
                else:
                    logger.warning(f"[{device_id}] nhan ACK nhung khong thay Correlation ID {correlation_id} trong cache")
            else:
                error_reason = payload.get("reason", "UNKNOWN_ERR")
                logger.error(f"[{device_id}] Lỗi khi ghi Lịch học vào Flash! | Lý do: {error_reason}")
        elif action == "shadow_response":
            logger.info(f"[{device_id}] Câp nhật trạng thái Device Shadow")
            await self.process_device_shadow(device_id, payload)
                
        else:
            logger.info(f"Nhận ACK từ [{device_id}] cho tác vụ {action}: {payload}")
            
    async def _update_shadow_db(self, device_id: str, synced_ids: list):
        """Hàm ghi/cập nhật mốc thời gian đồng bộ vào bảng DeviceEventShadow"""
        async with AsyncSessionLocal() as session:
            try:
                for event_id in synced_ids:
                    shadow_entry = DeviceEventShadow(
                        device_id=device_id,
                        event_id=event_id
                    )
                    await session.merge(shadow_entry)
                
                await session.commit()
                logger.info(f"[{device_id}] Da cap nhat Shadow DB cho {len(synced_ids)} sự kiện.")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"[{device_id}] Lỗi nghiêm trọng khi cập nhật Shadow DB: {e}", exc_info=True)
                
    async def process_device_shadow(self, device_id: str,payload: dict):
        """Xu li trang thai thiet bi ngoai vi"""
        core_data = payload.get("data", payload)
        ep_id = core_data.get("ep_id")
        new_state = core_data.get("reported_state")
        
        if ep_id and new_state:
            async with AsyncSessionLocal() as session:
                from models.shadow import EndpointStateShadow
                stmt = select(EndpointStateShadow).where(
                    EndpointStateShadow.device_id == device_id,
                    EndpointStateShadow.ep_id == ep_id
                )
                result = await session.execute(stmt)
                ep_record = result.scalar_one_or_none()
                
                if ep_record:
                    ep_record.reported_state = new_state
                    await session.commit()
                    logger.info(f"[{device_id}] Cập nhật Shadow: {ep_id} -> {new_state}")

ack_manager_service = AckManagerService()