import paho.mqtt.client as mqtt
import json, time, uuid

BROKER = "127.0.0.1"
PORT = 1883
DEVICE_ID = "e072a1d6f1bc"
PREFIX = "iot_schedule"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Đã kết nối MQTT Broker!")
        
        current_time = int(time.time())
        trigger_time = current_time + 15 
        print(f"💣 Đã cài bom nổ chậm vào lúc: {trigger_time} (Sau 15 giây nữa)")
        
        cmd_topic = f"{PREFIX}/{DEVICE_ID}/commands/sync_schedule"
        ack_topic = f"{PREFIX}/{DEVICE_ID}/ack/sync_response"
        corr_id = f"sync_{uuid.uuid4().hex[:8]}"

        payload = {
            "msg_id": "test_phase2_trigger",
            "timestamp": current_time,
            "v": "1.0",
            "data": {
                "add": [{
                    "id": f"event-test-{current_time}", 
                    "t": trigger_time, 
                    "a": "CLASS", 
                    "msg": "Test âm thanh Phase 2"
                }],
                "upd": [],
                "del": []
            }
        }
        
        props = mqtt.Properties(mqtt.PacketTypes.PUBLISH)
        props.ResponseTopic = ack_topic
        props.CorrelationData = corr_id.encode('utf-8')

        # Bắn lệnh đi
        client.publish(cmd_topic, json.dumps(payload), qos=2, properties=props)
        print("📤 Đã đưa gói tin cho Broker...")

def on_publish(client, userdata, mid):
    print(f"✅ Broker đã nhận và xử lý xong QoS 2 (mid={mid})!")
    print("👉 Hãy mở Serial Monitor của C++ lên xem ESP32 kích nổ!")

client = mqtt.Client(client_id="test_phase2_script", protocol=mqtt.MQTTv5)
client.on_connect = on_connect
client.on_publish = on_publish
client.connect(BROKER, PORT, 60)
client.loop_forever() # Để nó chạy nền, huynh muốn tắt thì ấn Ctrl+C