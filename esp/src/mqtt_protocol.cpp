#include "mqtt_protocol.h"
#include "time_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_random.h" // Dùng để gọi esp_random()

/* =========================================================================
 * THỰC THI BỘ TỪ ĐIỂN TOPIC
 * ========================================================================= */
void mqtt_proto_get_cmd_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/commands/#", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_audio_down_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/audio/stream_down", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_shadow_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/shadow/#", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_pong_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/telemetry/pong", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_status_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/status", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_time_req_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/events/time_request", PROJECT_PREFIX, device_id);
}

void mqtt_proto_get_audio_up_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/audio/stream_up", PROJECT_PREFIX, device_id);
}

/* =========================================================================
 * THỰC THI BỘ ĐÓNG GÓI PAYLOAD
 * ========================================================================= */
char* mqtt_proto_build_standard_payload(cJSON* data_obj) {
    // Tạo thư mục gốc (Root)
    cJSON* root = cJSON_CreateObject();
    
    // Tạo msg_id ngẫu nhiên (Ví dụ: msg_a1b2c3d4)
    char msg_id[24];
    snprintf(msg_id, sizeof(msg_id), "msg_%08lx", esp_random());
    cJSON_AddStringToObject(root, "msg_id", msg_id);
    
    // Đóng dấu thời gian chuẩn
    cJSON_AddNumberToObject(root, "timestamp", get_current_unix_timestamp());
    
    // Gắn phiên bản
    cJSON_AddStringToObject(root, "v", "1.0");
    
    // Gắn Data (Nếu null thì tạo cục data rỗng)
    if (data_obj != NULL) {
        cJSON_AddItemToObject(root, "data", data_obj); 
        // Lưu ý: data_obj lúc này đã bị root "nuốt". 
        // Khi xóa root thì data_obj cũng sẽ tự động được giải phóng khỏi RAM.
    } else {
        cJSON_AddItemToObject(root, "data", cJSON_CreateObject());
    }

    // In ra chuỗi string không format (để tiết kiệm băng thông mạng)
    char* payload_str = cJSON_PrintUnformatted(root);
    
    // Xóa cấu trúc cây JSON trong RAM
    cJSON_Delete(root);
    
    // Trả về chuỗi ký tự. HUYNH NHỚ PHẢI FREE CHUỖI NÀY SAU KHI DÙNG!
    return payload_str; 
}