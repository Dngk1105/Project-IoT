#include "system_state.h"
#include "esp_log.h"
#include "audio_i2s.h"

const char *TAG = "SYSTEM_STATE";

// Lưu trạng thái, dùng mutex để tránh đụng độ cho luồng
static volatile sys_state_t current_sys_state = SYS_INIT;
static volatile app_state_t current_app_state = STATE_IDLE;
static SemaphoreHandle_t state_mutex;

// Phục vụ debug
const char* sys_state_to_str(sys_state_t state) {
    switch(state) {
        case SYS_INIT:      return "SYS_INIT";
        case SYS_OFFLINE:   return "SYS_OFFLINE";
        case SYS_WIFI_OK:   return "SYS_WIFI_OK";
        case SYS_MQTT_OK:   return "SYS_MQTT_OK";
        default:            return "UNKNOWN";
    }
}

const char* app_state_to_str(app_state_t state) {
    switch(state) {
        case STATE_IDLE:         return "STATE_IDLE";
        case STATE_ALARMING:     return "STATE_ALARMING";
        case STATE_LISTENING:    return "STATE_LISTENING";
        case STATE_STREAM_UP:    return "STATE_STREAM_UP";
        case STATE_WAIT_SERVER:  return "STATE_WAIT_SERVER";
        case STATE_STREAM_DOWN:  return "STATE_STREAM_DOWN";
        case STATE_SYNCING:      return "STATE_SYNCING";
        default:                 return "UNKNOWN";
    }
}


// Khoi tao mutex
void state_manager_init(void){
    if (state_mutex == NULL){
        state_mutex = xSemaphoreCreateMutex();
        ESP_LOGI(TAG, "State Manager đã khởi tạo thành công.");
    }
}

//Hàm quản lí trạng thái, Chi co mot luong duoc su dung
void set_sys_state(sys_state_t new_state){
    if (state_mutex == NULL) return; // Tranh goi ham truoc khi khoi tao

    if (xSemaphoreTake(state_mutex, portMAX_DELAY)){
        if (current_sys_state != new_state){
            ESP_LOGI(TAG, "Cap nhat SYSTEM_STATE: %s -> %s", 
                sys_state_to_str(current_sys_state), sys_state_to_str(new_state));
            
            current_sys_state = new_state;
            
            // Neu mat ket noi mang ma dang stream -> fallback Offline (IDLE)
            if (new_state == SYS_OFFLINE || new_state == SYS_WIFI_OK){
                if (current_app_state == STATE_STREAM_UP || current_app_state == STATE_WAIT_SERVER){
                    ESP_LOGW(TAG, "Mat Ket NOi, tam dung stream am thanh va cho phan hoi tu server!!!");
                    current_app_state = STATE_IDLE;
                    audio_start_streaming(false);
                    //TODO: Thong bao tinh trang mat mang (nhay led)
                }
            }
        }

        xSemaphoreGive(state_mutex);
    }
}

// Hàm yêu cầu chuyển đổi trạng thái tác vụ (Kiểm tra điều kiện trước khi chuyển)
bool request_app_state(app_state_t new_state){
    if (state_mutex == NULL) return false;
    bool allowed = false;

    if (xSemaphoreTake(state_mutex, portMAX_DELAY)){
        
        // Muon stream up/down, dong bo lich len server thi can ket noi mqtt
        if ((new_state == STATE_STREAM_UP || new_state == STATE_SYNCING 
            || new_state == STATE_STREAM_DOWN) && current_sys_state != SYS_MQTT_OK){
                ESP_LOGE(TAG, "Chua co ket noi MQTT, khong chuyen sang trang thai %s", app_state_to_str(new_state));
        } 
        
        // Neu co lich dong bo lich tu Server gui xuong, uu tien dong bo lich
        else if (new_state == STATE_SYNCING) {
            ESP_LOGW(TAG, "Co yeu cau cap nhat lich (STATE_SYNCING), Tam dung cac tac vu khac");

            // Dung stream
            if (current_app_state == STATE_STREAM_UP){
                audio_start_streaming(false);
            }
            // Nếu đang stream down (loa đang kêu), FSM sẽ phải tự xử lý việc xả buffer I2S ở loop chính

            current_app_state = new_state;
            allowed = true;
        }

        // Duoc chuyen doi trang thai
        else {
            ESP_LOGI(TAG, "APP STATE Chuyển đổi: %s -> %s", 
                app_state_to_str(current_app_state), app_state_to_str(new_state));
            current_app_state = new_state;
            allowed = true;
        }

        xSemaphoreGive(state_mutex);
    }

    return allowed;
}

// Cac ham getter
app_state_t get_app_state(void){
    if (state_mutex == NULL) return STATE_IDLE;
    app_state_t state;

    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_app_state;
    xSemaphoreGive(state_mutex);

    return state;
}

sys_state_t get_sys_state(void){
    if (state_mutex == NULL) return SYS_INIT;
    sys_state_t state;

    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_sys_state;
    xSemaphoreGive(state_mutex);

    return state;
}


//Kiem tra co idle
bool is_system_idle(void) {
    if (state_mutex == NULL) return false;
    bool idle = false;
    xSemaphoreTake(state_mutex, portMAX_DELAY);
    idle = (current_app_state == STATE_IDLE);
    xSemaphoreGive(state_mutex);
    return idle;
}

// Hàm ép trạng thái, Dùng cho các trường hợp khẩn cấp
void force_app_state_idle(void) {
    if (state_mutex == NULL) return;
    xSemaphoreTake(state_mutex, portMAX_DELAY);
    if (current_app_state != STATE_IDLE) {
        ESP_LOGE(TAG, "Ép buộc hệ thống về STATE_IDLE từ trạng thái %s", app_state_to_str(current_app_state));
        current_app_state = STATE_IDLE;
    }
    xSemaphoreGive(state_mutex);
}