from fastapi import FastAPI
from fastapi_mqtt import FastMQTT, MQTTConfig
from contextlib import asynccontextmanager
import json

# 1. Cấu hình kết nối MQTT Broker
mqtt_config = MQTTConfig(
    host="localhost",
    port=1883,
    keepalive=60
)

mqtt = FastMQTT(config=mqtt_config)

# Biến global lưu trạng thái kết nối MQTT an toàn
is_mqtt_connected = False

# 2. Quản lý vòng đời của ứng dụng FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[SYSTEM] Khởi động MQTT Client...")
    await mqtt.mqtt_startup()
    yield
    print("[SYSTEM] Đóng MQTT Client...")
    await mqtt.mqtt_shutdown()

# 3. Khởi tạo FastAPI
app = FastAPI(lifespan=lifespan, title="HUST IoT Assistant - Central Node")

# 4. Các sự kiện (Callbacks) của MQTT
@mqtt.on_connect()
def connect(client, flags, rc, properties):
    global is_mqtt_connected
    is_mqtt_connected = True
    print("[MQTT] Đã kết nối tới Broker thành công!")
    
    # Đăng ký lắng nghe LWT và Telemetry từ ESP32
    client.subscribe("hust_iot/assistant/esp32_main/sys/status")
    client.subscribe("hust_iot/assistant/esp32_main/sys/telemetry")
    print("[MQTT] Đã subscribe: sys/status & sys/telemetry")

@mqtt.on_message()
async def message(client, topic, payload, qos, properties):
    msg_str = payload.decode()
    print(f"\n[MQTT REC] Topic: {topic}")
    
    try:
        # Tạm thời parse JSON để kiểm tra log
        data = json.loads(msg_str)
        print(f"[MQTT REC] Data : {data}")
    except json.JSONDecodeError:
        print(f"[MQTT REC] Raw  : {msg_str}")

@mqtt.on_disconnect()
def disconnect(client, packet, exc=None):
    global is_mqtt_connected
    is_mqtt_connected = False
    print("[MQTT] Mất kết nối tới Broker!")

@mqtt.on_subscribe()
def subscribe(client, mid, qos, properties):
    print(f"[MQTT] Xác nhận đã subscribe thành công (mid={mid})")

# 5. Route Test HTTP
@app.get("/")
async def root():
    return {
        "status": "Backend API đang chạy",
        "mqtt_connected": is_mqtt_connected
    }