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
#include "esp_psram.h"
#include "audio_psram.h"
#include <math.h>

uint8_t* psram_buffer = NULL;
size_t psram_write_pos = 0;

static const char *TAG = "AUDIO_I2S";

static volatile bool is_streaming = false;
static volatile bool is_stop_requested = false;
static int flush_chunks_remaining = 0;
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
    .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
    .gpio_cfg = {
        .mclk = I2S_GPIO_UNUSED,
        .bclk = (gpio_num_t)I2S_SPK_BCLK,
        .ws   = (gpio_num_t)I2S_SPK_WS,
        .dout = (gpio_num_t)I2S_SPK_SD,
        .din  = I2S_GPIO_UNUSED,
        .invert_flags = { false, false, false }
    }
};


void audio_test_beep_task(void *pvParameters) {
    ESP_LOGI("HW_TEST", "=== BẮT ĐẦU BÀI TEST AUTO BEEP (5s/lần) ===");
    
    // Đợi 2 giây cho hệ thống ổn định rồi mới bắt đầu test
    vTaskDelay(pdMS_TO_TICKS(2000)); 

    while(1) {
        // 1. Đảm bảo kho PSRAM đã được reset
        psram_write_pos = 0;

        // 2. Tạo sóng Sin 440Hz dài 0.5s (8000 mẫu = 16000 bytes)
        int sample_rate = 16000;
        int num_samples = 8000;
        float freq = 440.0;
        int volume = 4000; // Âm lượng vừa phải chống xé màng loa

        for (int i = 0; i < num_samples; i++) {
            float t = (float)i / sample_rate;
            int16_t sample = (int16_t)(sin(2.0 * M_PI * freq * t) * volume);
            
            // Ép thẳng 2 byte của sample vào PSRAM
            if (psram_buffer && (psram_write_pos + 2 <= 4*1024*1024)) {
                memcpy(&psram_buffer[psram_write_pos], &sample, 2);
                psram_write_pos += 2;
            }
        }

        // 3. Kích hoạt cờ cho Playback Task "hát"
        ESP_LOGI("HW_TEST", "Đã nạp xong %d bytes sóng Sin. Ra lệnh phát!", psram_write_pos);         
        is_playback_finished = true; 

        // 4. Ngủ 5 giây rồi lặp lại
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

void audio_request_stop(void) {
    is_stop_requested = true;
    // Giả sử mỗi vòng lặp đọc 20ms audio. 
    // Muốn vét đuôi 400ms thì cần đọc thêm 20 vòng nữa (400/20 = 20)
    flush_chunks_remaining = AUDIO_FLUSH_CHUNKS; 
}

// Watchdog la giam sat trang thai ung dung

/* =========================================================================
 * TASK STREAM MIC LÊN SERVER
 *
 * Với data_bit_width=16BIT, driver trả về int16_t trực tiếp.
 * Chỉ cần high-pass filter để cắt DC offset, không cần shift thủ công.
 * Có thuật toán VAD thay cho watchdog cũ, tự động biết điểm dừng 
 * ========================================================================= */
static void audio_stream_task(void *pvParameters) {
    static int32_t raw_buf[AUDIO_BUFFER_SIZE / 4];   // đọc frame 32-bit nguyên
    static int16_t pcm_buf[AUDIO_BUFFER_SIZE / 4];   // output 16-bit sau extract
    size_t bytes_read = 0;
    int no_data_count = 0;
    static int32_t dc_x_prev = 0;
    static int32_t dc_y_prev = 0;
    uint32_t silence_duration_ms = 0; 

    ESP_LOGI(TAG, "Stream Task bắt đầu...");

    // Dùng để lắng nghe liệu có ai đang thực sự nói không
    // Nếu nghe được có người nói, khoảng nghỉ giữa các từ phải được thu hẹp lại 
    bool has_started_speaking = false;

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
                int32_t y  = x - dc_x_prev + (int32_t)(HPF_COEFF * (float)dc_y_prev);
                dc_x_prev  = x;
                dc_y_prev  = y;
                if (y >  32767) y =  32767;
                if (y < -32768) y = -32768;
                pcm_buf[i] = (int16_t)y;
            }

            // Đẩy data lên server
            char topic[80];
            mqtt_proto_get_audio_up_topic(mqtt_get_device_id(), topic, sizeof(topic));
            mqtt_handler_publish(topic, (const char*)pcm_buf, (int)(sample_count * 2), 0, 0, 0);

            // Kiểm tra có yêu cầu dừng
            if (is_stop_requested) {
                if (flush_chunks_remaining > 0) {
                    flush_chunks_remaining--; // Đợi flush nốt dữ liệu, mấy từ cuối
                } else {
                    is_streaming = false;
                    is_stop_requested = false;
                    
                    ESP_LOGI(TAG, "Đã vét cạn Buffer. Gửi lệnh ngắt Server.");
                    
                    // Bắn lệnh Stop cho Server
                    char ctrl_topic[80];
                    mqtt_proto_get_audio_control_topic(mqtt_get_device_id(), ctrl_topic, sizeof(ctrl_topic));
                    cJSON* data = cJSON_CreateObject();
                    cJSON_AddStringToObject(data, "state", "stop_stream");
                    char* payload = mqtt_proto_build_standard_payload(data);
                    mqtt_handler_publish(ctrl_topic, payload, 0, 1, 0);
                    free(payload);

                    //Báo hiệu FSM chuyển trạng thái 
                    request_app_state(STATE_WAIT_SERVER);
                }
            }

            // Âm lượng trung bình 
            int32_t sum = 0;
            for (size_t i = 0; i < sample_count; i++) sum += abs(pcm_buf[i]);
            int avg = (sample_count > 0) ? (int)(sum / sample_count) : 0;

            // Tính thời lượng của chunk hiện tại theo mili-giây
            // Công thức: (Số mẫu * 1000) / Tần số lấy mẫu (16000)
            uint32_t chunk_time_ms = (sample_count * 1000) / 16000;
            if (avg > VAD_AMPLITUDE_THRESHOLD) {
                silence_duration_ms = 0; 
                // Neu day la cau dau tien
                if (!has_started_speaking) {
                    has_started_speaking = true;
                    ESP_LOGI(TAG, "Da bat duoc am thanh dau tien");
                }
            } else {
                silence_duration_ms += chunk_time_ms; 
            }
            uint32_t active_timeout = has_started_speaking ? VAD_SILENCE_TIMEOUT_MS : VAD_INITIAL_TIMEOUT_MS;
            // Nếu người dùng im lặng quá 1.5 giây VÀ chưa từng phát lệnh dừng
            if (silence_duration_ms >= active_timeout && !is_stop_requested) {
                if (has_started_speaking) ESP_LOGW(TAG, "Qua thoi gian cho noi, huy stream");
                else ESP_LOGI(TAG, "Da noi xong (Im lang %lu ms).", silence_duration_ms);
                
                // Kích hoạt cơ chế dừng mềm (để vét nốt cái đuôi Hang Time nếu cần)
                audio_request_stop();
                
                // Reset lại để tránh gọi kích hoạt liên tục trong các vòng lặp tiếp theo
                silence_duration_ms = 0; 
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

    // audio_ringbuf = xRingbufferCreate(RINGBUF_SIZE, RINGBUF_TYPE_BYTEBUF);
    // if (!audio_ringbuf){
    //     ESP_LOGE(TAG, "KHONG TAO RINGBUF DUOC!");
    //     return ESP_FAIL;
    // }

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
        xTaskCreatePinnedToCore(audio_stream_task, "Audio_Stream_Up",
                                TASK_STACK_AUDIO, NULL, TASK_PRIO_AUDIO,
                                &audio_stream_task_handle, 1);
        ESP_LOGI(TAG, "Bắt đầu Stream Mic → Server");

    } else if (!enable && is_streaming) {
        is_streaming = false;
        ESP_LOGI(TAG, "Dừng Stream Mic");
    }
}

bool audio_is_streaming(void) { return is_streaming; }


/* =========================================================================
 * PHÁT ÂM THANH TỪ SERVER → LOA
 * Duplicate mono → stereo cho MAX98357A STEREO config
 * Nếu data bị chia ra thành từng chunk, nếu có chunk lẻ thì cần ghép nối byte thừa và chunk mới 
 * ========================================================================= */
static void audio_playback_task(void *pvParameters) {    
    // Mảng 2048 chuẩn xác chống tràn RAM
    static int16_t stereo_buf[2048]; 
    ESP_LOGI(TAG, "Playback Task khởi động — Chế độ PSRAM Staging...");

    while (1){
        // CHỈ PHÁT KHI ĐÃ NHẬN ĐỦ LỆNH STOP TỪ MQTT VÀ CÓ DỮ LIỆU
        if (is_playback_finished && psram_write_pos > 0) {
            ESP_LOGI("PLAYBACK", "Bắt đầu phát từ PSRAM. Tổng: %d bytes", psram_write_pos);
            
            size_t read_pos = 0;
            size_t samples_played = 0;
            const size_t fade_samples = 1600; // Fade-in 100ms chống tiếng "Bụp"

            while (read_pos < psram_write_pos) {
                size_t remaining = psram_write_pos - read_pos;
                size_t bytes_to_read = (remaining > 2048) ? 2048 : remaining;
                size_t samples_to_read = bytes_to_read / 2;

                for (size_t i = 0; i < samples_to_read; i++) {
                    int16_t mono_sample;
                    memcpy(&mono_sample, &psram_buffer[read_pos + (i * 2)], 2);
                    
                    float volume_multiplier = 1.0; 

                    // ÁP DỤNG FADE-IN CHO ĐOẠN ĐẦU CÂU NÓI
                    if (samples_played < fade_samples) {
                        float fade_coeff = (float)samples_played / (float)fade_samples;
                        volume_multiplier *= fade_coeff;
                        samples_played++;
                    }

                    stereo_buf[i * 2]     = (int16_t)(mono_sample * volume_multiplier); 
                    stereo_buf[i * 2 + 1] = (int16_t)(mono_sample * volume_multiplier);
                }

                size_t written = 0;
                i2s_channel_write(tx_handle, stereo_buf, samples_to_read * 4, &written, portMAX_DELAY);
                read_pos += bytes_to_read;
            }
            
            // Phát xong: Reset kho và trạng thái
            psram_write_pos = 0; 
            is_playback_finished = false; 
            ESP_LOGI("PLAYBACK", "Đã phát xong luồng TTS, kho PSRAM đã trống.");
            
        } else {
            // CHẾ ĐỘ CHỜ (KHI KHÔNG CÓ LỆNH PHÁT)
            // Bơm số 0 liên tục vào DMA để giữ nhịp BCLK, triệt tiêu nhiễu rè nền
            memset(stereo_buf, 0, sizeof(stereo_buf));
            size_t written = 0;
            i2s_channel_write(tx_handle, stereo_buf, sizeof(stereo_buf), &written, portMAX_DELAY);
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

void audio_psram_init(void) {
    if (!psram_buffer) {
        psram_buffer = (uint8_t*)heap_caps_malloc(PSRAM_MAX_SIZE, MALLOC_CAP_SPIRAM);
    }
    psram_write_pos = 0;
}

void audio_psram_feed(const uint8_t* data, size_t len) {
    if (psram_buffer && (psram_write_pos + len < PSRAM_MAX_SIZE)) {
        memcpy(psram_buffer + psram_write_pos, data, len);
        psram_write_pos += len;
    }
}

/* =========================================================================
 * Xa bo dem DMA
 * Lap day bo dem gia tri 0x00 de ngat tin hieu am thanh
 * ========================================================================= */
void audio_flush_playback(void){
    if(!tx_handle) return;
    uint8_t silence_buf[2048] = {0};
    size_t written = 0;
    for (int i = 0; i < 32; i++){
        i2s_channel_write(tx_handle, silence_buf, sizeof(silence_buf), &written, pdMS_TO_TICKS(100));
    }
    ESP_LOGI(TAG, "Da xa sach DMA I2S (Zero-fill).");
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


bool audio_is_finished(void) {
    return is_playback_finished;
}

void audio_set_finished(bool value) {
    is_playback_finished = value;
    if (value == false){
        psram_write_pos = 0;
    }
}
