#ifndef WIFI_CORE_H
#define WIFI_CORE_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Khởi tạo và kết nối WiFi Station
 * Cấu hình lấy từ config.h
 */
void wifi_init_sta(void);

/**
 * @brief Block luồng hiện tại cho đến khi WiFi kết nối thành công
 * Dùng Event Group của FreeRTOS.
 */
void wifi_wait_for_connection(void);

bool wifi_is_connected(void);

#ifdef __cplusplus
}
#endif

#endif // WIFI_CORE_H