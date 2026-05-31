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
 * BỘ ĐỆM RINGBUFFER CHỐNG JITTER (MẠNG LAG)
 * ========================================================================= */

// Đẩy dữ liệu âm thanh nhị phân thô nhận từ MQTT vào RingBuffer (Non-blocking)
void audio_ringbuf_feed(const uint8_t *data, size_t len);
void audio_psram_init(void);
void audio_psram_feed(const uint8_t *data, size_t len);

// Báo hiệu đã nhận xong trọn vẹn toàn bộ các chunk file Audio từ Server
void audio_ringbuf_finish(void);


/* =========================================================================
 * DỌN DẸP TÀI NGUYÊN
 * ========================================================================= */

/**
 * Dừng I2S và giải phóng tất cả tài nguyên
 */
void audio_i2s_deinit(void);

/**
 * Xa buffer phat ra loa
 */
void audio_flush_playback(void);

//Xin dung, Module khac goi vao
void audio_request_stop(void);


bool audio_is_finished(void);
void audio_set_finished(bool value);

extern void audio_test_beep_task(void *pvParameters);
#ifdef __cplusplus
}
#endif

#endif // AUDIO_I2S_H