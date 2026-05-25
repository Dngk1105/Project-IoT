"""
listen_stream.py — Nghe audio stream từ ESP32 qua MQTT
Chạy trên máy tính: python listen_stream.py

Yêu cầu:
    pip install paho-mqtt pyaudio

Nếu lỗi pyaudio trên Windows:
    pip install pipwin && pipwin install pyaudio

Nếu lỗi pyaudio trên Linux:
    sudo apt install portaudio19-dev && pip install pyaudio

Nếu lỗi pyaudio trên macOS:
    brew install portaudio && pip install pyaudio
"""

import paho.mqtt.client as mqtt
import pyaudio
import struct
import threading
import queue
import sys

# =========================================================================
# CẤU HÌNH — chỉnh cho khớp với config.h của ESP32
# =========================================================================
MQTT_BROKER   = "192.168.1.2"   # IP broker (giống MQTT_BROKER_URI)
MQTT_PORT     = 1883
DEVICE_ID     = "e072a1d6fa90"  # Device ID của ESP32 (thấy trong log)

SAMPLE_RATE   = 16000           # Hz — khớp AUDIO_SAMPLE_RATE
CHANNELS      = 1               # Mono
SAMPLE_FORMAT = pyaudio.paInt16 # 16-bit PCM
CHUNK_SIZE    = 512             # bytes mỗi lần write ra loa

TOPIC_STREAM  = f"iot_schedule/{DEVICE_ID}/audio/stream_up"

# =========================================================================
# HÀNG ĐỢI AUDIO — tách MQTT callback và playback thread
# Tránh block MQTT loop khi pyaudio write bị chậm
# =========================================================================
audio_queue = queue.Queue(maxsize=100)

# =========================================================================
# MQTT CALLBACKS
# =========================================================================
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Kết nối broker {MQTT_BROKER} — reason={reason_code}")
    client.subscribe(TOPIC_STREAM, qos=0)
    print(f"[MQTT] Subscribed: {TOPIC_STREAM}")
    print(f"[AUDIO] Đang nghe... Nói vào mic ESP32!")
    print("        Ctrl+C để dừng.\n")

def on_message(client, userdata, msg):
    """Nhận raw PCM 16-bit từ ESP32, đẩy vào queue để playback thread xử lý."""
    try:
        audio_queue.put_nowait(msg.payload)
    except queue.Full:
        pass  # Bỏ qua nếu queue đầy (playback chậm hơn stream)

def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] Mất kết nối — reason={reason_code}")

# =========================================================================
# PLAYBACK THREAD — đọc từ queue và phát qua loa máy tính
# =========================================================================
def playback_thread(stream):
    print("[AUDIO] Playback thread bắt đầu.")
    while True:
        try:
            pcm_bytes = audio_queue.get(timeout=5)
            if pcm_bytes is None:   # Tín hiệu dừng
                break

            # Validate: phải là số lẻ bytes → lỗi alignment
            if len(pcm_bytes) % 2 != 0:
                pcm_bytes = pcm_bytes[:-1]

            stream.write(pcm_bytes, exception_on_underflow=False)

        except queue.Empty:
            continue
        except OSError as e:
            print(f"[AUDIO] Lỗi write: {e}")

# =========================================================================
# MAIN
# =========================================================================
def main():
    # Khởi tạo PyAudio
    pa = pyaudio.PyAudio()

    # In danh sách thiết bị output để debug
    print("[AUDIO] Thiết bị output khả dụng:")
    default_out = pa.get_default_output_device_info()
    for i in range(pa.get_device_count()):
        dev = pa.get_device_info_by_index(i)
        if dev["maxOutputChannels"] > 0:
            marker = " ← default" if i == default_out["index"] else ""
            print(f"  [{i}] {dev['name']}{marker}")
    print()

    # Mở stream output (loa máy tính)
    stream = pa.open(
        format=SAMPLE_FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        output=True,
        frames_per_buffer=CHUNK_SIZE,
    )

    # Bắt đầu playback thread
    t = threading.Thread(target=playback_thread, args=(stream,), daemon=True)
    t.start()

    # Khởi tạo MQTT client (paho v2 API)
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="pc_listener_stream",
        protocol=mqtt.MQTTv5
    )
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Dừng.")
    except ConnectionRefusedError:
        print(f"[LỖI] Không kết nối được broker tại {MQTT_BROKER}:{MQTT_PORT}")
        print("      Kiểm tra IP broker và đảm bảo Mosquitto đang chạy.")
    finally:
        audio_queue.put(None)   # Dừng playback thread
        t.join(timeout=2)
        stream.stop_stream()
        stream.close()
        pa.terminate()
        client.disconnect()

if __name__ == "__main__":
    main()