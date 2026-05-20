#ifndef CONFIG_H
#define CONFIG_H

/* =========================================================================
 * THÔNG SỐ MẠNG (WIFI)
 * ========================================================================= */
#define WIFI_SSID               "TP-Link_BA00"
#define WIFI_PASSWORD           "98755370"
#define WIFI_MAX_RETRY          5       // Số lần thử kết nối lại trước khi reset module

/* =========================================================================
 * THÔNG SỐ MQTT BROKER
 * ========================================================================= */
#define MQTT_BROKER_URI         "mqtt://192.168.0.101:1883" // IP của Server nội bộ
// #define MQTT_USERNAME        "admin"                    
// #define MQTT_PASSWORD        "secret"
#define MQTT_KEEPALIVE_SEC      60                          // Chu kỳ gửi Pingreq

/* =========================================================================
 * BẢN ĐỒ CHÂN KẾT NỐI (GPIO MAPPING)
 * ========================================================================= */
// --- Ngoại vi cơ bản ---
#define PIN_BTN_WAKE            0       // Nút bấm vật lý (Boot button)

// --- I2S Audio (Mic & Speaker) ---
#define I2S_MIC_WS              25      // L/R Clock (Word Select)
#define I2S_MIC_SCK             26      // Bit Clock (BCLK)
#define I2S_MIC_SD              27      // Serial Data (DIN)

#define I2S_SPK_WS              19
#define I2S_SPK_SCK             21
#define I2S_SPK_SD              22

/* =========================================================================
 * CẤU HÌNH AUDIO & XỬ LÝ GIỌNG NÓI
 * ========================================================================= */
#define AUDIO_SAMPLE_RATE       16000   // 16kHz chuẩn cho nhận diện giọng nói (STT)
#define AUDIO_CHANNELS          1       // Mono
#define AUDIO_BITS_PER_SAMPLE   16      // 16-bit
#define VAD_THRESHOLD_DB        -40.0f  // Ngưỡng decibel để kích hoạt Voice Activity Detection

/* =========================================================================
 * THỜI GIAN & ĐỒNG BỘ (NTP)
 * ========================================================================= */
#define NTP_SERVER_1            "pool.ntp.org"
#define NTP_SERVER_2            "time.nist.gov"
#define TIME_SYNC_INTERVAL_MS   3600000 // Đồng bộ lại mỗi 1 tiếng (1000 * 60 * 60)
#define TIMEZONE_OFFSET_SEC     25200   // Múi giờ VN (UTC+7) = 7 * 60 * 60

/* =========================================================================
 * TÀI NGUYÊN HỆ THỐNG (FREERTOS TASKS)
 * Định nghĩa bộ nhớ RAM (Stack) và mức độ ưu tiên (Priority) cho các Task ngầm.
 * ========================================================================= */
#define TASK_STACK_MQTT         4096
#define TASK_PRIO_MQTT          5       // Ưu tiên trung bình

#define TASK_STACK_AUDIO        8192    // Xử lý âm thanh cần nhiều RAM
#define TASK_PRIO_AUDIO         10      // Ưu tiên rất cao để không bị giật tiếng

#define TASK_STACK_PERIPHERALS  2048
#define TASK_PRIO_PERIPHERALS   3       // Ưu tiên thấp (Chớp đèn, còi)

#endif // CONFIG_H