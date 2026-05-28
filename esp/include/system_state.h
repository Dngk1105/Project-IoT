#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

/*
* Chương trình cần các biến trạng thái để quản lí esp, nhận biết tác vụ đang 
thực hiện yêu cầu gì và tình trạng kết nối
* Gôm 2 loại trạng thái: 
    + Trạng thái hệ thống: Tình trạng kết nối của thiết bị
    + Trạng thái ứng dụng: Tác vụ ứng dụng đang thực hiện
*/

typedef enum{
    SYS_INIT,   //Khởi động
    SYS_OFFLINE, // Chạy local
    SYS_WIFI_OK, // Có wifi nhưng chưa kết nối được broker
    SYS_MQTT_OK, // Kết nối broker thành công 
    // Không kiểm tra kết nối tới server (hỏng bản chất mqtt), tất cả các thiết bị nên chỉ nói chuyện thông qua broker thôi
} sys_state_t;

typedef enum{
    STATE_IDLE, // Rảnh rỗi, chờ đến giờ báo thức hoặc chờ Wake Word
    STATE_ALARMING, // Đang đổ chuông báo thức bằng file âm thanh Local
    STATE_LISTENING, // Lắng nghe yêu cầu/phản hồi từ người dùng
    STATE_STREAM_UP, // Đẩy luồng audio
    STATE_WAIT_SERVER, // Đợi phản hồi từ server 
    STATE_STREAM_DOWN, // Phát âm thanh từ server trả xuống 
    STATE_SYNCING,
} app_state_t;

// Khoi tao mutex
void state_manager_init(void);

//Hàm quản lí trạng thái, Chi co mot luong duoc su dung
void set_sys_state(sys_state_t new_state);

// Hàm yêu cầu chuyển đổi trạng thái tác vụ (Kiểm tra điều kiện trước khi chuyển)
bool request_app_state(app_state_t new_state);

// Cac ham getter
app_state_t get_app_state(void);
sys_state_t get_sys_state(void);

bool is_system_idle(void);
void force_app_state_idle(void);

const char* sys_state_to_str(sys_state_t state);
const char* app_state_to_str(app_state_t state);

#ifdef __cplusplus
}
#endif