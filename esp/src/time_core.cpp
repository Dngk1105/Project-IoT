#include "time_core.h"
#include "config.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include <time.h>
#include <sys/time.h>

static const char *TAG = "TIME_CORE";

/* =========================================================================
 * KHỞI TẠO ĐỒNG BỘ THỜI GIAN QUA SNTP
 *
 * Theo MQTT Convention: Toàn bộ timestamp phải là UNIX Timestamp (số nguyên)
 * Hàm này sẽ đồng bộ thời gian từ server NTP để hệ thống luôn có thời gian chính xác.
 * ========================================================================= */
void time_core_init(void) {
    ESP_LOGI(TAG, "Đang khởi tạo SNTP để đồng bộ thời gian...");

    // Cấu hình chế độ hoạt động của SNTP
    sntp_setoperatingmode(SNTP_OPMODE_POLL);                    // Chế độ Poll (hỏi định kỳ)

    // Thiết lập các server NTP (ưu tiên pool.ntp.org)
    sntp_setservername(0, NTP_SERVER_1);                        // Server chính
    sntp_setservername(1, NTP_SERVER_2);                        // Server dự phòng

    // Bắt đầu tiến trình đồng bộ thời gian
    sntp_init();

    ESP_LOGI(TAG, "SNTP đã được khởi tạo. Đang chờ đồng bộ thời gian từ: %s", NTP_SERVER_1);

    // Thiết lập múi giờ Việt Nam (UTC+7)
    setenv("TZ", "ICT-7", 1);      // ICT = Indochina Time
    tzset();

    // Chờ một chút để SNTP đồng bộ lần đầu (tối đa 10 giây)
    // Trong thực tế, bạn có thể làm hàm chờ non-blocking ở task riêng
    vTaskDelay(pdMS_TO_TICKS(8000));

    time_t now;
    time(&now);
    if (now > 1720000000) {  // Kiểm tra xem thời gian đã hợp lệ chưa (sau năm 2024)
        ESP_LOGI(TAG, "Đồng bộ thời gian thành công! Current UNIX Timestamp: %lu", (uint32_t)now);
    } else {
        ESP_LOGW(TAG, "Chưa đồng bộ được thời gian. Sẽ thử lại sau...");
    }
}

/* =========================================================================
 * LẤY THỜI GIAN UNIX TIMESTAMP HIỆN TẠI
 * 
 * Trả về số giây kể từ 00:00:00 ngày 1/1/1970 (UTC)
 * Đây là định dạng BẮT BUỘC theo MQTT Convention (không dùng chuỗi ISO)
 * ========================================================================= */
uint32_t get_current_unix_timestamp(void) {
    time_t now;
    time(&now);
    
    // Nếu thời gian chưa được đồng bộ (vẫn là năm 1970), trả về 0 để dễ debug
    if (now < 1720000000) {
        ESP_LOGW(TAG, "Cảnh báo: Thời gian chưa được đồng bộ đúng (có thể đang dùng thời gian mặc định)");
    }
    
    return (uint32_t)now;
}
