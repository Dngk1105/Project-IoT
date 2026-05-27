#include "system_state.h"
#include "esp_log.h"
#include "audio_i2s.h"

const char *TAG = "SYSTEM_STATE";

// Lưu trạng thái, dùng mutex để tránh đụng độ cho luồng
static volatile sys_state_t current_sys_state = SYS_INIT;
static volatile app_state_t current_app_state = STATE_IDLE;
static SemaphoreHandle_t state_mutex;

// Khoi tao mutex
void state_manager_init(void){
    state_mutex = xSemaphoreCreateMutex();
}

//Hàm quản lí trạng thái, Chi co mot luong duoc su dung
void set_sys_state(sys_state_t new_state){
    if (xSemaphoreTake(state_mutex, portMAX_DELAY)){
        if (current_sys_state != new_state){
            ESP_LOGI(TAG, "Cap nhat SYSTEM_STATE: %d -> %d", current_sys_state, new_state);
            current_sys_state = new_state;
            
            // Neu mat ket noi mang ma dang stream -> fallback Offline (IDLE)
            if (new_state == SYS_OFFLINE
            && (current_app_state == STATE_STREAM_UP || current_app_state == STATE_WAIT_SERVER)){
                ESP_LOGW(TAG, "Mat Ket NOi, tam dung stream am thanh va cho phan hoi tu server!!!");
                current_app_state = STATE_IDLE;
                audio_start_streaming(false);
            }
        }

        xSemaphoreGive(state_mutex);
    }
}

// Hàm yêu cầu chuyển đổi trạng thái tác vụ (Kiểm tra điều kiện trước khi chuyển)
bool request_app_state(app_state_t new_state){
    bool allowed = false;

    if (xSemaphoreTake(state_mutex, portMAX_DELAY)){
        
        // Muon stream up/down, dong bo lich len server thi can ket noi mqtt
        if ((new_state == STATE_STREAM_UP || new_state == STATE_SYNCING 
            || new_state == STATE_STREAM_DOWN) && current_sys_state != SYS_MQTT_OK){
                ESP_LOGE(TAG, "Chua co ket noi MQTT, khong chuyen sang trang thai %d", new_state);
        } 
        
        // Neu co lich dong bo lich tu Server gui xuong, uu tien dong bo lich
        else if (new_state == STATE_SYNCING) {
            ESP_LOGW(TAG, "Co yeu cau cap nhat lich (STATE_SYNCING), Tam dung cac tac vu khac");

            // Dung stream
            if (current_app_state == STATE_STREAM_UP){
                audio_start_streaming(false);
            }

            current_app_state = new_state;
            allowed = true;
        }

        // Duoc chuyen doi trang thai
        else {
            ESP_LOGI(TAG, "APP STATE Chuyển đổi: %d -> %d", current_app_state, new_state);
            current_app_state = new_state;
            allowed = true;
        }

        xSemaphoreGive(state_mutex);
    }

    return allowed;
}

// Cac ham getter
app_state_t get_app_state(void){
    app_state_t state;

    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_app_state;
    xSemaphoreGive(state_mutex);

    return state;
}

sys_state_t get_sys_state(void){
    sys_state_t state;

    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_sys_state;
    xSemaphoreGive(state_mutex);

    return state;
}