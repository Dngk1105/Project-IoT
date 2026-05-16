# Hướng Dẫn Cài Đặt Môi Trường & Chạy Test Kết Nối ESP32

Tài liệu này hướng dẫn các thành viên trong team cách khởi chạy toàn bộ hệ thống Server (Broker, Backend, Web UI) ở local để có thể giao tiếp và test thực tế với mạch ESP32.

## 🛠 Yêu cầu hệ thống
Trước khi bắt đầu, máy tính của bạn cần cài đặt sẵn:
1. **Docker Desktop** (Để chạy MQTT Broker)
2. **Python 3.8+** (Để chạy API Backend)
3. **Trình duyệt Web** (Chrome/Edge - Để mở Dashboard)

---

## Bước 1: Khởi động MQTT Broker (Mosquitto)
Broker đóng vai trò trung tâm trung chuyển tin nhắn giữa ESP32, Backend và Web UI.

1. Mở Terminal / Command Prompt.
2. Di chuyển vào thư mục hạ tầng:
   ```bash
   cd server/infrastructure
   ```
3. Khởi chạy Docker Compose:
   ```bash
   docker-compose up -d
   ```
4. Kiểm tra xem container đã chạy chưa bằng lệnh `docker ps`. 
   *Lưu ý: Broker sẽ mở 2 cổng mạng: `1883` (Giao thức MQTT TCP cho ESP32/Backend) và `9001` (WebSockets cho Web UI).*

---

## Bước 2: Chạy Backend Server (FastAPI)
Backend xử lý logic lưu trữ và giao tiếp chuyên sâu.

1. Mở một Terminal mới, di chuyển vào thư mục backend:
   ```bash
   cd server/backend
   ```
2. Tạo và kích hoạt môi trường ảo (Khuyên dùng):
   ```bash
   python -m venv venv
   
   # Kích hoạt trên Windows:
   venv\Scripts\activate
   
   # Kích hoạt trên macOS/Linux:
   source venv/bin/activate
   ```
3. Cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   ```
4. Khởi chạy server:
   ```bash
   uvicorn main:app --reload
   ```
   *Server sẽ chạy tại `http://127.0.0.1:8000`. Bạn có thể truy cập `http://127.0.0.1:8000/docs` để xem và test các API qua Swagger UI.*

---

## Bước 3: Mở Web Dashboard giám sát
Web Dashboard dùng để bắt log real-time và gửi lệnh xuống ESP32.

1. Mở File Explorer của hệ điều hành.
2. Điều hướng tới đường dẫn thư mục frontend: `server/frontend/html/`
3. Nhấp đúp chuột vào file `index.html` để mở trực tiếp bằng trình duyệt Chrome hoặc Edge (không cần chạy qua Live Server).
4. Kiểm tra trạng thái góc trên bên trái màn hình. Nếu báo **"Thành công" (Màu xanh lá)** nghĩa là Web đã kết nối tới Broker thành công qua WebSockets.

---

## Bước 4: Hướng dẫn Test kết nối với ESP32
Khi 3 thành phần trên đã chạy lên xanh mượt, bạn đã có một môi trường giả lập hoàn chỉnh:

- **Test luồng dữ liệu (Không cần ESP32):** Ở Web Dashboard, sử dụng khung "Test Publish", nhập Topic bất kỳ (Vd: `hust_iot/test`) và Payload `{"msg": "hello"}`, sau đó bấm Publish. Khung Console sẽ lập tức nảy log. Đồng thời Terminal của Backend cũng sẽ in ra log xác nhận đã nhận được.
- **Test kết nối thật với mạch ESP32:** Nạp code vào mạch ESP32. Đảm bảo config MQTT trỏ về **địa chỉ IPv4 LAN** của máy tính đang chạy Docker (Ví dụ: `192.168.1.x`, port `1883`). Mọi dữ liệu telemetry hay trạng thái LWT (Online/Offline) ESP32 đẩy lên sẽ lập tức hiện trên Dashboard Web!
