"""
relay_stream.py — Relay audio 2 chiều ESP32 ↔ PC
- Nhận raw PCM từ topic stream_up  → phát qua loa PC
- Gửi lại raw PCM xuống topic stream_down → ESP32 phát qua MAX98357A

Yêu cầu:
    pip install paho-mqtt pyaudio

Chạy: python relay_stream.py
"""

import paho.mqtt.client as mqtt
import pyaudio
import queue
import threading

# =========================================================================
# CẤU HÌNH
# =========================================================================
MQTT_BROKER  = "192.168.1.2"     # IP broker — khớp MQTT_BROKER_URI
MQTT_PORT    = 1883
DEVICE_ID    = "e072a1d6fa90"    # Device ID từ log ESP32

SAMPLE_RATE  = 16000
CHANNELS     = 1
FORMAT       = pyaudio.paInt16
CHUNK        = 512

TOPIC_UP     = f"iot_schedule/{DEVICE_ID}/audio/stream_up"    # Nhận từ Mic
TOPIC_DOWN   = f"iot_schedule/{DEVICE_ID}/audio/stream_down"  # Gửi xuống Loa

# =========================================================================
# HÀNG ĐỢI — tách MQTT callback khỏi playback thread
# =========================================================================
playback_queue = queue.Queue(maxsize=200)

mqtt_client = None  # Tham chiếu global để publish từ playback thread

# =========================================================================
# MQTT CALLBACKS
# =========================================================================
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Kết nối broker {MQTT_BROKER} OK")
    client.subscribe(TOPIC_UP, qos=0)
    print(f"[MQTT] Subscribe: {TOPIC_UP}")
    print(f"[RELAY] Sẵn sàng — Nói vào mic ESP32!")
    print(f"        Audio sẽ phát qua loa PC VÀ loa ESP32 đồng thời.")
    print("        Ctrl+C để dừng.\n")

def on_message(client, userdata, msg):
    """Nhận PCM từ mic ESP32, đẩy vào queue để relay."""
    try:
        playback_queue.put_nowait(msg.payload)
    except queue.Full:
        pass  # Bỏ qua nếu queue đầy

def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Mất kết nối — reason={reason_code}")

# =========================================================================
# RELAY THREAD
# Đọc từ queue → phát qua loa PC → publish lại xuống stream_down
# =========================================================================
def relay_thread(pc_stream):
    print("[RELAY] Thread bắt đầu.")
    while True:
        try:
            pcm_bytes = playback_queue.get(timeout=5)
            if pcm_bytes is None:
                break

            if len(pcm_bytes) % 2 != 0:
                pcm_bytes = pcm_bytes[:-1]

            # 1. Phát qua loa PC
            pc_stream.write(pcm_bytes, exception_on_underflow=False)

            # 2. Gửi xuống stream_down để ESP32 phát qua MAX98357A
            if mqtt_client and mqtt_client.is_connected():
                mqtt_client.publish(TOPIC_DOWN, pcm_bytes, qos=0)

        except queue.Empty:
            continue
        except OSError as e:
            print(f"[AUDIO] Lỗi: {e}")

# =========================================================================
# MAIN
# =========================================================================
def main():
    global mqtt_client

    pa = pyaudio.PyAudio()

    # Hiển thị thiết bị output
    print("[AUDIO] Thiết bị output:")
    default_idx = pa.get_default_output_device_info()["index"]
    for i in range(pa.get_device_count()):
        dev = pa.get_device_info_by_index(i)
        if dev["maxOutputChannels"] > 0:
            marker = " ← default" if i == default_idx else ""
            print(f"  [{i}] {dev['name']}{marker}")
    print()

    pc_stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        output=True,
        frames_per_buffer=CHUNK,
    )

    t = threading.Thread(target=relay_thread, args=(pc_stream,), daemon=True)
    t.start()

    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="pc_relay_server",
        protocol=mqtt.MQTTv5
    )
    mqtt_client.on_connect    = on_connect
    mqtt_client.on_message    = on_message
    mqtt_client.on_disconnect = on_disconnect

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Dừng relay.")
    except ConnectionRefusedError:
        print(f"[LỖI] Không kết nối được broker {MQTT_BROKER}:{MQTT_PORT}")
    finally:
        playback_queue.put(None)
        t.join(timeout=2)
        pc_stream.stop_stream()
        pc_stream.close()
        pa.terminate()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()