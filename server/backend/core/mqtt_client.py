from fastapi_mqtt import FastMQTT, MQTTConfig
from gmqtt import Client as MQTTClient
from typing import Any
import json
import logging

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

def publish_message(topic: str, payload: dict, qos: int = 1, retain: bool = False):
    """Hàm bọc (Wrapper) để tự động chuyển dict thành JSON và in log"""
    try:
        json_payload = json.dumps(payload)
        fast_mqtt.publish(message_or_topic = topic, payload= json_payload, qos=qos, retain=retain)
        logger.info(f"[GỬI] Topic: {topic} | Payload: {json_payload}")
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
    client.subscribe("device/+/status", qos=1)

@fast_mqtt.on_message()
async def on_message(client: MQTTClient, topic: str, payload: bytes, qos: int, properties: Any):
    """Hàm này hứng mọi tin nhắn mà Backend đã subscribe"""
    try:
        msg_str = payload.decode('utf-8')
        logger.info(f"[NHẬN] Topic: {topic} | Payload: {msg_str}")
    except Exception as e:
        logger.error(f"Lỗi giải mã payload từ topic {topic}: {e}")

@fast_mqtt.on_disconnect()
def on_disconnect(client: MQTTClient, packet, exc=None):
    logger.warning("Backend đã ngắt kết nối với MQTT Broker!")

