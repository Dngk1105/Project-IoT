#include "light_control.h"
#include "config.h"
#include "esp_log.h"
#include "driver/gpio.h"

static const char *TAG = "LIGHT_CONTROL";
static bool is_light_on = false;

void light_control_init(void) {
    gpio_config_t io_conf = {};
    io_conf.intr_type = GPIO_INTR_DISABLE;
    io_conf.mode = GPIO_MODE_INPUT_OUTPUT; // Đặt Input_Output để có thể đọc ngược lại trạng thái điện áp
    io_conf.pin_bit_mask = (1ULL << LED_LIGHT_GPIO);
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    gpio_config(&io_conf);
    
    // Vừa bật nguồn là khóa chân về mức 0 ngay để an toàn phần cứng
    gpio_set_level(LED_LIGHT_GPIO, 0); 
    is_light_on = false;
    ESP_LOGI(TAG, "Đã cấu hình xong chân Đèn (%d). Mặc định: TẮT", LED_LIGHT_GPIO);
}

void light_control_set_state(bool turn_on) {
    gpio_set_level(LED_LIGHT_GPIO, turn_on ? 1 : 0);
    is_light_on = turn_on;
    ESP_LOGI(TAG, "Đèn vật lý đã chuyển sang trạng thái -> %s", turn_on ? "BẬT" : "TẮT");
}

bool light_control_get_state(void) {
    return is_light_on;
}