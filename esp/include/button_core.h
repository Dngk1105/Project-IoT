#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Khởi tạo toàn bộ nút bấm đã được cấu hình
 * Khởi chạy Task quét nút ngầm (Debounce 50ms)
 */
void button_core_init(void);

#ifdef __cplusplus
}
#endif