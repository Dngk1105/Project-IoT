#include "time_core.h"
#include "config.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include <time.h>
#include <sys/time.h>

static const char *TAG = "TIME_CORE";
static bool is_synced = false;

/* =========================================================================
 * KHỞI TẠO ĐỒNG BỘ THỜI GIAN QUA Server
 *
 * Theo MQTT Convention: Toàn bộ timestamp phải là UNIX Timestamp (số nguyên)
 * Hàm này sẽ đồng bộ thời gian từ server NTP để hệ thống luôn có thời gian chính xác.
 * ========================================================================= */
void time_core_init(void) {
    ESP_LOGI(TAG, "Đang khởi tạo Time Core để đồng bộ thời gian voi Server...");
    is_synced = false;
}

void time_core_set_time(uint32_t unix_timestamp){
    struct timeval tv;
    tv.tv_sec = unix_timestamp;
    tv.tv_usec = 0;
    
    settimeofday(&tv, NULL);

    is_synced = true;
    ESP_LOGI(TAG, "Đã đồng bộ RTC thành công! Timestamp: %lu", unix_timestamp);
}

/* =========================================================================
 * LẤY THỜI GIAN UNIX TIMESTAMP HIỆN TẠI
 * 
 * Neu chua sync voi server thi tra ve 0
 * Đây là định dạng BẮT BUỘC theo MQTT Convention (không dùng chuỗi ISO)
 * ========================================================================= */
uint32_t get_current_unix_timestamp(void) {
    if (!is_synced) return 0;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec;
}

bool time_core_is_synced(void) {
    return is_synced;
}