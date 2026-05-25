#ifndef AUDIO_I2S_H
#define AUDIO_I2S_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * KHỞI TẠO AUDIO I2S
 * ========================================================================= */

/**
 * Khởi tạo driver I2S với cấu hình gộp bus (chia sẻ BCLK và WS)
 * Sử dụng GPIO 12 (BCLK), GPIO 13 (WS) cho cả Mic và Loa
 */
esp_err_t audio_i2s_init(void);


/* =========================================================================
 * STREAM AUDIO LÊN SERVER
 * ========================================================================= */

/**
 * Bắt đầu hoặc dừng stream âm thanh từ Microphone lên MQTT Broker
 * Topic sử dụng: iot_schedule/<device_id>/audio/stream_up
 * Tự động kích hoạt Voice Watchdog 5 giây
 */
void audio_start_streaming(bool enable);

/**
 * Kiểm tra trạng thái hiện tại có đang stream audio hay không
 */
bool audio_is_streaming(void);


/* =========================================================================
 * VOICE WATCHDOG
 * ========================================================================= */

/**
 * Reset Voice Watchdog Timer (5 giây)
 * Hàm này nên được gọi khi nhận được phản hồi TTS từ Server
 */
void audio_reset_watchdog(void);


/* =========================================================================
 * PHÁT ÂM THANH
 * ========================================================================= */

/**
 * Phát âm thanh qua Loa từ buffer dữ liệu
 * Dùng để phát TTS nhận từ Server hoặc file cảnh báo
 */
esp_err_t audio_playback(const uint8_t* data, size_t len);

/* =========================================================================
 * TEST LOOPBACK
 * ========================================================================= */
/**
 * Test Loopback: Ghi âm từ Mic và phát lại ngay qua Loa
 * Dùng để kiểm tra cả Mic và Loa có hoạt động không
 */
esp_err_t audio_test_loopback(void);

/* =========================================================================
 * DỌN DẸP TÀI NGUYÊN
 * ========================================================================= */

/**
 * Dừng I2S và giải phóng tất cả tài nguyên
 */
void audio_i2s_deinit(void);

#ifdef __cplusplus
}
#endif

#endif // AUDIO_I2S_H