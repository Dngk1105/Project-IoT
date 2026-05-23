from fastapi import APIRouter, Body
from pydantic import BaseModel
from core.mqtt_client import fast_mqtt

router = APIRouter(prefix="/test", tags=["MQTT Testing"])

# Định nghĩa khuôn mẫu dữ liệu (Schema)
class PublishSchema(BaseModel):
    topic: str = "device/esp32_test/commands/alarm"
    payload: dict = {"action": "snooze", "duration": 300}
    qos: int = 1

class SubscribeSchema(BaseModel):
    topic: str = "device/+/telemetry" # Hỗ trợ wildcard + và #

@router.post("/publish")
async def test_publish(data: PublishSchema):
    """Bắn một gói tin JSON tới Topic bất kỳ"""
    fast_mqtt.publish(data.topic, data.payload, data.qos)
    return {"message": "Đã gửi lệnh Publish", "data": data}

@router.post("/subscribe")
async def test_subscribe(data: SubscribeSchema):
    """Yêu cầu Backend lắng nghe một Topic mới (Kết quả in ra Terminal)"""
    fast_mqtt.subscribe(topic=data.topic)
    return {"message": f"Đã theo dõi topic {data.topic}. Hãy xem kết quả in ra ở Terminal (Console)."}