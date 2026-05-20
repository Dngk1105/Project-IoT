#ifndef MQTT_HANDLER_H
#define MQTT_HANDLER_H

#include "mqtt_client.h"
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Khởi tạo MQTT Client (Cấu hình Broker, Client ID, LWT, MQTT 5.0)
 * Yêu cầu WiFi đã kết nối thành công trước khi gọi hàm này.
 */
void mqtt_handler_init(void);

/**
 * @brief Bắt đầu tiến trình MQTT (Connect tới Broker)
 */
void mqtt_handler_start(void);

/**
 * @brief Kiểm tra trạng thái kết nối MQTT
 * @return true nếu đang kết nối, false nếu offline
 */
bool mqtt_is_connected(void);

/**
 * @brief Lấy handle của MQTT Client để các module khác (device_shadow, telemetry) 
 * có thể gọi hàm esp_mqtt_client_publish()
 */
esp_mqtt_client_handle_t mqtt_get_client(void);

#ifdef __cplusplus
}
#endif

#endif // MQTT_HANDLER_H