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

/**
 * @brief Publish dữ liệu lên một topic
 * @param topic Tên topic cần publish
 * @param payload Dữ liệu cần gửi
 * @param len Chiều dài dữ liệu (nếu là chuỗi string có thể để 0)
 * @param qos Chất lượng dịch vụ (0, 1, 2)
 * @param retain Cờ giữ lại tin nhắn (0 hoặc 1)
 * @return Message ID nếu thành công, -1 nếu thất bại
 */
int mqtt_handler_publish(const char *topic, const char *payload, int len, int qos, int retain);

/**
 * @brief Subscribe một topic
 * @param topic Tên topic cần theo dõi
 * @param qos Chất lượng dịch vụ (0, 1, 2)
 * @return Message ID nếu thành công, -1 nếu thất bại
 */
int mqtt_handler_subscribe(const char *topic, int qos);

#ifdef __cplusplus
}
#endif

#endif // MQTT_HANDLER_H