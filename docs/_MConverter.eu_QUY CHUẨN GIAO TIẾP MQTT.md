# QUY CHUẨN GIAO TIẾP MQTT (MQTT CONVENTION)

**Mục đích:** Tài liệu này quy định các tiêu chuẩn bắt buộc khi phát triển, thiết kế và review code liên quan đến giao thức MQTT trên cả Edge (ESP32) và Server (FastAPI). Mọi luồng giao tiếp Pub/Sub mới đều phải tuân thủ nghiêm ngặt các quy tắc dưới đây.

## 1. Tiêu chuẩn Kết nối & Khởi tạo (Connection Standards) {#tiêu-chuẩn-kết-nối-khởi-tạo-connection-standards}

- **Phiên bản giao thức:** Bắt buộc sử dụng **MQTT v5.0** trên cả Server và ESP32 để tận dụng các tính năng User Properties và Reason Codes.

- **Client ID:** Phải là duy nhất (Unique) trên toàn hệ thống để tránh tình trạng \"đá\" session (kick-out) lẫn nhau.

  - *Edge:* Khởi tạo theo cú pháp: esp32\_\<mac_address\> (Ví dụ: esp32_A1B2C3D4E5F6).

  - *Server:* Khởi tạo theo cú pháp: server_backend\_\<uuid\>.

- **Keep-Alive:** Set mặc định là 60 giây. ESP32 phải duy trì Pingreq để Broker không đánh dấu là Offline.

## 2. Quy tắc Đặt tên Topic (Topic Naming Convention) {#quy-tắc-đặt-tên-topic-topic-naming-convention}

Tuyệt đối không dùng hardcode lung tung. Cấu trúc Topic phải tuân theo định dạng phân cấp (Hierarchical) chuẩn:

device/\<device_id\>/\<category\>/\<action\>

- **\<device_id\>:** Bắt buộc là MAC Address của thiết bị (viết liền, in thường, không có dấu :). Tránh dùng các tên chung chung như phong_khach.

- **\<category\>:** Nhóm chức năng logic. Các nhóm hợp lệ:

  - shadow: Trạng thái phần cứng hiện tại (LED, Mic, Buzzer).

  - telemetry: Dữ liệu sức khỏe hệ thống (RAM, RSSI, Uptime).

  - events: Các sự kiện bất đồng bộ phát sinh (Báo thức kêu, Nhận lệnh giọng nói, Snooze).

  - commands: Lệnh từ Server yêu cầu ESP32 thực thi (Ví dụ: đổi màu LED, bật còi).

  - status: Trạng thái kết nối mạng (LWT).

## 3. Đặc tả Dữ liệu (Payload Specification) {#đặc-tả-dữ-liệu-payload-specification}

- **Định dạng:** 100% Payload phải là chuỗi **JSON** hợp lệ, mã hóa **UTF-8**. KHÔNG dùng chuỗi thuần (plain-text) hoặc nhị phân thô, ngoại trừ luồng audio (nếu có).

- **Kích thước:** Giữ Payload nhỏ nhất có thể (Lý tưởng \< 512 Bytes cho các bản tin thường xuyên) để tối ưu Heap cho ESP32.

- **Định dạng Thời gian:** Mọi mốc thời gian trong Payload **bắt buộc** dùng **UNIX Timestamp (Số nguyên - Integer)**. KHÔNG dùng chuỗi định dạng ISO 8601 (\"2026-05-21T\... \") để tránh ESP32 phải xử lý string tốn tài nguyên.

**Mẫu Payload chuẩn (Telemetry):**

```JSON

{

  "timestamp": 1716598800,

  "data\": {

    "free_heap_kb": 128,

    "rssi": -65
  }
}
```

## 4. Quản lý Vòng đời (Device Lifecycle & LWT) {#quản-lý-vòng-đời-device-lifecycle-lwt}

Để Server biết ESP32 bị sập nguồn hay rớt mạng, luồng LWT (Last Will and Testament) là **bắt buộc**.

- **Birth Message:** Ngay khi ESP32 connect thành công vào Broker, phải Publish một bản tin báo thức dậy.

  - Topic: device/\<device_id\>/status

  - Payload: {\"status\": \"online\", \"timestamp\": \<unix_time\>}

  - QoS: 1

  - Retain: **True**

- **Last Will (LWT):** Lúc cấu hình MQTT Client trên ESP32, phải đăng ký bản tin di chúc.

  - Topic: device/\<device_id\>/status

  - Payload: {\"status\": \"offline\", \"reason\": \"connection_lost\"}

  - QoS: 1

  - Retain: **True**

## 5. Quy tắc sử dụng QoS & Retain Flag {#quy-tắc-sử-dụng-qos-retain-flag}

Cấm sử dụng tùy tiện QoS và Retain, phải tuân theo bảng quy định sau:

| **Loại Dữ Liệu**        | **Topic tham khảo** | **QoS Cần Thiết** | **Retain** | **Lý do / Hoàn cảnh sử dụng**                                                                                                                       |
|-------------------------|---------------------|-------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Telemetry**           | \.../telemetry      | **QoS 0**         | False      | Dữ liệu cập nhật liên tục, rớt 1-2 gói không ảnh hưởng hệ thống, ưu tiên tốc độ.                                                                    |
| **Shadow (Trạng thái)** | \.../shadow/update  | **QoS 1**         | **True**   | Server hoặc App cần đọc được trạng thái *mới nhất* ngay khi vừa kết nối, không phải chờ tới đợt publish tiếp theo.                                  |
| **Lệnh điều khiển**     | \.../commands/#     | **QoS 1**         | False      | Bắt buộc thiết bị phải nhận được lệnh (đổi màu đèn, kêu còi). Không Retain để tránh việc thiết bị vừa khởi động lại bị nhận lại lệnh cũ đã hết hạn. |
| **Sự kiện quan trọng**  | \.../events/snooze  | **QoS 1**         | False      | Server bắt buộc phải ghi nhận việc người dùng xin báo lại, tránh sai lệch Database.                                                                 |

## 6. Tiêu chuẩn Xử lý Ngoại lệ (Offline Queueing) {#tiêu-chuẩn-xử-lý-ngoại-lệ-offline-queueing}

Khi ESP32 ở trong trạng thái mất kết nối WiFi nhưng người dùng vẫn tương tác (Ví dụ: ra lệnh \"Snooze\" bằng giọng nói):

1.  Tuyệt đối không dùng các hàm publish() dạng blocking làm treo hệ thống.

2.  Bắt buộc serialize dữ liệu đẩy vào hàng đợi nhị phân trong bộ nhớ Flash (LittleFS) (tham khảo file local_storage.cpp).

3.  Khi có mạng trở lại, phải gửi bù (sync) với cờ **QoS 1**. Chỉ được xóa file nhị phân khỏi LittleFS khi Broker trả về gói tin PUBACK.
