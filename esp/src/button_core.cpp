#include "button_core.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "system_state.h"
#include "audio_i2s.h"
#include "mqtt_handler.h"
#include "mqtt_protocol.h"
#include "cJSON.h"
#include "config.h"

// Cấu hình chân nút bấm
static const char *TAG = "BUTTON_CORE";

typedef struct {
    gpio_num_t pin;             // Chân GPIO cắm nút
    bool is_pressed;            // Trạng thái hiện tại (phục vụ Debounce)
    void (*on_pressed)(void);   // Con trỏ hàm: Thực thi khi NHẤN
    void (*on_released)(void);  // Con trỏ hàm: Thực thi khi NHẢ
} button_context_t;

static void on_ptt_pressed(void) {
    ESP_LOGI(TAG, "Nút PTT được NHẤN! Bắt đầu thu âm...");
    if (request_app_state(STATE_STREAM_UP)) {
        audio_start_streaming(true);
        
        char topic[80];
        mqtt_proto_get_audio_control_topic(mqtt_get_device_id(), topic, sizeof(topic));
        cJSON* data = cJSON_CreateObject();
        cJSON_AddStringToObject(data, "state", "start_stream");
        char* payload = mqtt_proto_build_standard_payload(data);
        mqtt_handler_publish(topic, payload, 0, 1, 0);
        free(payload);
    }
}

static void on_ptt_released(void) {
    ESP_LOGI(TAG, "Nút PTT được NHẢ! Dừng thu âm, chờ Server...");
    if (get_app_state() == STATE_STREAM_UP) {
        audio_request_stop();
        
        char topic[80];
        mqtt_proto_get_audio_control_topic(mqtt_get_device_id(), topic, sizeof(topic));
        cJSON* data = cJSON_CreateObject();
        cJSON_AddStringToObject(data, "state", "stop_stream");
        char* payload = mqtt_proto_build_standard_payload(data);
        mqtt_handler_publish(topic, payload, 0, 1, 0);
        free(payload);

        // Kích hoạt Watchdog 5 giây
        request_app_state(STATE_WAIT_SERVER);
    }
}

static button_context_t my_buttons[] = {
    // {Chân GPIO, Trạng thái đầu, Hàm gọi khi nhấn, Hàm gọi khi nhả}
    {PUSH_TO_TALK_BTN, false, on_ptt_pressed, on_ptt_released}
    
};

#define NUM_BUTTONS (sizeof(my_buttons) / sizeof(my_buttons[0]))

static void button_task(void *pvParameters) {
    ESP_LOGI(TAG, "Core giám sát %d nút bấm bắt đầu chạy...", NUM_BUTTONS);

    while(1) {
        // Quét qua toàn bộ mảng cấu hình
        for (int i = 0; i < NUM_BUTTONS; i++) {
            int level = gpio_get_level(my_buttons[i].pin);
            
            // Phát hiện Cạnh xuống (Kéo GND -> Nhấn)
            if (level == 0 && !my_buttons[i].is_pressed) { 
                vTaskDelay(pdMS_TO_TICKS(500)); // Debounce 500ms
                if (gpio_get_level(my_buttons[i].pin) == 0) {
                    my_buttons[i].is_pressed = true;
                    // Kích hoạt Callback nếu có
                    if (my_buttons[i].on_pressed != NULL) {
                        my_buttons[i].on_pressed();
                    }
                }
            } 
            // Phát hiện Cạnh lên (Thả GND -> Nhả)
            else if (level == 1 && my_buttons[i].is_pressed) { 
                vTaskDelay(pdMS_TO_TICKS(50)); // Debounce 50ms
                if (gpio_get_level(my_buttons[i].pin) == 1) {
                    my_buttons[i].is_pressed = false;
                    // Kích hoạt Callback nếu có
                    if (my_buttons[i].on_released != NULL) {
                        my_buttons[i].on_released();
                    }
                }
            }
        }
        // Quét 100Hz (10ms/lần)
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void button_core_init(void) {
    gpio_config_t io_conf = {};
    io_conf.intr_type = GPIO_INTR_DISABLE;      
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_ENABLE;    

    //Bitmask: Tự động gom tất cả các chân GPIO trong mảng để config 1 lần
    uint64_t pin_bit_mask = 0;
    for (int i = 0; i < NUM_BUTTONS; i++) {
        pin_bit_mask |= (1ULL << my_buttons[i].pin);
    }
    
    io_conf.pin_bit_mask = pin_bit_mask;
    gpio_config(&io_conf);

    // Chạy Task
    xTaskCreatePinnedToCore(button_task, "Button_Task", 4096, NULL, 5, NULL, 1);
    
    ESP_LOGI(TAG, "Khởi tạo Button Framework thành công!");
}