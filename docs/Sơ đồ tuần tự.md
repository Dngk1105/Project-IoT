#Đồng bộ lịch

Central Server (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge - LittleFS)
Central Server (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge - LittleFS)
Kịch bản: Server ép cấu hình lịch mới xuống Thiết bị (Web thay đổi hoặc Định kỳ)
Tầng Mạng Xong. Kích hoạt xử lý Local Storage
alt
[Trường hợp 1: Ghi Flash THÀNH CÔNG]
[Trường hợp 2: Ghi Flash THẤT BẠI (Lỗi bad sector / Full bộ nhớ)]
Khởi tạo phiên đồng bộ (ID: sync_789)
1
Publish: Cmd_Sync [QoS 2]
Topic: iot_schedule/{device_id}/commands/sync_schedule
Properties: [Response_Topic="iot_schedule/{device_id}/ack/sync_response", Corr_Data="sync_789", Message_Expiry=3600]
2
Forward Bản tin Cmd_Sync [QoS 2]
3
PUBCOMP (Xác nhận bắt tay tầng mạng thành công)
4
PUBCOMP
5
Thực thi hàm ghi file cục bộ: f_write("/schedule.json")
6
Publish: Ứng dụng ACK [QoS 1]
Topic: iot_schedule/{device_id}/ack/sync_response
Properties: [Corr_Data="sync_789"]
Payload: {"status": "SUCCESS", "timestamp": 1779422760}
7
Forward Bản tin Ứng dụng ACK
8
Đối khớp Corr_Data "sync_789" -> Xác nhận Database OK
9
Stream Audio TTS [QoS 0]: "Đã đồng bộ lịch thành công"
10
Publish: Ứng dụng ACK [QoS 1]
Topic: iot_schedule/{device_id}/ack/sync_response
Properties: [Corr_Data="sync_789"]
Payload: {"status": "FLASH_ERR", "timestamp": 1779422760}
11
Forward Bản tin Ứng dụng ACK
12
Đối khớp Corr_Data -> Ghi nhật ký lỗi phần cứng hệ thống
13
Stream Audio TTS [QoS 0]: "Cảnh báo lỗi bộ nhớ cục bộ"
14




#Luồng hoạt động tổng thể

External API (HUST SIS / Weather)
Central Server (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge Device)
External API (HUST SIS / Weather)
Central Server (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge Device)
--- PHẦN 1: KHỞI TẠO TƯƠNG TÁC (TRIGGER) ---
alt
[ESP-SR nhận diện được từ khóa Offline ("OK" / "Snooze")]
[ESP không hiểu lệnh (Ồn nhiễu / Câu lệnh phức tạp)]
alt
[Kịch bản A: Đến giờ báo thức (Xử lý Offline tại Edge)]
[Kịch bản B: Người dùng chủ động tương tác bằng Wake Word]
--- PHẦN 2: XỬ LÝ TRÊN CLOUD & GIÁM SÁT WATCHDOG ---
--- PIPELINE SYNC & APP-ACK (MQTT v5 Properties) ---
alt
[Ghi Flash Thành Công]
[Ghi Flash Thất Bại]
alt
[Ngoại lệ STT: Không nhận diện được giọng nói]
[Ngoại lệ API: Lỗi kết nối nguồn dữ liệu bên ngoài]
[Xử lý Intent thành công: Yêu cầu cập nhật lịch học (CRUD)]
--- PHẦN 3: PHẢN HỒI ÂM THANH CHO NGƯỜI DÙNG ---
opt
[Khi ở Trạng thái STATE_STREAM_UP]
--- PHẦN 4: NGẮT HỆ THỐNG TOÀN CỤC (GLOBAL INTERRUPTS) ---
par
[Kịch bản Rủi ro mất mạng: Ngắt Watchdog kích nổ]
[Kịch bản Race Condition: Can thiệp ngắt từ phía Web UI]
Người Dùng
Kích hoạt loa I2S phát chuông: "Đã đến giờ lịch học, huynh xác nhận chứ?"
1
Chuyển trạng thái sang STATE_LISTENING
2
Trả lời bằng giọng nói
3
Ghi nhận nhật ký Flash trước (Write-Ahead Logging vào LittleFS)
4
Publish: Event_Update [QoS 1]
Topic: iot_schedule/{device_id}/events/snooze
Payload: {"action": "snooze", "timestamp": 1779422760}
5
Forward Event_Update -> Cập nhật Database
6
Chuyển về trạng thái STATE_IDLE
7
Thay đổi trạng thái: STATE_STREAM_UP (Fallback lên Cloud)
8
"Hey System" -> "Hủy lịch học chiều nay giúp ta"
9
Thay đổi trạng thái: STATE_STREAM_UP
10
Kích hoạt Voice Watchdog Timer (Giới hạn 5s)
11
Stream Audio Chunks [QoS 0]
Topic: iot_schedule/{device_id}/audio/stream_up (Kèm cờ End_of_Speech)
12
Forward luồng Audio
13
Thực thi Pipeline: STT -> LLM Agent -> Trích xuất intent dạng JSON via Pydantic
14
Chuẩn bị luồng phản hồi: "Xin lỗi, huynh nhắc lại được không?"
15
Request Data
16
Gateway Timeout (504)
17
Chuẩn bị luồng phản hồi: "Kết nối máy chủ nhà trường đang bảo trì"
18
Thực thi cập nhật cơ sở dữ liệu gốc (PostgreSQL)
19
Publish: Cmd_Sync [QoS 2]
Topic: iot_schedule/{device_id}/commands/sync_schedule
Properties: [Response_Topic=".../ack/sync_response", Corr_Data="sync_888"]
20
Forward Cmd_Sync [QoS 2]
21
Thực thi ghi bộ nhớ Flash LittleFS
22
Publish: Ack [QoS 1]
Topic: iot_schedule/{device_id}/ack/sync_response
Properties: [Corr_Data="sync_888"]
Payload: {"status": "SUCCESS"}
23
Forward Ack -> Xác nhận đóng phiên sync_888
24
Chuẩn bị luồng phản hồi TTS: "Đã cập nhật thời gian biểu mới thành công"
25
Publish: Ack [QoS 1]
Topic: iot_schedule/{device_id}/ack/sync_response
Properties: [Corr_Data="sync_888"]
Payload: {"status": "FLASH_ERR"}
26
Forward Ack -> Ghi cảnh báo lỗi hệ thống phần cứng
27
Chuẩn bị luồng phản hồi TTS: "Gặp sự cố ghi nhớ dữ liệu trên mạch"
28
Stream Audio TTS Chunks [QoS 0]
Topic: iot_schedule/{device_id}/audio/stream_down
29
Forward luồng Audio TTS
30
Giải phóng Voice Watchdog Timer (Xác nhận nhận tín hiệu sống)
31
Phát âm thanh qua mạch I2S & Loa ngoại vi
32
Reset trạng thái về STATE_IDLE
33
Mất kết nối Wi-Fi / Broker chết đứng khi đang stream
34
Watchdog Timer vượt ngưỡng 5s -> Kích nổ ngắt ứng dụng!
35
Ngắt kết nối dở dang, giải phóng bộ đệm ghi âm
36
Kích hoạt bộ nhớ tại chỗ, phát tệp MP3 Local: "Mạng gặp sự cố, hệ thống chuyển sang chế độ ngoại tuyến"
37
Fallback trạng thái: STATE_IDLE / OFFLINE_MODE
38
Tự động phát di chúc: LWT [QoS 1, Retain=True]
Topic: iot_schedule/{device_id}/status
Payload: {"status": "offline", "reason": "connection_lost"}
39
Đánh dấu trạng thái thiết bị ngoại tuyến trong Database
40
Người dùng thay đổi lịch đột xuất trên Web Dashboard
41
Publish Lệnh ép đồng bộ khẩn cấp: Cmd_Sync [QoS 2]
Topic: iot_schedule/{device_id}/commands/sync_schedule
42
Forward Cmd_Sync [QoS 2]
43
Kích hoạt Ngắt Phần Mềm (Software Interrupt): Lập tức dừng mọi tác vụ thu/phát âm thanh dở dang!
44
Ưu tiên tài nguyên gọi hàm ghi file LittleFS cập nhật cấu hình lịch mới từ Server
45
Publish: Ack [QoS 1] báo cáo hoàn thành ngắt lên kênh Response_Topic
46
Khởi động lại vòng lặp trạng thái về STATE_IDLE
47
Người Dùng




Luồng Giám sát sức khỏe thiết bị (Telemetry & Device Shadow)
Device Manager (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge Device)
Device Manager (FastAPI Core)
Mosquitto Broker (v5.0)
ESP32-S3 (Edge Device)
Định kỳ chạy tác vụ ngầm FreeRTOS (Chu kỳ 5 phút/lần)
alt
[Trường hợp phát hiện bất thường (Cạn RAM hệ thống hoặc Micro không nhận tín hiệu)]
[Hệ thống hoạt động bình thường]
Đọc dung lượng bộ nhớ khả dụng (Free Heap Size)
1
Đo thông số cường độ sóng mạng (Wi-Fi RSSI)
2
Trích xuất dữ liệu chẩn đoán Mic I2S (last_audio_heard_ms, audio_peak_db)
3
Publish: Telemetry_Log [QoS 0]
Topic: iot_schedule/{device_id}/telemetry/metrics
Payload: JSON {free_heap_kb, rssi, uptime_s, audio_metrics}
4
Forward Telemetry_Log
5
Thực thi kiểm tra cấu trúc dữ liệu qua Pydantic Schema
6
Kích hoạt cờ Warning_Flag nội bộ trong Database
7
Publish WebSocket [Port 9001] đẩy dữ liệu Realtime lên Frontend
8
Web UI lập tức hiển thị cảnh báo đỏ trên trang quản lý thiết bị ngoại vi
9
Ghi nhật ký chuỗi thời gian (Time-series Log) phục vụ vẽ biểu đồ đồ thị
10




