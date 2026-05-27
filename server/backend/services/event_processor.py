import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)

class EventProcessorService:
    def __init__(self):
        pass
    
    async def process_event(self, device_id: str, action: str, payload: dict, publish_cb: Callable):
        #Tra ve UNIX TimeStamp
        if action == "time_request":
            current_unix_time = int(time.time())
            
            #Dong goi theo chuan
            response_payload = {
                "v": "1.0",
                "data": {
                    "timestamp": current_unix_time
                }
            }
            
            cmd_topic = f"iot_schedule/{device_id}/commands/time_sync"
            publish_cb(cmd_topic, response_payload, qos=1)
            logger.info(f"Đã cấp giờ chuẩn ({current_unix_time}) cho [{device_id}]")
            
        elif action == "button_press":
            btn_id = payload.get("data", {}).get("button")
            logger.info(f"Người dùng bấm nút {btn_id} trên mạch [{device_id}]")
        
        elif action == "audio_control":
            state = payload.get("data", {}).get("state")
            logger.info(f"Trạng thái Mic của [{device_id}]: {state}")

        else:
            logger.warning(f"Sự kiện không xác định từ [{device_id}]: {action}")
            
event_processor_service = EventProcessorService()