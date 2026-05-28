#pragma once

#include <stdint.h>
#include <stddef.h>
#include "cJSON.h"

#ifdef __cplusplus
extern "C" {
#endif

// Hằng số tiền tố (Khớp 100% với Server)
#define PROJECT_PREFIX "iot_schedule"

/* =========================================================================
 * BỘ TỪ ĐIỂN TOPIC
 * Sinh chuỗi topic an toàn vào buffer được cấp phát sẵn
 * ========================================================================= */
void mqtt_proto_get_cmd_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_audio_down_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_shadow_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_pong_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_status_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_audio_up_topic(const char* device_id, char* out_buffer, size_t max_len);
void mqtt_proto_get_audio_control_topic(const char* device_id, char* out_buffer, size_t max_len);

// Topic dùng để ESP32 Publish lên Server
void mqtt_proto_get_time_req_topic(const char* device_id, char* out_buffer, size_t max_len);


/* =========================================================================
 * BỘ ĐÓNG GÓI PAYLOAD (ENVELOPE BUILDER)
 * ========================================================================= */
/**
 * Đóng gói đối tượng cJSON data vào Envelope chuẩn (có msg_id, timestamp, v).
 * LƯU Ý: Hàm này trả về một chuỗi con trỏ (char*) cấp phát động.
 * NHẤT ĐỊNH PHẢI GỌI free(payload_str) SAU KHI PUBLISH XONG!
 */
char* mqtt_proto_build_standard_payload(cJSON* data_obj);

#ifdef __cplusplus
}
#endif