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

// Event Group để đồng bộ giữa 2 core
// App_Task (Core 1) chờ MQTT_Task (Core 0) kết nối xong mới bắt đầu stream
static EventGroupHandle_t system_event_group;
#define MQTT_READY_BIT BIT0

/* =========================================================================
 * TASK MQTT — CORE 0
 * Sau khi mqtt kết nối thành công, set MQTT_READY_BIT để báo Core 1.
 * ========================================================================= */
void mqtt_task_runner(void *pvParameters) {
    wifi_wait_for_connection();

    ESP_LOGI(TAG, "Khởi tạo MQTT Handler...");
    mqtt_handler_init();
    mqtt_handler_start();

    // Chờ MQTT kết nối thực sự (mqtt_is_connected() = true)
    // Poll mỗi 200ms, tối đa 30 giây
    int wait_count = 0;
    while (!mqtt_is_connected() && wait_count < 150) {
        vTaskDelay(pdMS_TO_TICKS(200));
        wait_count++;
    }

    if (mqtt_is_connected()) {
        ESP_LOGI(TAG, "✅ MQTT đã kết nối — báo hiệu Core 1 bắt đầu.");
        xEventGroupSetBits(system_event_group, MQTT_READY_BIT);
    } else {
        ESP_LOGE(TAG, "❌ MQTT không kết nối được sau 30 giây!");
        // Vẫn set bit để Core 1 không bị treo mãi — sẽ tự xử lý reconnect
        xEventGroupSetBits(system_event_group, MQTT_READY_BIT);
    }

    ESP_LOGI(TAG, "MQTT Task hoàn tất khởi tạo và tự hủy.");
    vTaskDelete(NULL);
}

/* =========================================================================
 * TASK ỨNG DỤNG & AUDIO — CORE 1
 *
 * Thứ tự khởi động:
 *   1. Chờ MQTT_READY_BIT từ Core 0
 *   2. Init time + audio
 *   3. Bắt đầu stream thật lên Server
 * ========================================================================= */
void app_logic_task(void *pvParameters) {
    wifi_wait_for_connection();

    // [FIX] Chờ MQTT kết nối xong trước khi làm gì với audio
    ESP_LOGI(TAG, "Đang chờ MQTT sẵn sàng...");
    xEventGroupWaitBits(system_event_group, MQTT_READY_BIT,
                        pdFALSE, pdTRUE, portMAX_DELAY);
    ESP_LOGI(TAG, "✅ MQTT sẵn sàng — tiếp tục khởi tạo Audio.");

    // Khởi tạo thời gian và I2S
    time_core_init();

    esp_err_t audio_ret = audio_i2s_init();
    if (audio_ret != ESP_OK) {
        ESP_LOGE(TAG, "❌ I2S khởi tạo thất bại (0x%x) — dừng task.", audio_ret);
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "Device ID: %s", mqtt_get_device_id());
    audio_start_streaming(true);

    // Vòng lặp giám sát trạng thái
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(5000));
        ESP_LOGI(TAG, "[STATUS] Streaming: %s | MQTT: %s | Free Heap: %lu bytes",
                 audio_is_streaming() ? "ON"  : "OFF",
                 mqtt_is_connected()  ? "YES" : "NO",
                 esp_get_free_heap_size());
    }
}

/* =========================================================================
 * ENTRY POINT
 * ========================================================================= */
extern "C" void app_main() {
    ESP_LOGI(TAG, "=== IoT Schedule Edge Device — Khởi động ===");

    // Tạo Event Group đồng bộ trước khi tạo task
    system_event_group = xEventGroupCreate();

    wifi_init_sta();

    // Core 0: Mạng & MQTT
    xTaskCreatePinnedToCore(mqtt_task_runner, "MQTT_Task",
                            TASK_STACK_MQTT, NULL, TASK_PRIO_MQTT, NULL, 0);

    // Core 1: Audio & Logic (priority cao hơn để xử lý realtime)
    xTaskCreatePinnedToCore(app_logic_task, "App_Audio_Task",
                            TASK_STACK_AUDIO, NULL, TASK_PRIO_AUDIO, NULL, 1);

    ESP_LOGI(TAG, "Tất cả task đã tạo xong. Hệ thống đang chạy.");
}
