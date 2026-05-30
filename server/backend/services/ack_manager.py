from typing import Callable
from core.logger import get_logger
from core.database import AsyncSessionLocal
from models.shadow import DeviceEventShadow

logger = get_logger(__name__)

class AckManagerService:
    def __init__(self):
        pass

    async def process_ack(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        msg_id = payload.get("msg_id")
        data: dict = payload.get("data", {})
        status = data.get("status", "")
        
        if action == "sync_response":
            if status == "SUCCESS":
                # Ví dụ payload data: {"status": "SUCCESS", "synced_ids": ["uuid-1", "uuid-2"]}
                synced_ids = data.get("synced_ids", [])
                logger.info(f"[{device_id}] Đã ghi Lịch học thành công vào Flash! (msg_id: {msg_id})")
                
                if synced_ids: 
                    await self._update_shadow_db(device_id, synced_ids)
            else:
                error_reason = data.get("reason", "UNKNOWN_ERR")
                logger.error(f"[{device_id}] Lỗi khi ghi Lịch học vào Flash! (msg_id: {msg_id} | Lý do: {error_reason})")
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

ack_manager_service = AckManagerService()