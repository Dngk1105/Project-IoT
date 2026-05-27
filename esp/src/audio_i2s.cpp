#include "audio_i2s.h"
#include "config.h"
#include "mqtt_handler.h"
#include "system_state.h"
#include "mqtt_protocol.h"
#include "esp_log.h"
#include "driver/i2s_std.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/timers.h"
#include "freertos/ringbuf.h"
#include <stdlib.h>
#include <string.h>
#include "esp_timer.h"

static const char *TAG = "AUDIO_I2S";

static volatile bool is_streaming = false;
static TaskHandle_t audio_stream_task_handle = NULL;
static TaskHandle_t audio_playback_task_handle = NULL;

static void audio_stream_task(void *pvParameters);
static void audio_playback_task(void *pvParameters);

/* Audio Playback dung bo dem RingBuffer
 * MQTT day payload vao Ring
 * Audio Task lay payload tu Ring, Chi lay khi RingBuffer du du lieu
*/
static volatile bool is_playback_finished = true;
static RingbufHandle_t audio_ringbuf = NULL;

static i2s_chan_handle_t rx_handle = NULL;  // I2S_NUM_0 — INMP441
static i2s_chan_handle_t tx_handle = NULL;  // I2S_NUM_1 — MAX98357A

/* =========================================================================
 * CONFIG I2S_NUM_0 — INMP441 Microphone
 *
 * data_bit_width = 16BIT : ESP-IDF driver tự extract 16-bit từ frame 32-bit,
 *                          trả về buffer int16_t đúng chuẩn — không cần shift thủ công.
 * slot_bit_width = 32BIT : Frame vật lý 32-bit của INMP441
 * bit_shift = true       : Philips I2S format
 * left_align = false     : Data right-justified sau khi driver extract
 * ========================================================================= */
static i2s_std_config_t mic_config = {
    .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
    .slot_cfg = {
        .data_bit_width = I2S_DATA_BIT_WIDTH_32BIT,  // Đọc nguyên frame 32-bit
        .slot_bit_width = I2S_SLOT_BIT_WIDTH_32BIT,
        .slot_mode      = I2S_SLOT_MODE_MONO,
        .slot_mask      = I2S_STD_SLOT_LEFT,
        .ws_width       = 32,
        .ws_pol         = false,
        .bit_shift      = true,
        .left_align     = false,
        .big_endian     = false,
        .bit_order_lsb  = false
    },
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = (gpio_num_t)I2S_MIC_BCLK,
        .ws   = (gpio_num_t)I2S_MIC_WS,
        .dout = I2S_GPIO_UNUSED,
        .din  = (gpio_num_t)I2S_MIC_SD,
        .invert_flags = { false, false, false }
    }
};

/* =========================================================================
 * CONFIG I2S_NUM_1 — MAX98357A Speaker
 *
 * slot_mode = STEREO : MAX98357A bắt buộc cần stereo clock

 * ========================================================================= */
static i2s_std_config_t spk_config = {
    .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
    .slot_cfg = {
        .data_bit_width = I2S_DATA_BIT_WIDTH_16BIT,
        .slot_bit_width = I2S_SLOT_BIT_WIDTH_16BIT,
        .slot_mode      = I2S_SLOT_MODE_STEREO,
        .slot_mask      = I2S_STD_SLOT_BOTH,
        .ws_width       = 16,
        .ws_pol         = false,
        .bit_shift      = true,
        .left_align     = false,
        .big_endian     = false,
        .bit_order_lsb  = false
    },
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = (gpio_num_t)I2S_SPK_BCLK,
        .ws   = (gpio_num_t)I2S_SPK_WS,
        .dout = (gpio_num_t)I2S_SPK_SD,
        .din  = I2S_GPIO_UNUSED,
        .invert_flags = { false, false, false }
    }
};

/* =========================================================================
 * Xa bo dem DMA
 * Lap day bo dem gia tri 0x00 de ngat tin hieu am thanh
 * ========================================================================= */
void audio_flush_playback(void){
    if(!tx_handle) return;
    uint8_t silence_buf[2048] = {0};
    size_t written = 0;
    for (int i = 0; i < 12; i++){
        i2s_channel_write(tx_handle, silence_buf, sizeof(silence_buf), &written, pdMS_TO_TICKS(100));
    }
    ESP_LOGI(TAG, "Da xa sach DMA I2S (Zero-fill).");
}


// Watchdog la giam sat trang thai ung dung

/* =========================================================================
 * TASK STREAM MIC LÊN SERVER
 *
 * Với data_bit_width=16BIT, driver trả về int16_t trực tiếp.
 * Chỉ cần high-pass filter để cắt DC offset, không cần shift thủ công.
 * ========================================================================= */
static void audio_stream_task(void *pvParameters) {
    static int32_t raw_buf[AUDIO_BUFFER_SIZE / 4];   // đọc frame 32-bit nguyên
    static int16_t pcm_buf[AUDIO_BUFFER_SIZE / 4];   // output 16-bit sau extract
    size_t bytes_read = 0;
    int no_data_count = 0;
    static int32_t dc_x_prev = 0;
    static int32_t dc_y_prev = 0;

    ESP_LOGI(TAG, "Stream Task bắt đầu...");

    while (is_streaming) {
        if (!rx_handle || !mqtt_is_connected()) {
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }

        esp_err_t ret = i2s_channel_read(rx_handle, raw_buf, sizeof(raw_buf),
                                         &bytes_read, pdMS_TO_TICKS(300));

        if (ret == ESP_OK && bytes_read > 0) {
            no_data_count = 0;
            size_t sample_count = bytes_read / 4;

            for (size_t i = 0; i < sample_count; i++) {
                pcm_buf[i] = (int16_t)(raw_buf[i] >> 14);
            }

            // High-pass IIR — cắt DC offset còn lại
            for (size_t i = 0; i < sample_count; i++) {
                int32_t x  = (int32_t)pcm_buf[i];
                int32_t y  = x - dc_x_prev + (int32_t)(0.97f * (float)dc_y_prev);
                dc_x_prev  = x;
                dc_y_prev  = y;
                if (y >  32767) y =  32767;
                if (y < -32768) y = -32768;
                pcm_buf[i] = (int16_t)y;
            }

            int32_t sum = 0;
            for (size_t i = 0; i < sample_count; i++) sum += abs(pcm_buf[i]);
            int avg = (sample_count > 0) ? (int)(sum / sample_count) : 0;

            // VAD: chỉ publish khi có giọng nói thật
            if (avg > VAD_AMPLITUDE_THRESHOLD) {
                char topic[80];
                mqtt_proto_get_audio_up_topic(mqtt_get_device_id(), topic, sizeof(topic));
                mqtt_handler_publish(topic, (const char*)pcm_buf,
                                     (int)(sample_count * 2), 0, 0);
                // ESP_LOGI(TAG, "🎤 %d samples | Amplitude: %d 🔊", sample_count, avg);
            } else {
                // ESP_LOGD(TAG, "🎤 quiet | Amplitude: %d", avg);
            }

        } else {
            no_data_count++;
            ESP_LOGW(TAG, " i2s_read err=0x%x count=%d", ret, no_data_count);
            if (no_data_count >= 10) {
                ESP_LOGW(TAG, "Reset RX... Vi khong co du lieu");
                i2s_channel_disable(rx_handle);
                vTaskDelay(pdMS_TO_TICKS(50));
                i2s_channel_enable(rx_handle);
                no_data_count = 0;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
    audio_stream_task_handle = NULL;
    ESP_LOGI(TAG, "Stream Task dừng.");
    vTaskDelete(NULL);
}

/* =========================================================================
 * KHỞI TẠO I2S
 * NUM_0: INMP441 RX — GPIO 12/13/14
 * NUM_1: MAX98357A TX — GPIO 17/18/16
 * ========================================================================= */
esp_err_t audio_i2s_init(void) {
    ESP_LOGI(TAG, "Khởi tạo I2S — NUM_0(Mic) + NUM_1(Loa) - Bo dem RingBuffer");

    audio_ringbuf = xRingbufferCreate(RINGBUF_SIZE, RINGBUF_TYPE_BYTEBUF);
    if (!audio_ringbuf){
        ESP_LOGE(TAG, "KHONG TAO RINGBUF DUOC!");
        return ESP_FAIL;
    }

    i2s_chan_config_t mic_chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&mic_chan, NULL, &rx_handle));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle, &mic_config));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_handle));
    ESP_LOGI(TAG, "INMP441 (NUM_0 RX) sẵn sàng");

    i2s_chan_config_t spk_chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&spk_chan, &tx_handle, NULL));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle, &spk_config));
    ESP_ERROR_CHECK(i2s_channel_enable(tx_handle));
    ESP_LOGI(TAG, "MAX98357A (NUM_1 TX) sẵn sàng");

    // voice_watchdog_timer = xTimerCreate("VoiceWD", pdMS_TO_TICKS(5000),
    //                                     pdFALSE, 0, voice_watchdog_callback);
    // if (!voice_watchdog_timer) {
    //     ESP_LOGE(TAG, "Tạo Watchdog Timer thất bại!");
    //     return ESP_FAIL;
    // }

    // Chay TaskPlayBack ngam
    xTaskCreatePinnedToCore(audio_playback_task, "Audio_Playback",
                            TASK_STACK_AUDIO, NULL, TASK_PRIO_AUDIO, &audio_playback_task_handle, 1);

    ESP_LOGI(TAG, "Audio I2S khởi tạo hoàn tất!");
    return ESP_OK;
}

/* =========================================================================
 * ĐIỀU KHIỂN STREAM UP
 * ========================================================================= */
void audio_start_streaming(bool enable) {
    if (enable && !is_streaming) {
        is_streaming = true;
        // if (voice_watchdog_timer) {
        //     xTimerReset(voice_watchdog_timer, 0);
        //     xTimerStart(voice_watchdog_timer, 0);
        // }
        xTaskCreatePinnedToCore(audio_stream_task, "Audio_Stream_Up",
                                TASK_STACK_AUDIO, NULL, TASK_PRIO_AUDIO,
                                &audio_stream_task_handle, 1);
        ESP_LOGI(TAG, "Bắt đầu Stream Mic → Server");

    } else if (!enable && is_streaming) {
        is_streaming = false;
        // if (voice_watchdog_timer) xTimerStop(voice_watchdog_timer, 0);
        // audio_stream_task_handle = NULL;
        ESP_LOGI(TAG, "Dừng Stream Mic");
    }
}

bool audio_is_streaming(void) { return is_streaming; }

// void audio_reset_watchdog(void) {
//     if (voice_watchdog_timer) xTimerReset(voice_watchdog_timer, 0);
// }

/* =========================================================================
 * PHÁT ÂM THANH TỪ SERVER → LOA
 * Duplicate mono → stereo cho MAX98357A STEREO config
 * Nếu data bị chia ra thành từng chunk, nếu có chunk lẻ thì cần ghép nối byte thừa và chunk mới 
 * ========================================================================= */
static void audio_playback_task(void *pvParameters) {    
    // // Dùng bộ đệm tĩnh, tránh cấp phát quá nhiều vùng nhớ trên heap
    // // Cấp phát static 
    // // nhận tối đa MAX_STEREO_SAMPLES 1024 => 2048 byte mono => 4096 stero
    // static int16_t stereo[MAX_STEREO_SAMPLES * 2];
    // size_t sample_count = 0;
    // size_t data_idx = 0;

    size_t item_size;
    bool is_prebuffering = true;
    uint8_t leftover_byte = 0;
    bool has_leftover = false;

    static int16_t stereo[MAX_STEREO_SAMPLES * 2];

    ESP_LOGI(TAG, "Playback Task khởi động, chờ dữ liệu từ MQTT...");

    while (1){
        // Block task cho du lieu ringbuffer 
        // Khi cho du lieu do vao set timeout 1s
        // Khi nhan du lieu do vao set timout 10ms
        TickType_t wait_time = is_prebuffering ? pdMS_TO_TICKS(1000) : pdMS_TO_TICKS(10);
        uint8_t *item = (uint8_t*)xRingbufferReceive(audio_ringbuf, &item_size, wait_time);
        if (item != NULL){
            if (is_prebuffering){
                UBaseType_t free_size = xRingbufferGetCurFreeSize(audio_ringbuf);
                UBaseType_t used_size = RINGBUF_SIZE - free_size;

                if (used_size >= PREBUFFER_BYTES || is_playback_finished){
                    is_prebuffering = false;
                    ESP_LOGI(TAG, "Đã tích đủ %d bytes. Bắt đầu đẩy ra I2S.", used_size);
                    request_app_state(STATE_STREAM_DOWN); // Báo FSM để tắt Watchdog
                } else {
                    vRingbufferReturnItem(audio_ringbuf, (void *)item);
                    vTaskDelay(pdMS_TO_TICKS(10));
                    continue;
                }
            }

            // Mono -> Stero, Noi chunk
            size_t sample_count = 0;
            size_t data_idx = 0;
            // Neu co byte thua, ghep byte dau tien vao chunk 
            if (has_leftover && item_size > 0){
                // Chuẩn PCM Little Endian: Byte lẻlà LSB, Byte mới là MSB
                uint16_t sample = leftover_byte | ((uint16_t)item[0] << 8);
                int32_t v = (int16_t)sample * 2;
                if (v >  32767) v =  32767;
                if (v < -32768) v = -32768;
                
                stereo[0] = (int16_t)v; // LEFT
                stereo[1] = (int16_t)v; // RIGHT
                sample_count++;
                data_idx++; // Đã dùng mất 1 byte của chunk mới
                has_leftover = false;
            }

            // Xu li cac cap byte tiep theo
            while (data_idx + 1 < item_size) {
                // Nếu buffer đầy thì xả ra I2S trước để lấy chỗ trống
                if (sample_count >= MAX_STEREO_SAMPLES) {
                    size_t written = 0;
                    i2s_channel_write(tx_handle, stereo, sample_count * 2 * sizeof(int16_t), &written, pdMS_TO_TICKS(500));
                    sample_count = 0;
                }
        
                uint16_t sample = item[data_idx] | ((uint16_t)item[data_idx + 1] << 8);
                int32_t v = (int16_t)sample * 2;
                if (v >  32767) v =  32767;
                if (v < -32768) v = -32768;
                
                stereo[sample_count * 2]     = (int16_t)v;
                stereo[sample_count * 2 + 1] = (int16_t)v;
                sample_count++;
                data_idx += 2;
            }

            // Nếu chunk này lẻ, dư ra 1 byte cuối cùng
            if (data_idx < item_size) {
                leftover_byte = item[data_idx];
                has_leftover = true;
            }
            
            // Ghi Phan con lai ra DMA
            if (sample_count > 0) {
                size_t written = 0;
                esp_err_t ret = i2s_channel_write(tx_handle, stereo, sample_count * 2 * sizeof(int16_t), &written, pdMS_TO_TICKS(500));
            }

            // Giao trả lại khối nhớ cho FreeRTOS quản lý
            vRingbufferReturnItem(audio_ringbuf, (void *)item);
        } else {    // Khong co item
            if (!is_prebuffering){
                if (is_playback_finished){
                    ESP_LOGI(TAG, "Hoàn tất phát luồng TTS. Đang xả DMA...");
                    audio_flush_playback();
                    is_prebuffering = true;
                    request_app_state(STATE_IDLE); // Trả ESP32 về trạng thái ngủ
                } else {
                    // Co jitter 
                    ESP_LOGW(TAG, "Buffer Underrun! Loa bị đói dữ liệu do manglag.");
                    is_prebuffering = true; // Ép tích lũy lại Pre-buffer
                }
            }
        }
    }
}


/*
    API De mqtt day du lieu vao ringbuf
*/
void audio_ringbuf_feed(const uint8_t *data, size_t len){
    if (!audio_ringbuf || !data || len == 0) return;
    
    // Ném data vào bồn (Block tối đa 100ms nếu bồn đầy do loa phát không kịp)
    BaseType_t res = xRingbufferSend(audio_ringbuf, data, len, pdMS_TO_TICKS(100));
    if (res == pdTRUE) {
        is_playback_finished = false;
    } else {
        ESP_LOGE(TAG, "Tràn RingBuffer! Mất %d bytes âm thanh.", len);
    }
}

void audio_ringbuf_finish(void) {
    is_playback_finished = true;
}

/* =========================================================================
 * DỌN DẸP
 * ========================================================================= */
void audio_i2s_deinit(void) {
    audio_start_streaming(false);

    if (audio_playback_task_handle){
        vTaskDelete(audio_playback_task_handle);
        audio_playback_task_handle = NULL;
    }
    if (rx_handle) { i2s_channel_disable(rx_handle); i2s_del_channel(rx_handle); rx_handle = NULL; }
    if (tx_handle) { i2s_channel_disable(tx_handle); i2s_del_channel(tx_handle); tx_handle = NULL; }
    // if (voice_watchdog_timer) { xTimerDelete(voice_watchdog_timer, 0); voice_watchdog_timer = NULL; }
    ESP_LOGI(TAG, "I2S deinit hoàn tất.");
}

