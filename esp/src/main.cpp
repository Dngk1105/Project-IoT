#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "config.h"
#include "wifi_core.h"
#include "mqtt_handler.h"
#include "time_core.h"
#include "audio_i2s.h"
#include "esp_log.h"

static const char *TAG = "MAIN_APP";

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

// Lưu trạng thái, dùng mutex để tránh đụng độ cho luồng
static volatile sys_state_t current_sys_state = SYS_INIT;
static volatile app_state_t current_app_state = STATE_IDLE;
static SemaphoreHandle_t state_mutex;

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
    }
    xSemaphoreGive(state_mutex);
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
            if (current_app_state == STATE_STREAM_UP) audio_start_streaming(false);
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
app_state_t get_app_state() {
    app_state_t state;
    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_app_state;
    xSemaphoreGive(state_mutex);
    return state;
}

sys_state_t get_sys_state() {
    sys_state_t state;
    xSemaphoreTake(state_mutex, portMAX_DELAY);
    state = current_sys_state;
    xSemaphoreGive(state_mutex);
    return state;
}

/*Doi sang dung bien trang thai de quan li ket noi */
// // Event Group để đồng bộ giữa 2 core
// // App_Task (Core 1) chờ MQTT_Task (Core 0) kết nối xong mới bắt đầu stream
// static EventGroupHandle_t system_event_group;
// #define MQTT_READY_BIT BIT0

/* =========================================================================
 * TASK MQTT — CORE 0
 * Khong tu huy nua, can lien tuc kiem tra ket noi
 * Neu ket noi wifi thanh cong (sys_state == SYS_WIFI_OK)
 * Ket noi mqtt thanh cong (sys_state == SYS_MQTT_OK)
 * Task kiem tra ket noi xxx giay/lan
 * ========================================================================= */
void mqtt_task_runner(void *pvParameters) {
    wifi_wait_for_connection();

    ESP_LOGI(TAG, "Khởi tạo MQTT Handler...");
    mqtt_handler_init();
    mqtt_handler_start();

    // // Chờ MQTT kết nối thực sự (mqtt_is_connected() = true)
    // // Poll mỗi 200ms, tối đa 30 giây
    // int wait_count = 0;
    // while (!mqtt_is_connected() && wait_count < 150) {
    //     vTaskDelay(pdMS_TO_TICKS(200));
    //     wait_count++;
    // }
    while (1){
        if (mqtt_is_connected()) {
            set_sys_state(SYS_MQTT_OK);
        } else {
            if (get_sys_state() == SYS_MQTT_OK) // Rot ket noi, quay tro ve trang thai cu
                set_sys_state(SYS_WIFI_OK);
        }
        vTaskDelay(pdMS_TO_TICKS(1000)); //Dung tam thoi 1s
    }
}

/* =========================================================================
 * Dieu phoi logic chinh cho ca chuong trinh
 * Quyet dinh se lam gi voi tung trang thai ung dung
 * ========================================================================= */
void app_logic_task(void *pvParameters) {
    // Cho ket noi wifi de dong bo gio
    while(get_sys_state() == SYS_INIT) 
        vTaskDelay(pdMS_TO_TICKS(100));

    // wifi_wait_for_connection(); nam trong task mqtt
    
    // Khởi tạo các ngoại vi
    time_core_init();
    audio_i2s_init();

    ESP_LOGI(TAG, "Logic Task bắt đầu hoạt động...");

    while (1){
        app_state_t current_state = get_app_state();
        sys_state_t net_state = get_sys_state();

        switch (current_state){
            case STATE_IDLE:
                // 1. Kiểm tra lịch báo thức offline (từ LittleFS)
                // if (local_storage_check_alarm_time()) {
                //      request_app_state(STATE_ALARMING);
                // }
                
                // 2. Định kỳ bắn Telemetry (Chỉ cần có MQTT)
                // if (net_state == SYS_MQTT_OK && time_to_send_telemetry) {
                //      telemetry_send_metrics();
                // }
                break;
            case STATE_ALARMING:
                // Phát file MP3 cảnh báo từ Flash
                ESP_LOGI(TAG, "Đang đổ chuông báo thức...");
                // audio_play_local_mp3("/spiffs/alarm.mp3");
                // Hen khoang thoi gian phat lien tuc
                // Phát xong tự động chuyển sang chế độ chờ lệnh
                request_app_state(STATE_LISTENING);
                break;

            case STATE_LISTENING:
                // Kích hoạt ESP-SR (WakeNet/MultiNet)
                ESP_LOGI(TAG, "Đang chờ người dùng ra lệnh...");
                // Nếu nghe được "Snooze" -> local_storage_update() -> Gửi Event QoS1 -> Về IDLE
                // Nếu câu phức tạp -> request_app_state(STATE_STREAM_UP)
                break;

            case STATE_STREAM_UP:
                // Đang đẩy mic lên server. Việc đẩy thực tế chạy ở Task khác (audio_stream_task)
                // Ở đây FSM chỉ giám sát.
                break;
            
            case STATE_WAIT_SERVER:
                // Đang nằm chờ luồng Stream Down về
                // Hoac lenh dieu khien he thong
                // Mien la co phan hoi tu server 
                // Voice Watchdog sẽ kích nổ nếu kẹt ở đây quá 5 giây.
                break;

            case STATE_STREAM_DOWN:
                // Dang phat tieng tu server
                break;

            case STATE_SYNCING:
                // Đang ghi File. Cực kỳ nhạy cảm, không được làm việc khác.
                // local_storage_save_json();
                // Dong bo time voi server
                ESP_LOGI(TAG, "Đã ghi xong lịch học. Quay về IDLE.");
                request_app_state(STATE_IDLE);
                break;
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // 20Hz
    }

    // // [FIX] Chờ MQTT kết nối xong trước khi làm gì với audio
    // ESP_LOGI(TAG, "Đang chờ MQTT sẵn sàng...");
    // xEventGroupWaitBits(system_event_group, MQTT_READY_BIT,
    //                     pdFALSE, pdTRUE, portMAX_DELAY);
    // ESP_LOGI(TAG, "✅ MQTT sẵn sàng — tiếp tục khởi tạo Audio.");

    // // Khởi tạo thời gian và I2S
    // time_core_init();

    // esp_err_t audio_ret = audio_i2s_init();
    // if (audio_ret != ESP_OK) {
    //     ESP_LOGE(TAG, "❌ I2S khởi tạo thất bại (0x%x) — dừng task.", audio_ret);
    //     vTaskDelete(NULL);
    //     return;
    // }

    // ESP_LOGI(TAG, "Device ID: %s", mqtt_get_device_id());
    // audio_start_streaming(false);

    // // Vòng lặp giám sát trạng thái
    // while (1) {
    //     vTaskDelay(pdMS_TO_TICKS(5000));
    //     ESP_LOGI(TAG, "[STATUS] Streaming: %s | MQTT: %s | Free Heap: %lu bytes",
    //              audio_is_streaming() ? "ON"  : "OFF",
    //              mqtt_is_connected()  ? "YES" : "NO",
    //              esp_get_free_heap_size());
    // }
}

/* =========================================================================
 * ENTRY POINT
 * ========================================================================= */
extern "C" void app_main() {
    ESP_LOGI(TAG, "=== IoT Schedule Edge Device — Khởi động ===");

    // // Tạo Event Group đồng bộ trước khi tạo task
    // system_event_group = xEventGroupCreate();
    state_mutex = xSemaphoreCreateMutex();

    wifi_init_sta();

    // Core 0: Mạng & MQTT Lo viec giao tiep, giu nhip PINGREQ va bat tin hieu mang
    xTaskCreatePinnedToCore(mqtt_task_runner, "MQTT_Task",
                            TASK_STACK_MQTT, NULL, TASK_PRIO_MQTT, NULL, 0);

    // Core 1: Audio & Logic: Dieu phoi trang thai, am thanh va doc ghi bo nho
    xTaskCreatePinnedToCore(app_logic_task, "App_Audio_Task",
                            TASK_STACK_AUDIO, NULL, TASK_PRIO_AUDIO, NULL, 1);

    ESP_LOGI(TAG, "Tất cả task đã tạo xong. Hệ thống đang chạy.");
}
