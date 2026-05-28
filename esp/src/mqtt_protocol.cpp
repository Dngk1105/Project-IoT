#include "mqtt_protocol.h"
#include "time_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "esp_random.h" // Dùng để gọi esp_random()

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

void mqtt_proto_get_audio_control_topic(const char* device_id, char* out_buffer, size_t max_len) {
    snprintf(out_buffer, max_len, "%s/%s/events/audio_control", PROJECT_PREFIX, device_id);
}

char* mqtt_proto_build_standard_payload(cJSON* data_obj) {
    cJSON* root = cJSON_CreateObject();
    
    // header
    char msg_id[24];
    snprintf(msg_id, sizeof(msg_id), "msg_%08lx", esp_random());
    cJSON_AddStringToObject(root, "msg_id", msg_id);
    cJSON_AddNumberToObject(root, "timestamp", get_current_unix_timestamp());
    cJSON_AddStringToObject(root, "v", "1.0");
    
    if (data_obj != NULL) {
        cJSON_AddItemToObject(root, "data", data_obj); 
    } else {
        cJSON_AddItemToObject(root, "data", cJSON_CreateObject());
    }
    char* payload_str = cJSON_PrintUnformatted(root);
        cJSON_Delete(root);
    
    // Phai Delete sau khi dung
    return payload_str; 
}