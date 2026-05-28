#ifndef TIME_CORE_H
#define TIME_CORE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Khởi tạo đồng bộ thời gian qua Server 
 * Dung SNTP luc duoc luc khong 
 */
void time_core_init(void);

// Nap timestamp tu server vao RTC cua esp
void time_core_set_time(uint32_t unix_timestamp);

/**
 * @brief Lấy Unix Timestamp hiện tại
 * @return uint32_t timestamp (0 neu chua dong bo)
 */
uint32_t get_current_unix_timestamp(void);

// Kiem tra gio chuan chua
bool time_core_is_synced(void);

#ifdef __cplusplus
}
#endif

#endif // TIME_CORE_H