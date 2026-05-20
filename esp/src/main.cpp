#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "wifi_core.h"
#include "mqtt_handler.h"
#include "time_core.h"

// Task bọc MQTT chạy trên Core 0
void mqtt_task_runner(void *pvParameters) {
    // Đợi đến khi nào WiFi bắt tay thành công mới chạy tiếp
    wifi_wait_for_connection();
    
    mqtt_handler_init();
    mqtt_handler_start();
    
    // Task này chỉ init rồi tự hủy, vì driver esp_mqtt tự sinh task ngầm bên trong (nằm sẵn ở Core 0)
    vTaskDelete(NULL); 
}

// Task bọc Audio/App logic chạy trên Core 1
void app_logic_task(void *pvParameters) {
    // Đợi WiFi để đồng bộ giờ NTP
    wifi_wait_for_connection();
    time_core_init(); 
    
    while(1) {
        // TODO: Chạy logic kiểm tra báo thức, đọc Mic, xử lý AI...
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

extern "C" void app_main() {
    // 1. Khởi tạo WiFi (Chạy trên luồng Main mặc định)
    wifi_init_sta();

    // 2. Phân luồng chạy vào 2 Core
    
    // xTaskCreatePinnedToCore(TaskFunction_t, Name, StackDepth, Parameters, Priority, TaskHandle, CoreID);
    
    // Ném xử lý Mạng vào Core 0 (PRO_CPU = 0)
    xTaskCreatePinnedToCore(mqtt_task_runner, "MQTT_Init", 4096, NULL, 5, NULL, 0);

    // Ném xử lý Ứng dụng/Âm thanh vào Core 1 (APP_CPU = 1)
    xTaskCreatePinnedToCore(app_logic_task, "App_Logic", 8192, NULL, 5, NULL, 1);
}