import paho.mqtt.client as mqtt
import json
import uuid
import time

# --- CẤU HÌNH BÀI TEST ---
BROKER = "127.0.0.1"
PORT = 1883
DEVICE_ID = "e072a1d6f1bc" # <-- Thay bằng MAC Address ESP32 của huynh đang in trên Serial Monitor
PREFIX = "iot_schedule"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Đã kết nối MQTT Broker! Đang bắn gói Delta xuống {DEVICE_ID}...")
        
        cmd_topic = f"{PREFIX}/{DEVICE_ID}/commands/sync_schedule"
        ack_topic = f"{PREFIX}/{DEVICE_ID}/ack/sync_response"
        corr_id = f"sync_{uuid.uuid4().hex[:8]}"

        # Fake Delta Payload
        payload = {
            "msg_id": "test_msg_001",
            "timestamp": int(time.time()),
            "v": "1.0",
            "data": {
                "add": [
                    {"id": "event-uuid-1", "t": int(time.time()) + 3600, "a": "CLASS", "msg": "Học Hệ điều hành"},
                    {"id": "event-uuid-2", "t": int(time.time()) + 7200, "a": "MEET", "msg": "Họp nhóm IoT"}
                ],
                "upd": [],
                "del": []
            }
        }

        # Cấu hình Properties MQTT v5
        props = mqtt.Properties(mqtt.PacketTypes.PUBLISH)
        props.ResponseTopic = ack_topic
        props.CorrelationData = corr_id.encode('utf-8')

        # Bắn gói tin QoS 2
        client.publish(cmd_topic, json.dumps(payload), qos=2, properties=props)
        print(f"📤 Đã bắn lệnh tới: {cmd_topic}")
        print(f"   - Response Topic yêu cầu: {ack_topic}")
        print(f"   - Correlation ID: {corr_id}")
        print("\n⏳ Đang lắng nghe ESP32 trả ACK về...")
        
        # Lắng nghe ngược lại topic ACK để xem ESP32 có ngoan ngoãn trả lời không
        client.subscribe(ack_topic)

def on_message(client, userdata, msg):
    print(f"\n📥 NHẬN ĐƯỢC PHẢN HỒI TỪ ESP32:")
    print(f"   - Topic: {msg.topic}")
    print(f"   - Payload: {msg.payload.decode('utf-8')}")
    print("\n🎉 BÀI TEST THÀNH CÔNG RỰC RỠ! Nhấn Ctrl+C để thoát.")

# Khởi tạo Client MQTT v5
client = mqtt.Client(client_id="test_trigger_script", protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()