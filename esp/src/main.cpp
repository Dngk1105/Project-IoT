#include "wifi.h"
#include "mqtt_handler.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"



/// ======================================================
/// APP MAIN
///
/// Entry point của ESP-IDF
/// ======================================================
extern "C" void app_main(void)
{
    /// --------------------------------------------------
    /// WIFI CONNECT
    /// --------------------------------------------------
    wifi_init();



    /// --------------------------------------------------
    /// MQTT INIT
    /// --------------------------------------------------
    mqtt_init();



    /// Chờ MQTT connect ổn định
    vTaskDelay(pdMS_TO_TICKS(3000));



    /// --------------------------------------------------
    /// LOOP
    /// --------------------------------------------------
    while (1) {

        /// Publish test message
        mqtt_send(
            "hust_iot/test",
            "hello from esp32"
        );



        /// Delay 5 giây
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}