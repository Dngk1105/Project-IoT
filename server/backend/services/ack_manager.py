import logging
from typing import Callable

logger = logging.getLogger(__name__)

class AckManagerService:
    def __init__(self):
        pass

    async def process_ack(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        msg_id = payload.get("msg_id")
        status = payload.get("data", {}).get("status")
        
        if action == "sync_response":
            if status == "SUCCESS":
                logger.info(f"[{device_id}] Đã ghi Lịch học thành công vào Flash! (msg_id: {msg_id})")
                # TODO: Update Database (Schedule.sync_status = True)
            else:
                logger.error(f"[{device_id}] Lỗi khi ghi Lịch học vào Flash! (msg_id: {msg_id})")
        else:
            logger.info(f"Nhận ACK từ [{device_id}] cho tác vụ {action}: {payload}")

ack_manager_service = AckManagerService()