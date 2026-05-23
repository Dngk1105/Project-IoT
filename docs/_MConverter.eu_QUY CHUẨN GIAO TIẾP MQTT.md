# QUY CHUẨN GIAO TIẾP MQTT (MQTT CONVENTION)

**Mục đích:** Tài liệu này quy định các tiêu chuẩn bắt buộc khi phát triển, thiết kế và review code liên quan đến giao thức MQTT trên cả Edge (ESP32) và Server (FastAPI). Mọi luồng giao tiếp Pub/Sub mới đều phải tuân thủ nghiêm ngặt các quy tắc dưới đây nhằm đảm bảo tính toàn vẹn dữ liệu và tối ưu hiệu năng hệ thống IoT Schedule.

## 1. Tiêu chuẩn Kết nối & Khởi tạo (Connection Standards)

- **Phiên bản giao thức:** Bắt buộc sử dụng **MQTT v5.0** trên cả Server và ESP32 để khai thác các thuộc tính nâng cao gồm *User Properties, Response Topic, Correlation Data, Message Expiry* và *Reason Codes*.
- **Client ID:** Phải là duy nhất (Unique) trên toàn hệ thống để tránh tình trạng chiếm quyền điều khiển và ngắt kết nối chéo (*session kick-out*).
  - *Edge (ESP32):* Khởi tạo theo cú pháp: `esp32_<mac_address>` (Ví dụ: `esp32_a1b2c3d4e5f6` - viết liền, in thường, không dấu `:`).
  - *Server:* Khởi tạo theo cú pháp: `server_backend_<uuid>`.
- **Duy trì phiên kết nối bền vững (Persistent Session):**
  - Cấu hình MQTT Client trên ESP32 với cờ `Clean Start = False` (đối với v5) và thiết lập một giá trị `Session Expiry Interval` dài (ví dụ: `7200` giây).
  - Mục tiêu: Khi xảy ra rớt mạng ngắn hạn, Mosquitto Broker tự động lưu lại hàng đợi các bản tin điều khiển quan trọng (QoS 1/QoS 2) và đẩy bù ngay khi ESP32 kết nối lại mà không cần subscribe lại từ đầu.
- **Keep-Alive:** Thiết lập mặc định là **60 giây**. Tác vụ nền trên FreeRTOS của ESP32 phải đảm bảo gửi gói `PINGREQ` đúng hạn khi đường truyền rảnh để Broker không kích hoạt cờ LWT.

## 2. Quy tắc Đặt tên Topic (Topic Naming Convention)

Tuyệt đối cấm hardcode chuỗi thủ công trong mã nguồn. Cấu trúc hệ thống cây Topic phải tuân theo định dạng phân cấp và định danh thiết bị như sau:

`iot_schedule/<device_id>/<category>/<action_or_sub>`

- **`<device_id>`:** Địa chỉ MAC của ESP32 (viết liền, in thường, ví dụ: `a1b2c3d4e5f6`).
- **`<category>` và `<action_or_sub>`:** Định nghĩa phân lớp chức năng rõ ràng:
  - `status`: Quản lý vòng đời (`online`, `offline` qua LWT).
  - `shadow`: Trạng thái đồng bộ ngoại vi (`led`, `mic`, `buzzer`).
  - `telemetry`: Chỉ số sức khỏe hệ thống (`metrics`).
  - `audio`: Luồng truyền tải dữ liệu âm thanh số (`stream_up`, `stream_down`).
  - `commands`: Lệnh ép từ Server xuống thiết bị (`sync_schedule`, `led_ctrl`, `buzzer_ctrl`).
  - `ack`: Kênh phản hồi ứng dụng từ Edge trả ngược lên Server (`sync_response`).
  - `ota`: Kênh nhận chỉ thị nâng cấp phần mềm từ xa (`firmware_upgrade`).

## 3. Đặc tả Dữ liệu (Payload Specification)

- **Định dạng chuỗi:** **100%** bản tin trạng thái và điều khiển phải là chuỗi **JSON** hợp lệ, mã hóa **UTF-8** và validate qua *Pydantic Schema* ở phía Server.
- **Ngoại lệ Luồng Audio:** Dữ liệu âm thanh thô thu từ Mic I2S (`stream_up`) hoặc luồng phát TTS từ Server (`stream_down`) được truyền tải dưới dạng chuỗi nhị phân thô (*Raw Binary Chunks*) để giảm tối đa overhead.
- **Kích thước gói:** Giữ Payload JSON nhỏ nhất có thể (Lý tưởng `< 512 Bytes` cho các bản tin định kỳ) để tránh phân mảnh bộ nhớ Heap của ESP32.
- **Định dạng Thời gian:** Mọi mốc thời gian bên trong Payload **bắt buộc** sử dụng **UNIX Timestamp (Kiểu số nguyên - Integer)**. Nghiêm cấm sử dụng chuỗi định dạng ISO 8601 (như `"2026-05-22T..."`) để giảm tải tài nguyên phân tích chuỗi (*string parsing*) trên MCU.

### Mẫu Payload Telemetry Chuẩn (Bao gồm Giám sát âm thanh)

```json
{
  "timestamp": 1779422760,
  "data": {
    "free_heap_kb": 128,
    "rssi": -65,
    "uptime_s": 3600,
    "audio_metrics": {
      "last_audio_heard_ms": 1250,
      "audio_peak_db": -12
    }
  }
}
```

## 4. Quản lý Vòng đời (Device Lifecycle & LWT)

Cơ chế giám sát trạng thái sống/chết của thiết bị đầu cuối thông qua bản tin Birth (Khởi sinh) và LWT (Di chúc) cấu hình ở cấp độ kết nối mạng MQTT v5:

### Birth Message (Bản tin Khởi sinh)

Phát đi ngay khi kết nối thành công tới Broker.

- Topic: `iot_schedule/<device_id>/status`
- Payload: `{"status": "online", "timestamp": <unix_timestamp>}`
- QoS: `1`
- Retain: `True`

### Last Will and Testament (LWT - Bản tin Di chúc)

Đăng ký trực tiếp với Broker trong gói tin CONNECT. Kích hoạt tự động bởi Broker khi ESP32 đột ngột sập nguồn hoặc mất Wi-Fi vượt quá thời gian Keep-Alive.

- Topic: `iot_schedule/<device_id>/status`
- Payload: `{"status": "offline", "reason": "connection_lost", "timestamp": <unix_timestamp>}`
- QoS: `1`
- Retain: `True`

## 5. Quy tắc Sử dụng QoS & Retain Flag

Việc lựa chọn mức chất lượng dịch vụ (QoS) và cờ lưu giữ (Retain) phải tuân thủ nghiêm ngặt bảng ma trận thiết kế dưới đây:

| Loại Dữ Liệu | Topic Tham Khảo | QoS | Retain | Tính năng nâng cao MQTT v5 & Hoàn cảnh sử dụng |
|---|---|---|---|---|
| Audio Stream | `.../audio/stream_up` `.../audio/stream_down` | QoS 0 | False | Ưu tiên tối đa tốc độ truyền stream thời gian thực, giảm độ trễ đầu cuối, chấp nhận rơi rớt gói tin cục bộ. |
| Telemetry | `.../telemetry/metrics` | QoS 0 | False | Gửi định kỳ (5 phút/lần). Dữ liệu cập nhật liên tục, không cần bảo đảm truyền phát để tiết kiệm tài nguyên mạng. |
| Device Shadow | `.../shadow/led` `.../shadow/mic` | QoS 1 | True | Trạng thái phần cứng ngoại vi. Cần bật Retain=True để khi Frontend Dashboard Web hoặc Server kết nối vào sẽ đọc được cấu hình mới nhất lập tức. |
| Sự kiện ứng dụng | `.../events/snooze` `.../events/stop` | QoS 1 | False | Các hành động phản hồi offline từ Edge phát lên Server. Server bắt buộc phải nhận được (At least once) để cập nhật đồng bộ lại Database lõi. |
| Đồng bộ lịch | `.../commands/sync_schedule` | QoS 2 | False | `Message Expiry Interval = 3600s`: Sử dụng cơ chế bắt tay QoS 2 để đảm bảo dữ liệu ghi lịch xuống Flash đúng một lần duy nhất (Exactly once), tránh lặp gói. Nếu thiết bị offline quá 1 tiếng, Broker tự động hủy gói để tránh báo thức dồn dập lệnh cũ khi có mạng lại. Đính kèm thuộc tính `Response Topic` và `Correlation Data`. |
| Xác nhận (ACK) | `.../ack/sync_response` | QoS 1 | False | Trả ngược từ ESP32 lên Server, đính kèm chính xác mã định danh `Correlation Data` nhận được để đóng pipeline Request-Response tầng ứng dụng. |

## 6. Tiêu chuẩn Ứng dụng: Giao tiếp Request-Response & Xử lý Ngoại lệ

### 6.1. Pipeline Request-Response Tầng Ứng dụng (Đồng bộ lịch)

Khi Server thực hiện thay đổi lịch học (Định kỳ hoặc do có thao tác trực tiếp từ Web Dashboard tạo ra can thiệp ngắt - Race Condition Mitigation):

1. Server gửi gói tin chứa JSON lịch trình xuống topic `.../commands/sync_schedule` với QoS 2.
2. Trong gói tin, Server đính kèm thuộc tính MQTT v5:
   - `Response Topic`: Địa chỉ mong muốn nhận phản hồi (Ví dụ: `iot_schedule/a1b2c3d4e5f6/ack/sync_response`).
   - `Correlation Data`: Mã ID duy nhất mã hóa phiên đồng bộ (Ví dụ: `sync_789`).
3. ESP32 nhận tin, bóc tách JSON và thực hiện gọi hàm ứng dụng ghi xuống Flash (`f_write("/schedule.json")` thông qua module `local_storage.cpp`).
4. ESP32 publish bản tin phản hồi tầng ứng dụng lên `Response Topic` thu được với QoS 1, payload mang thông tin trạng thái (`{"status": "SUCCESS"}` hoặc `{"status": "FLASH_ERR"}`) kèm theo đúng mã `Correlation Data` (`sync_789`) để Server đối khớp trạng thái Database.

### 6.2. Cơ chế Hàng đợi Ngoại lệ (Offline Queueing) & Voice Watchdog

#### Tương tác âm thanh trực tuyến (`STATE_STREAM_UP`)

Khi thiết bị thu âm và stream dữ liệu lên Server, ESP32 phải chạy một Software Timer Voice Watchdog giới hạn 5 giây. Nếu quá thời gian này mà mạng lỗi (mất kết nối WiFi, Server sập) không có phản hồi TTS về, ngắt Watchdog tự động hủy tác vụ thu phát dở dang, giải phóng bộ đệm ghi âm, phát loa tệp MP3 cảnh báo lỗi mạng cục bộ và đưa thiết bị về trạng thái an toàn `STATE_IDLE`.

#### Hành động tương tác Offline (Ví dụ: Báo thức nổ, bấm nút Snooze/Stop khi mất Wi-Fi)

- Tuyệt đối nghiêm cấm sử dụng các hàm gọi `publish()` cấu hình dạng chặn hệ thống (*Blocking Call*) gây treo luồng chính của FreeRTOS.
- Ứng dụng phải kích hoạt cơ chế ghi nhật ký trước (Write-Ahead Logging), tuần tự hóa dữ liệu tác vụ và đẩy vào hàng đợi lưu trữ trong phân vùng bộ nhớ Flash tĩnh (LittleFS).
- Ngay sau khi kết nối mạng được tái thiết lập thành công (dựa trên trạng thái `IP_EVENT_STA_GOT_IP`), một worker chạy nền sẽ quét vùng đệm LittleFS, thực hiện gửi bù dữ liệu thông qua bản tin `Event_Update` với QoS 1.
- Chỉ khi nhận được gói tin xác nhận mạng `PUBACK` từ phía Broker, ứng dụng mới tiến hành xóa bỏ tệp tin lưu trữ tạm thời ra khỏi LittleFS.
