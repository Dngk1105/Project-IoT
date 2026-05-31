#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "cJSON.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_CACHED_EVENTS 50

// Map với EventLiteESP32.action của Server
typedef enum {
    ACTION_ALARM = 0,
    ACTION_CLASS,
    ACTION_MEET,
    ACTION_VOICE
} event_action_t;

typedef struct {
    char id[40];           // UUID (36 ký tự + null)
    uint32_t timestamp;    // Giờ UNIX (t)
    event_action_t action; // Loại sự kiện (a)
    char msg[36];          // Tiêu đề ngắn gọn (msg)
} esp_calendar_event_t;

/* =========================================================================
 * API QUẢN LÝ LƯU TRỮ VÀ LỊCH TRÌNH
 * ========================================================================= */

/**
 * @brief Khởi tạo phân vùng LittleFS và nạp dữ liệu từ file schedule.json lên RAM
 */
void local_storage_init(void);

/**
 * @brief Nhận JSON Delta từ Server, tính toán lại Cache và ghi xuống Flash
 * @param delta_data Con trỏ cJSON trỏ tới object chứa mảng "add", "upd", "del"
 * @return true nếu ghi Flash thành công
 */
bool local_storage_sync_schedule(cJSON *delta_data);

/**
 * @brief Trả về sự kiện sắp diễn ra nhất (để app_logic_task so sánh giờ)
 * @param out_event Con trỏ để copy dữ liệu sự kiện ra ngoài
 * @return true nếu có sự kiện, false nếu kho rỗng
 */
bool local_storage_get_next_event(esp_calendar_event_t *out_event);

/**
 * @brief Xóa một sự kiện khỏi RAM và Flash sau khi đã báo thức hoặc hết hạn
 */
void local_storage_remove_event(const char* event_id);


#ifdef __cplusplus
}
#endif