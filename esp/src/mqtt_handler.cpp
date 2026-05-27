#include "mqtt_handler.h"
#include "config.h"
#include "time_core.h"
#include "audio_i2s.h"
#include "system_state.h"
#include "esp_log.h"
#include "esp_mac.h"
#include <string.h>
#include <stdio.h>
#include "cJSON.h"

static const char *TAG = "MQTT_HANDLER";

static esp_mqtt_client_handle_t mqtt_client = NULL;
static bool is_connected = false;

/* =========================================================================
 * BIẾN TOÀN CỤC THEO QUY CHUẨN MQTT
 * ========================================================================= */
static char device_id[13];           // MAC address viết liền, in thường (ví dụ: e072a1d6fa90)
static char client_id[32];           // esp32_<device_id>
static char status_topic[80];        // iot_schedule/<device_id>/status
volatile uint32_t last_server_pong_time = 0; // Kiểm tra kết nối tới server
static const char *lwt_payload_template = "{\"status\":\"offline\",\"reason\":\"connection_lost\",\"timestamp\":%lu}";

// Dùng để định tuyến các topic (han che goi tin bi bam nho)
typedef enum {
    MSG_TYPE_UNKNOWN = 0,
    MSG_TYPE_AUDIO_DOWN,
    MSG_TYPE_SYNC_SCHEDULE,
    MSG_TYPE_SHADOW,
    MSG_TYPE_EVENTS,
    MSG_TYPE_PONG
} mqtt_msg_type_t;
static mqtt_msg_type_t current_msg_type = MSG_TYPE_UNKNOWN;
static char current_topic[128] = {0}; // Lưu lại topic của chunk đầu tiên

/* =========================================================================
 * GETTER FUNCTIONS
 * ========================================================================= */
const char* mqtt_get_device_id(void) {
    return device_id;
}

esp_mqtt_client_handle_t mqtt_get_client(void) {
    return mqtt_client;
}

bool mqtt_is_connected(void) {
    return is_connected;
}

uint32_t mqtt_get_last_pong_time(void) { 
    return last_server_pong_time; 
}

/* =========================================================================
 * Tach cau truc JSON
    {
    "msg_id": "chuoi-dinh-danh-duy-nhat",
    "timestamp": 1779422760,
    "v": "1.0",
    "data": {
        // Dữ liệu linh hoạt tuỳ thuộc vào Topic
        }
    }
 * ========================================================================= */
static void parse_json_envelope(const char *payload, mqtt_msg_type_t msg_type){
    cJSON *root = cJSON_Parse(payload);
    if (root == NULL){
        ESP_LOGE(TAG, "PayLoad JSON khong hop le!!");
        return;
    }

    cJSON *data = cJSON_GetObjectItem(root, "data");
    if (data != NULL && cJSON_IsObject(data)){
        if (msg_type == MSG_TYPE_SYNC_SCHEDULE){
            ESP_LOGI(TAG, "Dong bo lich hoc, chuyen tiep qua local_storage...");
            // TODO: local_storage_save_schedule(cJSON_PrintUnformatted(data));
        }
        else if (msg_type == MSG_TYPE_SHADOW){
            ESP_LOGI(TAG, "Device shadow. Cap nhat ngoai vi");
            // TODO: device_shadow_update(data);
        }
        //.....
    }

    cJSON_Delete(root);
}

/* =========================================================================
 * CALLBACK XỬ LÝ SỰ KIỆN MQTT - THEO SƠ ĐỒ TUẦN TỰ
 * ========================================================================= */
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
        {
            // Cap nhat trang thai he thong
            ESP_LOGI(TAG, "MQTT Connected to Broker!");
            is_connected = true;
            set_sys_state(SYS_MQTT_OK); 
            
            /* Subscribe các topic theo đúng MQTT Convention */
            char cmd_topic[80], audio_down_topic[80], shadow_topic[80], events_topic[80], pong_topic[80];
            
            snprintf(cmd_topic,       sizeof(cmd_topic),       "iot_schedule/%s/commands/#", device_id);
            snprintf(audio_down_topic,sizeof(audio_down_topic),"iot_schedule/%s/audio/stream_down", device_id);
            snprintf(shadow_topic,    sizeof(shadow_topic),    "iot_schedule/%s/shadow/#", device_id);
            snprintf(pong_topic,    sizeof(pong_topic),    "iot_schedule/%s/telemetry/pong/#", device_id);


            mqtt_handler_subscribe(cmd_topic, 2);
            mqtt_handler_subscribe(audio_down_topic, 0);   // Audio stream ưu tiên tốc độ (QoS 0)
            mqtt_handler_subscribe(shadow_topic, 1);
            mqtt_handler_subscribe(events_topic, 1);
            mqtt_handler_subscribe(pong_topic, 0);

            ESP_LOGI(TAG, "Đã subscribe đầy đủ các topic chính");

            /* Publish Birth Message (Online) */
            char birth_payload[128];
            uint32_t current_time = get_current_unix_timestamp();
            snprintf(birth_payload, sizeof(birth_payload), 
                    "{\"status\":\"online\",\"timestamp\":%lu}", current_time);
            
            mqtt_handler_publish(status_topic, birth_payload, 0, 1, 1);
            ESP_LOGI(TAG, "Published Birth Message to %s", status_topic);
            break;
        }

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "MQTT Disconnected from Broker!");
            is_connected = false;

            if (get_sys_state() == SYS_MQTT_OK) 
                set_sys_state(SYS_WIFI_OK);
            break;

        case MQTT_EVENT_SUBSCRIBED:
            ESP_LOGI(TAG, "MQTT Subscribed successfully, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_DATA: {
            /*
            thư viện esp-mqtt khi nhận file lớn, nó băm nhỏ file ra (chống tràn RAM)
            Mảnh đầu tiên chứa toptic và các mảnh sau chứa data
            VD: I (14135) MQTT_HANDLER: MQTT Message Received
                I (14135) MQTT_HANDLER: TOPIC=iot_schedule/e072a1d6f1bc/audio/stream_down
                I (14135) MQTT_HANDLER: DATA len=4047 bytes
                I (14135) MQTT_HANDLER: [STREAM_DOWN] Nhận chunk audio TTS từ Server (4047 bytes)
                I (14195) MQTT_HANDLER: MQTT Message Received
                I (14195) MQTT_HANDLER: TOPIC=
                I (14195) MQTT_HANDLER: DATA len=224 bytes
            nếu so sánh strstr() vào event->topic chắc chắn sẽ trả về lỗi vì topic = null
            */
           /// Goi tin audio lon co the bi bam ra, can luong nhan data nay
           //static bool is_audio_stream = false;

           // Manh dau tien
           if (event->current_data_offset == 0){
               // Parse topic neu co
               // char safe_topic[128] = {0};   Doi sang current_topic
               int copy_len = (event->topic_len < sizeof(current_topic) - 1) ? event->topic_len : sizeof(current_topic) - 1;
               if (event->topic && event->topic_len > 0){
                   strncpy(current_topic, event->topic, copy_len);
               } 
               ESP_LOGI(TAG, "MQTT Message Received | Topic: %s |Tổng dung lượng: %d bytes", current_topic, event->total_data_len);

               // Xử lý theo Sơ đồ Tuần tự
               // Lệnh đồng bộ lịch từ Server
               if (strstr(event->topic, "/commands/sync_schedule") != NULL) {
                    current_msg_type = MSG_TYPE_SYNC_SCHEDULE;
                    ESP_LOGI(TAG, "[SYNC_SCHEDULE] Nhận lệnh đồng bộ lịch từ Server");
                    request_app_state(STATE_SYNCING);
                   // TODO: Gọi hàm local_storage_sync_schedule(...)
                   // Sau khi xử lý xong → gửi Application ACK với Correlation Data
               }

               // Nhận Audio Stream từ Server (TTS)
               else if (strstr(event->topic, "/audio/stream_down") != NULL) {
                    ESP_LOGI(TAG, "[STREAM_DOWN] Nhận chunk audio TTS từ Server (%d bytes)", event->data_len);
                    current_msg_type = MSG_TYPE_AUDIO_DOWN;
               }
               
               // Lệnh điều khiển Device Shadow
                else if (strstr(event->topic, "/shadow/") != NULL) {
                    current_msg_type = MSG_TYPE_SHADOW;
                    ESP_LOGI(TAG, "[SHADOW] Nhận lệnh điều khiển ngoại vi");
                    // TODO: device_shadow_process_command(...)
                }

                else if (strstr(current_topic, "/telemetry/pong") != NULL) {
                    current_msg_type = MSG_TYPE_PONG;
                    ESP_LOGI(TAG, "[EVENT] Nhận event từ Server");
                }
                
                else {
                    current_msg_type = MSG_TYPE_UNKNOWN;
                }
            }

            switch(current_msg_type){
                case MSG_TYPE_AUDIO_DOWN:
                    //Du lieu nhi phan tho, parse vao ring buffer
                    if (event->data_len > 0){
                        audio_ringbuf_feed((const uint8_t*)event->data, event->data_len);
                        ESP_LOGI(TAG, "Xa %d bytes vao Ringbuffer", event->data_len);
                    }
                    break;
                
                case MSG_TYPE_PONG:
                    // Trang thai ket noi toi server
                    last_server_pong_time = get_current_unix_timestamp();
                    ESP_LOGD(TAG, "Nhận PONG từ Server lúc %lu", last_server_pong_time);
                    break;

                case MSG_TYPE_SYNC_SCHEDULE:
                case MSG_TYPE_SHADOW:
                    // Cac goi tin JSON. Gia su goi < MQTT_BUFFER_IN_SIZE (Khong bam)
                    // Neu gui goi tin lon thi can noi vao 
                    if (event->current_data_offset == 0 && event->data_len == event->total_data_len){
                        char *json_str = (char*)malloc(event->data_len + 1);
                        if (json_str) {
                            memcpy(json_str, event->data, event->data_len);
                            json_str[event->data_len] = '\0';
                            parse_json_envelope(json_str, current_msg_type);
                            free(json_str);
                        }
                    } else{
                        ESP_LOGW(TAG, "JSON bi bam nho, chua xu li duoc");
                    }
                    break;
                default:
                    break;
            }

            // Don dep neu nhan manh cuoi
            if (event->current_data_offset + event->data_len >= event->total_data_len){
                if (current_msg_type == MSG_TYPE_AUDIO_DOWN){
                    ESP_LOGI(TAG, "Đã nhận trọn vẹn file Audio TTS.");
                    // Báo cho Audio Task biết để xả nốt loa
                    audio_ringbuf_finish();
                }
                current_msg_type = MSG_TYPE_UNKNOWN;
            }
            break;
        }
        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT Error Occurred");
            break;

        default:
            ESP_LOGD(TAG, "Other MQTT event id: %d", event->event_id);
            break;
    }
}

/* =========================================================================
 * KHỞI TẠO MQTT CLIENT (v5.0 + Persistent Session)
 * ========================================================================= */
void mqtt_handler_init(void) {
    // Lấy địa chỉ MAC để tạo Device ID theo convention
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(device_id, sizeof(device_id), "%02x%02x%02x%02x%02x%02x", 
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    snprintf(client_id, sizeof(client_id), "esp32_%s", device_id);
    snprintf(status_topic, sizeof(status_topic), "iot_schedule/%s/status", device_id);

    ESP_LOGI(TAG, "Configuring MQTT v5.0 - Client ID: %s", client_id);

    esp_mqtt_client_config_t mqtt_cfg = {};

    mqtt_cfg.broker.address.uri = MQTT_BROKER_URI;
    mqtt_cfg.session.protocol_ver = MQTT_PROTOCOL_V_5;
    mqtt_cfg.session.keepalive = MQTT_KEEPALIVE_SEC;

    // Tăng buffer để hỗ trợ audio chunk lớn
    mqtt_cfg.buffer.size = MQTT_BUFFER_IN_SIZE;
    mqtt_cfg.buffer.out_size = MQTT_BUFFER_OUT_SIZE;

    // Persistent Session theo Convention
    mqtt_cfg.session.disable_clean_session = true;

    // Last Will and Testament (LWT)
    char lwt_payload[128];
    uint32_t ts = get_current_unix_timestamp();
    snprintf(lwt_payload, sizeof(lwt_payload), lwt_payload_template, ts);

    mqtt_cfg.session.last_will.topic = status_topic;
    mqtt_cfg.session.last_will.msg = lwt_payload;
    mqtt_cfg.session.last_will.msg_len = strlen(lwt_payload);
    mqtt_cfg.session.last_will.qos = 1;
    mqtt_cfg.session.last_will.retain = 1;

    mqtt_cfg.credentials.client_id = client_id;

    mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    esp_mqtt_client_register_event(mqtt_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL);

    ESP_LOGI(TAG, "MQTT Handler đã được khởi tạo thành công (Device ID: %s)", device_id);
}

/* =========================================================================
 * BẮT ĐẦU KẾT NỐI MQTT
 * ========================================================================= */
void mqtt_handler_start(void) {
    if (mqtt_client != NULL) {
        ESP_LOGI(TAG, "Starting MQTT Client...");
        esp_mqtt_client_start(mqtt_client);
    } else {
        ESP_LOGE(TAG, "MQTT Client not initialized!");
    }
}

/* =========================================================================
 * HÀM PUBLISH
 * ========================================================================= */
int mqtt_handler_publish(const char *topic, const char* payload, int len, int qos, int retain) {
    if (!mqtt_is_connected()) {
        ESP_LOGW(TAG, "Bỏ qua Publish: MQTT đang mất kết nối. Topic: %s", topic);
        return -1;
    }

    if (mqtt_client == NULL || topic == NULL || payload == NULL) {
        ESP_LOGE(TAG, "Tham số Publish không hợp lệ");
        return -1;
    }

    if (len <= 0) {
        len = strlen(payload);
    }

    int msg_id = esp_mqtt_client_publish(mqtt_client, topic, payload, len, qos, retain);
    
    if (msg_id < 0) {
        ESP_LOGE(TAG, "Gửi tin nhắn thất bại lên topic: %s", topic);
    } else {
        ESP_LOGI(TAG, "Đã gửi tin nhắn thành công, msg_id=%d, Topic=%s", msg_id, topic);
    }

    return msg_id;
}

/* =========================================================================
 * HÀM SUBSCRIBE
 * ========================================================================= */
int mqtt_handler_subscribe(const char *topic, int qos) {
    if (!mqtt_is_connected()) {
        ESP_LOGW(TAG, "Bỏ qua Subscribe: MQTT đang mất kết nối. Topic: %s", topic);
        return -1;
    }

    if (mqtt_client == NULL || topic == NULL) {
        ESP_LOGE(TAG, "Tham số Subscribe không hợp lệ");
        return -1;
    }

    int msg_id = esp_mqtt_client_subscribe(mqtt_client, topic, qos);
    return msg_id;
}
