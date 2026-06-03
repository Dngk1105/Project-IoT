from fastapi_mqtt import FastMQTT, MQTTConfig
from gmqtt import Client as MQTTClient
from typing import Any, Dict, Callable
import json
import logging
import time

logger = logging.getLogger(__name__) #ghi log

mqtt_config = MQTTConfig(
    host="127.0.0.1",
    port=1883,
    keepalive=60,
    version=5,
    # username="admin", # Bỏ comment nếu dùng auth
    # password="password"
)

fast_mqtt = FastMQTT(config=mqtt_config)


"""Phân rã chuỗi quy chuẩn: iot_schedule/<device_id>/<category>/<action>"""
def parse_topic (topic: str):
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "iot_schedule":
        return None, None, None
    device_id = parts[1]
    category = parts[2]
    action = parts[3] if len(parts) >= 4 else "none"
    return device_id, category, action

def get_target_service(category: str):
    """
    Mapping category -> service handler
    """
    if category in ("status", "telemetry", "shadow"):
        from services.device_manager import device_manager_service
        
        service_map = {
            "status": device_manager_service.process_lifecycle_status,
            "telemetry": device_manager_service.process_hardware_telemetry,
            "shadow": device_manager_service.process_device_shadow
        }
        return service_map.get(category)

    elif category == "events":
        from services.event_processor import event_processor_service
        return event_processor_service.process_event

    elif category == "audio":
        from services.audio_engine import audio_engine_service
        return audio_engine_service.handle_stream

    elif category == "ack":
        from services.ack_manager import ack_manager_service
        return ack_manager_service.process_ack

    return None

def publish_message(topic: str, payload: dict, qos: int = 1, retain: bool = False, **kwargs):
    """Hàm bọc (Wrapper) để tự động chuyển dict thành JSON và in log"""
    try:
        json_payload = json.dumps(payload)
        fast_mqtt.publish(
            message_or_topic = topic, 
            payload= json_payload, 
            qos=qos, 
            retain=retain,
            **kwargs
        )
        logger.info(f"[GỬI] Topic: {topic} | Payload: {json_payload}")
        if kwargs:
            logger.debug(f"      LĐính kèm MQTTv5 Props: {kwargs}")
    except Exception as e:
        logger.error(f"Lỗi khi gửi bản tin MQTT: {e}")

def subscribe_topic(topic: str, qos: int = 1):
    """Hàm bọc để đăng ký lắng nghe topic lúc Runtime"""
    if fast_mqtt.client:
        fast_mqtt.client.subscribe(topic, qos=qos)
        logger.info(f"[SUBSCRIBE] Đã thêm topic: {topic}")
    else:
        logger.warning(f"Không thể subscribe {topic} vì Client chưa sẵn sàng.")



@fast_mqtt.on_connect()
def on_connect(client: MQTTClient, flags: int, rc: int, properties: Any):
    logger.info(f"Backend đã kết nối tới MQTT Broker (Code: {rc})")
    # Tự động lắng nghe trạng thái của tất cả ESP32 khi server vừa bật
    client.subscribe("iot_schedule/#", qos=1)


@fast_mqtt.on_message()
async def on_message(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    """Hàm này hứng mọi tin nhắn mà Backend đã subscribe"""
    device_id, category, action = parse_topic(topic)
    if not device_id:
        return
    
    # Khong echo lai topic minh pub
    if category == "commands" or action == "stream_down" or action == "control":
        return
    
    target_service = get_target_service(category)

    if not target_service:
        logger.warning(f"Category khong co trong danh muc co the xu li: {category}")
        return

    try:
        if category == "audio":
            # Neu du lieu la audio (truyen theo dang nhi phan)
            # Day payload thang xuong luon, khong parse json 
            await target_service(device_id, action, payload)
        else:
            #parse json cho payload 
            msg_str = payload.decode("utf-8")
            json_data = json.loads(msg_str)
            
            # Cam dam bao thoi gian chinh xac
            client_ts = json_data.get("timestamp", 0)
            if client_ts < 1700000000:  
                # Nếu ESP32 chưa có giờ (gửi số 0) hoặc giờ bị trôi
                # Sử dụng Timestamp của Server thay thế
                json_data["timestamp"] = int(time.time())
                logger.debug(f"Đã tự động trám Timestamp cho [{device_id}] vì thiết bị gửi giờ ảo: {client_ts}")
            
            # Service xu li json sau
            await target_service(device_id, action, json_data, publish_message) #truyen publish() de khong can parse lai file nay
    except UnicodeDecodeError:
        logger.error(f"[{device_id}] Gói tin tại {topic} không phải định dạng UTF-8 hợp lệ!")
    except json.JSONDecodeError:
        logger.error(f"[{device_id}] Bản tin từ {topic} không tuân thủ JSON quy chuẩn!")
    except Exception as e:
        logger.error(f"Lỗi hệ thống khi xử lý gói tin tầng ứng dụng ({topic}): {e}", exc_info=True)
    

@fast_mqtt.on_disconnect()
def on_disconnect(client: MQTTClient, packet, exc=None):
    logger.warning("Backend đã ngắt kết nối với MQTT Broker!")

