# ESP32 MQTT Handler Guide

Tài liệu này hướng dẫn cách sử dụng module:

- WiFi
- MQTT Publish
- MQTT Subscribe
- MQTT Event Handler

trên ESP32 sử dụng:

- ESP-IDF
- PlatformIO
- MQTT Broker (Mosquitto)

---

# 1. Cấu trúc project

```txt
esp/
├── include/
│   ├── wifi.h
│   └── mqtt_handler.h
│
├── src/
│   ├── main.cpp
│   ├── wifi.cpp
│   └── mqtt_handler.cpp
│
└── platformio.ini
````

---

# 2. Chức năng từng file

| File             | Chức năng                          |
| ---------------- | ---------------------------------- |
| wifi.cpp         | Kết nối WiFi                       |
| mqtt_handler.cpp | MQTT connect / publish / subscribe |
| main.cpp         | Entry point chính                  |
| platformio.ini   | Config PlatformIO                  |

---

# 3. Cài đặt broker MQTT

Project sử dụng:

* Mosquitto MQTT Broker
* chạy bằng Docker

---

## Chạy broker

Di chuyển tới:

```bash
server/infrastructure
```

Chạy:

```bash
docker-compose up -d
```

---

## Kiểm tra broker

```bash
docker ps
```

Phải thấy container Mosquitto đang chạy.

---

# 4. Lấy IP máy tính

ESP32 cần connect tới IP LAN của máy tính chạy broker.

---

## Windows

Mở CMD:

```bash
ipconfig
```

Tìm:

```txt
IPv4 Address
```

Ví dụ:

```txt
192.168.1.5
```

---

# 5. Config WiFi

File:

```txt
src/wifi.cpp
```

Sửa:

```cpp
#define WIFI_SSID      "YOUR_WIFI"
#define WIFI_PASSWORD  "YOUR_PASSWORD"
```

Ví dụ:

```cpp
#define WIFI_SSID      "PhongTro"
#define WIFI_PASSWORD  "12345678"
```

---

# 6. Config MQTT Broker

File:

```txt
src/mqtt_handler.cpp
```

Sửa:

```cpp
mqtt_cfg.broker.address.uri =
    "mqtt://192.168.1.5:1883";
```

Trong đó:

| Thành phần  | Ý nghĩa        |
| ----------- | -------------- |
| mqtt://     | Giao thức MQTT |
| 192.168.1.5 | IP máy tính    |
| 1883        | Port MQTT      |

---

# 7. Build project

```bash
platformio run
```

---

# 8. Upload code

```bash
platformio run -t upload
```

---

# 9. Mở Serial Monitor

```bash
platformio device monitor
```

---

# 10. Log mong đợi

```txt
WIFI CONNECTED SUCCESS
MQTT CONNECTED
SUBSCRIBED
PUBLISH SUCCESS
```

---

# 11. MQTT Publish

ESP32 gửi dữ liệu lên broker bằng:

```cpp
mqtt_send(
    "hust_iot/test",
    "hello from esp32"
);
```

---

## Ý nghĩa

| Tham số          | Ý nghĩa |
| ---------------- | ------- |
| hust_iot/test    | Topic   |
| hello from esp32 | Payload |

---

# 12. MQTT Subscribe

ESP subscribe topic:

```cpp
esp_mqtt_client_subscribe(
    client,
    "hust_iot/cmd",
    1
);
```

ESP sẽ nhận mọi message gửi tới:

```txt
hust_iot/cmd
```

---

# 13. MQTT Event System

ESP-IDF MQTT hoạt động theo:

```txt
event-driven architecture
```

KHÔNG cần:

```cpp
while(receive())
```

---

## Flow hoạt động

```txt
Broker gửi packet
        ↓
ESP MQTT task nhận packet
        ↓
ESP-IDF trigger event
        ↓
mqtt_event_handler()
        ↓
mqtt_data_handler()
```

---

# 14. MQTT_EVENT_CONNECTED

Event này xảy ra khi:

```txt
ESP connect broker thành công
```

Code:

```cpp
case MQTT_EVENT_CONNECTED:
```

---

# 15. MQTT_EVENT_DATA

Event này xảy ra khi:

```txt
ESP nhận message từ broker
```

Code:

```cpp
case MQTT_EVENT_DATA:
```

---

# 16. Xử lý dữ liệu nhận được

Hàm:

```cpp
mqtt_data_handler(...)
```

sẽ xử lý:

* topic
* payload

Ví dụ:

```txt
TOPIC: hust_iot/cmd
DATA : LED_ON
```

---

# 17. Test Publish từ máy tính

---

## Dùng terminal

```bash
mosquitto_pub ^
-h localhost ^
-t hust_iot/cmd ^
-m "LED_ON"
```

---

## ESP sẽ nhận

```txt
TOPIC: hust_iot/cmd
DATA : LED_ON
```

---

# 18. Test từ Web Dashboard

Mở:

```txt
server/frontend/html/index.html
```

---

## Topic

```txt
hust_iot/cmd
```

---

## Payload

```json
{
    "led": 1
}
```

---

# 19. Giải thích MQTT QoS

---

## QoS 0

```txt
fire and forget
```

Không đảm bảo tới nơi.

---

## QoS 1

```txt
at least once
```

Broker phải ACK.

---

## QoS 2

```txt
exactly once
```

Đảm bảo tuyệt đối nhưng chậm hơn.

---

# 20. Kiến trúc hệ thống

```txt
ESP32
  ↓
MQTT Broker
  ↓
Backend
  ↓
Web Dashboard
```

---

# 21. Các topic gợi ý

---

## Telemetry

```txt
hust_iot/device_01/telemetry
```

---

## Command

```txt
hust_iot/device_01/cmd
```

---

## Status

```txt
hust_iot/device_01/status
```

---

# 22. Những thứ có thể nâng cấp sau

* JSON parsing
* OTA update
* TLS SSL
* MQTT authentication
* LWT Online/Offline
* Reconnect strategy
* Device manager
* Dynamic topic
* Sensor telemetry
* Fingerprint integration

---

# 23. Những thư mục KHÔNG commit Git

Tạo:

```txt
.gitignore
```

---

## Nội dung

```gitignore
# PlatformIO
.pio/

# ESP-IDF
managed_components/

# Build
build/

# Python
venv/

# VSCode
.vscode/

# Logs
*.log
```

---

# 24. Tạo branch feature

Khuyên dùng:

```bash
git checkout -b feature/esp-mqtt-handler
```

---

# 25. Push branch

```bash
git push -u origin feature/esp-mqtt-handler
```

---

```
```
