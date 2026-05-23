# Kiến trúc Tổng thể Hệ thống IoT Schedule

## Tổng quan

Bản đặc tả kiến trúc tổng thể (*System Architecture*) cho hệ thống IoT Schedule.

Kiến trúc được thiết kế theo mô hình **Layered Architecture**, tách biệt rõ ràng giữa:

* Phần cứng
* Giao tiếp
* Xử lý logic
* Giao diện người dùng

---

# 1. Lớp Edge (Thiết bị đầu cuối - ESP32)

Đóng vai trò là **"Giác quan"** và **"Người thực thi"** tại chỗ.

Hệ thống hoạt động trên:

* FreeRTOS
* ESP-IDF Framework

## 1.1. Audio Subsystem (I2S)

Quản lý luồng âm thanh:

* Input: Microphone
* Output: Speaker/Buzzer

---

## 1.2. Edge AI Engine (ESP-SR)

### WakeNet

Liên tục lắng nghe offline để phát hiện từ khóa đánh thức.

Ví dụ:

```text
"Hey System"
```

### MultiNet

* MultiNet sử dụng model có sẵn từ ESP-SR.
* Ví dụ tiếng Việt trong tài liệu chỉ mang tính minh họa luồng xử lý.
* Hệ thống ưu tiên tiếng Anh để giảm độ phức tạp khi triển khai offline
  
Ví dụ:

```text
"Stop"
"Snooze 10 minutes"
```

Các lệnh này được xử lý cục bộ mà không cần gửi lên Server.

---

## 1.3. Local Storage (LittleFS)

Bộ nhớ đệm lưu trữ:

* Danh sách lịch trình
* JSON rút gọn
* Dữ liệu cho 24 - 48 giờ tới

Mục tiêu:

* ESP32 vẫn báo thức đúng giờ ngay cả khi mất kết nối mạng.


### ACK xác nhận ghi dữ liệu (Ứng dụng MQTT v5)

Sau khi ESP32 ghi thành công dữ liệu lịch trình xuống LittleFS, hệ thống sử dụng cơ chế Request-Response của MQTT v5 để báo cáo:

* Khi Server đẩy lịch xuống, bản tin `Cmd_Sync` [QoS 2] sẽ đính kèm thuộc tính `Response_Topic` (VD: `ack/esp1`) và `Correlation_Data` (VD: `sync_789`).
* ESP32 xử lý xong sẽ publish một bản tin ACK [QoS 1] vào đúng `Response_Topic` đó, trả lại chính xác `Correlation_Data` và Payload báo trạng thái (`SUCCESS` hoặc `FLASH_ERR`).
* ACK ở tầng ứng dụng này giúp Server biết chắc chắn dữ liệu đã nằm an toàn trong bộ nhớ Flash, độc lập hoàn toàn với ACK của mạng (PUBCOMP của QoS 2).
---

## 1.4. Device Shadow & Telemetry

### Chức năng

* Thu thập trạng thái thiết bị ngoại vi (Device Shadow):

  * Mic
  * Loa
  * LED
  * Nút bấm
  * ...
* Hardware Telemetry & Audio Monitor: Định kỳ (ví dụ: 5 phút/lần) đo đạc thông số sức khỏe của mạch
  * RAM trống
  * Cường độ sóng WiFi RSSI
  * Thời gian hoạt động Uptime
* Giám sát Âm thanh (Audio Heard): Tính năng này sẽ đo data từ Mic I2S để đẩy về Server, giúp phát hiện sớm tình trạng nhiễu phần cứng hoặc hỏng hóc micro từ xa.:
  *  độ dài đoạn âm thanh thu được gần nhất (last_audio_heard_ms)
  *  cường độ đỉnh âm thanh (audio_peak_db) 
* Đóng gói dữ liệu thành JSON
* Gửi trạng thái lên Server


### Software Timer (Voice Watchdog)
* Khi thiết bị chuyển sang trạng thái streaming âm thanh (`STATE_STREAM_UP`) lên Cloud, ESP32 sẽ kích hoạt một Software Timer (VD: 5s timeout).
* Nếu kết nối Wi-Fi bị drop hoặc Server không phản hồi luồng TTS xuống trong thời gian này, ngắt Timer sẽ nổ: thiết bị lập tức xả buffer âm thanh, ngắt kết nối dở dang và tự động phát audio cảnh báo mạng từ bộ nhớ nội bộ, sau đó fallback về trạng thái `STATE_IDLE`.

### MQTT Responsibilities

* Quản lý kết nối MQTT
* Duy trì cờ LWT (*Last Will and Testament*)
* Giúp Server phát hiện thiết bị mất kết nối đột ngột

## 1.5. Kênh Truyền Tải Bền Vững (Persistent Session)
- Cấu hình MQTT Client trên ESP32 với cờ Clean Session = False (hoặc Clean Start = False ở v5).

- Mục tiêu: Khi WiFi chập chờn hoặc rớt mạng ngắn hạn, Broker sẽ tự động lưu lại các bản tin điều khiển quan trọng (QoS 1) và đẩy bù cho ESP32 ngay khi thiết bị tái kết nối thành công mà không cần sub lại các topic từ đầu.
---

# 2. Lớp Connectivity (Mosquitto Broker)

Đóng vai trò là:

* Trạm trung chuyển dữ liệu
* Message Broker MQTT

Mosquitto chạy độc lập trong Docker Container.

## 2.1. TCP Port 1883

Kênh truyền thông không mã hóa dành riêng cho ESP32 và Server Core, áp dụng phân luồng QoS nghiêm ngặt:

* **Luồng âm thanh thô (Audio Stream Up/Down):** Chạy ở **QoS 0** để ưu tiên băng thông, độ trễ thấp nhất, chấp nhận rơi rớt gói tin.
* **Bản tin điều khiển & Đồng bộ lịch (Cmd_Sync):** Chạy ở **QoS 2** (Exactly once) để đảm bảo không lặp, không sót lệnh can thiệp bộ nhớ.
* **Bản tin trạng thái thiết bị ngoại vi & Event (Shadow/Telemetry/Ack):** Chạy ở **QoS 1** (At least once) kết hợp `Clean Session = False` để tự động đẩy bù gói tin khi thiết bị tái kết nối.

### Đánh giá băng thông Audio MQTT

Đây là vấn đề kỹ thuật cần được benchmark thực tế trong quá trình triển khai dự án.

Các yếu tố cần đo đạc:

* Tần số lấy mẫu Audio
* Kích thước chunk MQTT
* Tốc độ WiFi thực tế
* CPU usage của ESP32
* Latency đầu cuối
* Tỷ lệ mất packet

Các bài test sẽ giúp xác định:

* Giới hạn stream ổn định của MQTT
* Có cần nén audio hay không
---

## 2.2. WebSocket Port 9001

Mở cổng WebSocket để cho phép giao diện người dùng (Frontend Web) kết nối trực tiếp vào Broker.

Mục đích:
* Nhận dữ liệu realtime
* Không cần reload trang

Ví dụ dữ liệu:

* Online/Offline state
* Device logs
* Peripheral status

---

# 3. Lớp Backend (FastAPI Core)

Đây là:

* Bộ não trung tâm
* Xử lý tác vụ nặng
* Quản lý dữ liệu toàn cục

---

## 3.1. Device & State Manager

### Chức năng

* Quản lý danh sách thiết bị
* Theo dõi trạng thái Online/Offline
* Lắng nghe topic LWT
* Lưu trạng thái ngoại vi (*Device Shadow*)

---

## 3.2. NLP & Audio Engine

### Speech-to-Text (STT)

* Nhận audio stream từ MQTT
* Nối các mảnh dữ liệu (chunks) va chuyển giọng nói thành văn bản

### LLM Agent

Nhận input từ:

* Voice
* Web UI

Thực hiện:

* Intent detection (CRUD)
* Entity extraction:

  * Thời gian
  * Môn học
  * Quy luật lặp lại
* Chuẩn hóa dữ liệu thành JSON
* Validate bằng Pydantic

---

## 3.3. Data Aggregator (Crawler Services)

Các script crawler chạy nền để thu thập dữ liệu từ:

* HUST SIS
* Website trung tâm tiếng Anh
* Các nguồn lịch học khác

Công nghệ có thể sử dụng:

* Selenium
* BeautifulSoup

### Quy tắc ưu tiên dữ liệu

Trong trường hợp dữ liệu từ Voice Command và Crawler xung đột:

* Hệ thống ưu tiên dữ liệu từ Crawler.
* Thiết kế theo hướng thừa dữ liệu còn hơn thiếu dữ liệu

---

## 3.4. Task Scheduler (APScheduler)

Scheduler chạy định kỳ nền.

### Nhiệm vụ

* Quét Database
* Trích xuất lịch 1 - 2 ngày tiếp theo
* Đóng gói JSON
* Publish xuống topic MQTT của ESP32
* Đồng bộ dữ liệu xuống LittleFS
* Hỗ trợ MQTT v5 Message Expiry: Khi gửi gói lịch trình, Server đính kèm thuộc tính Message Expiry Interval (ví dụ: 3600 giây). Nếu ESP32 offline vượt quá thời gian này, Broker tự động hủy bản tin, ngăn chặn tình trạng thiết bị báo thức dồn dập các lịch cũ khi có mạng trở lại.
* Lắng nghe phản hồi tác vụ Offline (Snooze, Stop) của người dùng từ Edge phát lên để cập nhật lại cơ sở dữ liệu tổng.
### Xử lý phản hồi từ Edge

Nhận lệnh:

* Snooze
* Stop

Sau đó cập nhật lại Database.

---

# 4. Lớp Data & Storage (Database)

Lưu trữ dữ liệu vĩnh viễn (*Persistent Storage*).

## Database Engine

### Development

* SQLite

### Production

* PostgreSQL
---


# 5. Lớp Frontend (Web Dashboard)

Sử dụng:

* AdminLTE
* Tabler

---

## 5.1. Realtime Monitor

Frontend kết nối trực tiếp tới Broker bằng WebSocket.

Mục đích:

* Hiển thị trạng thái thiết bị realtime
* Theo dõi Mic/Speaker
* Theo dõi Online/Offline state

---

## 5.2. Schedule Dashboard

Frontend giao tiếp với FastAPI thông qua REST API.

### Chức năng
* Hiển thị, Thêm, Sửa, Xóa lịch học.
* **Đồng bộ thời gian thực (Interrupt Trigger):** Bất kỳ hành động thay đổi lịch nào từ Web UI đều sẽ lập tức trigger Backend đẩy bản tin lệnh `Cmd_Sync` [QoS 2] ép xuống ESP32. Nếu thiết bị đang bận (thu/phát âm thanh), tín hiệu này sẽ sinh ngắt (Interrupt) để ưu tiên ghi Flash file lịch mới ngay lập tức, giải quyết triệt để vấn đề Race Condition.

Có thể tích hợp:

* FullCalendar

---

# 6. Tóm tắt luồng dữ liệu

```text
ESP32 boot
    ↓
Gửi cấu hình phần cứng lên Server
    ↓
Server ghi nhận trạng thái thiết bị
    ↓
Server tính toán lịch 48h tới
    ↓
Publish JSON xuống ESP32
    ↓
ESP32 lưu vào LittleFS
    ↓
Đến giờ → ESP32 phát báo thức
    ↓
Người dùng nói "Snooze"
    ↓
ESP32 ghi Flash cập nhật lịch cục bộ (Write-Ahead Logging)
    ↓
ESP32 publish bản tin Event_Update [QoS 1] lên Server
    ↓
Server cập nhật Database (Background task)
```

---

# 7. Cấu trúc Thư mục Dự án

```text
IoT-project/                     # Thư mục gốc dự án
│
├── .gitignore                   
├── README.md                    
├── MASTER_DOCS.md               # Tài liệu đặc tả kiến trúc (Bản đang đọc)
│
├── docs/                        
│   ├── git_workflow.md          
│   ├── mqtt_topic_tree.md       
│   ├── database_schema.png      
│   └── hardware_wiring.pdf      
│
├── esp/                         # KHU VỰC EDGE (PlatformIO + ESP-IDF)
│   ├── platformio.ini           
│   ├── partitions_16MB.csv      
│   ├── sdkconfig.defaults       
│   ├── data/                    
│   ├── include/                 
│   │   ├── config.h             
│   │   ├── mqtt_handler.h       
│   │   ├── audio_i2s.h          
│   │   ├── wake_word.h          
│   │   ├── local_storage.h      # Đọc/ghi file JSON lịch trình vào LittleFS
│   │   ├── device_shadow.h      # Thu thập trạng thái ngoại vi
│   │   └── telemetry.h          # Khai báo đọc RAM, RSSI và thông số Mic (Audio Heard)
│   │   ├── time_core.h          # Đồng bộ NTP, quản lý RTC, sinh UNIX Timestamp
│   │   └── peripherals.h        # Quản lí ngoại vi (nếu cần)
│   │
│   └── src/                     
│       ├── CMakeLists.txt       
│       ├── main.cpp             
│       ├── mqtt_handler.cpp     
│       ├── audio_i2s.cpp        
│       ├── wake_word.cpp        
│       ├── local_storage.cpp    # Quản lý lịch cục bộ, kích hoạt chuông offline
│       ├── device_shadow.cpp    # Bắn trạng thái phần cứng lên Server
│       └── telemetry.cpp        # Định kỳ đóng gói tài nguyên hệ thống + chỉ số mic gửi lên
│       ├── time_core.cpp        # Chạy task đồng bộ giờ ngầm, giữ nhịp thời gian
│       └── peripherals.cpp      # Driver cấp thấp (VD: bật PWM cho còi, nháy LED RGB)
│
└── server/                      # KHU VỰC SERVER (Broker + API + Web)
    ├── infrastructure/          
    │   ├── docker-compose.yml   
    │   └── mosquitto/
    │       ├── config/mosquitto.conf 
    │       ├── data/            
    │       └── log/             
    │
    ├── backend/                 # API Server (FastAPI)
    │   ├── .env                 
    │   ├── requirements.txt     
    │   ├── main.py              
    │   ├── core/                      
    │   │   ├── config.py        
    │   │   ├── mqtt_client.py   # Bắt sự kiện LWT, thiết lập cấu hình MQTT v5
    │   │   └── scheduler.py     # Quét lịch, nén và tính expiry interval đẩy xuống
    │   ├── api/                 
    │   │   ├── device_routes.py 
    │   │   └── schedule_routes.py
    │   ├── services/            
    │   │   ├── audio_engine.py  # Xử lý luồng stream âm thanh, kết nối STT/TTS
    │   │   ├── llm_agent.py     # Gọi LLM, bóc tách thực thể sang JSON qua Pydantic
    │   │   ├── device_manager.py# Xử lý dữ liệu Shadow & Nhật ký Telemetry
    │   │   └── crawlers/        
    │   │       ├── hust_sis.py  
    │   │       └── english_center.py 
    │   ├── models/              
    │   │   ├── db_models.py     # Định nghĩa các bảng Database (Schedules, Devices, Telemetry_Logs)
    │   │   └── schemas.py       # Pydantic Schemas để validate dữ liệu từ Web và từ LLM Agent
    │   └── database/
    │       └── session.py       
    │
    └── frontend/                # GIAO DIỆN WEB TĨNH (AdminLTE / Tabler)
        ├── index.html           # Màn hình Dashboard theo dõi tổng quan
        ├── devices.html         # Quản lý thiết bị ngoại vi và xem biểu đồ Telemetry
        ├── calendar.html        # Khung đồ thị thời gian biểu FullCalendar
        └── assets/
            ├── css/style.css    
            └── js/
                ├── app.js       
                └── mqtt_ws.js   # Đổ dữ liệu realtime từ cổng 9001 lên màn hình giám sát
```

# 9. Kế hoạch Phát triển mở rộng - Phase 2 (Optional)
Các hạng mục bảo mật và quản lý nâng cao sẽ được cô lập và triển khai ở giai đoạn cuối cùng khi toàn bộ hệ thống lõi đã hoạt động ổn định:

## 9.1. Bảo mật Lớp Truyền tải TLS/SSL
Thay thế cổng kết nối TCP thuần 1883 bằng cổng bảo mật mã hóa Port 8883. Tự sinh chứng chỉ mã hóa khóa công khai (Self-signed Certificate), nạp chứng chỉ CA vào phân vùng dữ liệu của ESP32 để mã hóa toàn bộ dữ liệu truyền tải trên đường truyền, ngăn chặn tuyệt đối các cuộc tấn công bắt gói tin nghe lén thông tin cá nhân.

## 9.2. Xác thực Động (Dynamic Security Webhook)
Loại bỏ việc sử dụng tài khoản/mật khẩu tĩnh lưu trên file cấu hình của Mosquitto. Cấu hình kiến trúc để khi ESP32 gửi yêu cầu kết nối (CONNECT), Mosquitto Broker sẽ kích hoạt một lệnh gọi ngược (Webhook) sang API nội bộ của FastAPI để kiểm tra thông tin địa chỉ MAC và mật khẩu băm trong Database. Chỉ cho phép các thiết bị hợp lệ gia nhập mạng lưới.

## 9.3. Quản lý cập nhật Phần mềm từ xa (Firmware OTA via MQTT)
Cấu trúc thư mục: Bổ sung module services/ota_manager.py ở Backend.

Luồng hoạt động: Khi có phiên bản nâng cấp code, biên dịch file .bin mới và upload lên Server. Server đẩy một bản tin chứa thông tin phiên bản và đường dẫn bảo mật (URL HTTPS) xuống topic iot_schedule/{device_id}/ota (QoS 1, Retain True). ESP32 nhận tin, tự khởi động tác vụ nền esp_https_ota để tải ngầm firmware, kiểm tra tính toàn vẹn (Checksum), tự động chuyển đổi phân vùng khởi động (Partition Boot Switch) và reset chạy bản mới.
# 10. Sơ đồ Cây Giao tiếp
```mermaid
flowchart LR

    A[ESP32 Edge Device]

    A --> B[MQTT Handler]
    A --> C[Wake Word]
    A --> D[Local Storage]
    A --> E[Telemetry]

    B --> F[(Mosquitto Broker)]

    F --> G[FastAPI Backend]

    G --> H[Scheduler]
    G --> I[LLM Agent]
    G --> J[Audio Engine]
    G --> K[Device Manager]

    G --> L[(Database)]

    M[Frontend Dashboard]
    M --> G
```
```mermaid
flowchart TD
    subgraph "THẾ GIỚI BÊN NGOÀI"
        User[Người dùng\nTrình duyệt Web]
        External[Nguồn dữ liệu\nHUST SIS, Web Trung tâm]
        AI[AI Provider\nOpenAI / Gemini / STT Engine]
    end

    subgraph "HỆ THỐNG TRUNG TÂM (SERVER)"
        Backend[Backend\nFastAPI Core]
        Broker[Mosquitto Broker\nDocker Container]
    end

    subgraph "THIẾT BỊ ĐẦU CUỐI (EDGE - ESP32)"
        ESP32[ESP32]
        Hardware[Phần cứng Ngoại vi\nMic, Loa, LED, Nút bấm]
        EdgeAI[Xử lý Cục bộ\nESP-SR + LittleFS]
    end

    %% Kết nối
    User <-->|"HTTP/REST + WebSocket"| Backend
    External -->|"HTTPS"| Backend
    AI <-->|"API / gRPC"| Backend
    
    Backend <-->|"MQTT (TCP + WebSocket)"| Broker
    ESP32 <-->|"MQTT/TCP\nPort 1883"| Broker
    
    ESP32 --- Hardware
    ESP32 --- EdgeAI
```

