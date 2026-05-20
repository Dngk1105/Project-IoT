#ifndef TIME_CORE_H
#define TIME_CORE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Khởi tạo đồng bộ thời gian qua SNTP
 */
void time_core_init(void);

/**
 * @brief Lấy Unix Timestamp hiện tại (số giây từ 1/1/1970)
 * @return uint32_t timestamp
 */
uint32_t get_current_unix_timestamp(void);

#ifdef __cplusplus
}
#endif

#endif // TIME_CORE_H