#include "mqtt_handler.h"
#include "config.h"       
#include "time_core.h"   
#include "esp_log.h"
#include "esp_mac.h"      // Thư viện lấy địa chỉ MAC trên ESP-IDF v5/v6
#include <string.h>
#include <stdio.h>

static const char *TAG = "MQTT_HANDLER";

static esp_mqtt_client_handle_t mqtt_client = NULL;
static bool is_connected = false;

// Các biến lưu trữ Topic và Client ID toàn cục để vòng đời cấu hình không bị hủy
static char device_mac_str[13];
static char client_id[24];
static char status_topic[64];

// Payload cho LWT (Last Will and Testament) - QoS 1, Retain = True
static const char *lwt_payload = "{\"status\":\"offline\",\"reason\":\"connection_lost\"}";

/* =========================================================================
 * CALLBACK XỬ LÝ SỰ KIỆN MQTT
 * Tham khao: https://github.com/espressif/esp-idf/blob/v5.0/examples/protocols/mqtt/tcp/main/app_main.c
 * ========================================================================= */
static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    
    switch ((esp_mqtt_event_id_t)event_id) {
        case MQTT_EVENT_CONNECTED:
        {
            ESP_LOGI(TAG, "MQTT Connected to Broker!");
            is_connected = true;
                // Đăng ký các topic liên quan/gửi tới nó
                char cmd_topic[64];
                snprintf(cmd_topic, sizeof(cmd_topic), "device/%s/#", device_mac_str);
                mqtt_handler_subscribe(cmd_topic, 1);
    
                //Publish Birth Message ngay khi kết nối
                char birth_payload[128];
                // Lấy timestamp từ NTP/RTC qua time_core.h
                uint32_t current_time = get_current_unix_timestamp(); 
                snprintf(birth_payload, sizeof(birth_payload), "{\"status\":\"online\",\"timestamp\":%lu}", current_time);
                
                // Publish Birth Message (topic, payload, len, qos, retain)
                mqtt_handler_publish(status_topic, birth_payload, 0, 1, 1);
            ESP_LOGI(TAG, "Published Birth Message to %s", status_topic);
            break;
        }

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "MQTT Disconnected from Broker!");
            is_connected = false;
            break;

        case MQTT_EVENT_SUBSCRIBED:
            ESP_LOGI(TAG, "MQTT Subscribed, msg_id=%d", event->msg_id);
            break;

        case MQTT_EVENT_DATA:
            ESP_LOGI(TAG, "MQTT Message Received");
            ESP_LOGI(TAG, "TOPIC=%.*s", event->topic_len, event->topic);
            ESP_LOGI(TAG, "DATA=%.*s", event->data_len, event->data);
            
            // TODO: Bóc tách Topic, đẩy vào Queue xử lý lệnh (Còi, Đèn, Snooze)
            break;

        case MQTT_EVENT_ERROR:
            ESP_LOGE(TAG, "MQTT Error Occurred");
            break;

        default:
            ESP_LOGD(TAG, "Other MQTT event id:%d", event->event_id);
            break;
    }
}

/* =========================================================================
 * KHỞI TẠO VÀ CẤU HÌNH (Chuẩn ESP-IDF v5/v6)
 * ========================================================================= */
void mqtt_handler_init(void) {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    snprintf(device_mac_str, sizeof(device_mac_str), "%02x%02x%02x%02x%02x%02x", 
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

    // Khởi tạo Client ID và Status Topic
    snprintf(client_id, sizeof(client_id), "esp32_%s", device_mac_str);
    snprintf(status_topic, sizeof(status_topic), "device/%s/status", device_mac_str);

    ESP_LOGI(TAG, "Configuring MQTT v5.0 Client ID: %s", client_id);

    // Cấu trúc cấu hình MQTT cho ESP-IDF v5+
    esp_mqtt_client_config_t mqtt_cfg = {};
    
    // Cấu hình Broker
    mqtt_cfg.broker.address.uri = MQTT_BROKER_URI;
    
    // Cấu hình Session & Protocol
    mqtt_cfg.session.protocol_ver = MQTT_PROTOCOL_V_5;
    mqtt_cfg.session.keepalive = 60; //
    
    // Đăng ký Last Will and Testament (LWT)
    mqtt_cfg.session.last_will.topic = status_topic;
    mqtt_cfg.session.last_will.msg = lwt_payload;
    mqtt_cfg.session.last_will.msg_len = strlen(lwt_payload);
    mqtt_cfg.session.last_will.qos = 1;
    mqtt_cfg.session.last_will.retain = 1;

    // Cấu hình Credentials
    mqtt_cfg.credentials.client_id = client_id;
    // Nếu có username/password thì khai báo:
    // mqtt_cfg.credentials.username = MQTT_USERNAME;
    // mqtt_cfg.credentials.authentication.password = MQTT_PASSWORD;

    // Khởi tạo Client
    mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    
    // Đăng ký Callback
    esp_mqtt_client_register_event(mqtt_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL);

}

void mqtt_handler_start(void) {
    if (mqtt_client != NULL) {
        ESP_LOGI(TAG, "Starting MQTT Client...");
        esp_mqtt_client_start(mqtt_client);
    } else {
        ESP_LOGE(TAG, "MQTT Client not initialized!");
    }
}

/* =========================================================================
 * THIẾT LẬP CÁC HÀM PUB/SUB
 * ========================================================================= */

 int mqtt_handler_publish(const char *topic, const char* payload, int len, int qos, int retain){
    if (!mqtt_is_connected()) {
        ESP_LOGW(TAG, "Bỏ qua Publish: MQTT đang mất kết nối. Topic: %s", topic);
        return -1;
    }

    if (mqtt_client == NULL || topic == NULL || payload == NULL) {
        ESP_LOGE(TAG, "Tham số Publish không hợp lệ (Client, Topic hoặc Payload bị NULL)");
        return -1;
    }
    //Kiểm tra len payload
    if (len <= 0) {
        len = strlen(payload);
    }

    //API gốc của ESP-IDF
    int msg_id = esp_mqtt_client_publish(mqtt_client, topic, payload, len, qos, retain);
    
    if (msg_id < 0) {
        ESP_LOGE(TAG, "Gửi tin nhắn thất bại lên topic: %s", topic);
    } else {
        ESP_LOGI(TAG, "Đã gửi tin nhắn thành công, msg_id=%d, Topic=%s", msg_id, topic);
    }

    return msg_id;
}
int mqtt_handler_subscribe(const char *topic, int qos){
    if (!mqtt_is_connected()){
        ESP_LOGW(TAG, "Bỏ qua Subscribe: MQTT đang mất kết nối. Topic: %s", topic);
        return -1;
    }

    if (mqtt_client == NULL || topic == NULL) {
        ESP_LOGE(TAG, "Tham số Subscribe không hợp lệ (Client hoặc Topic bị NULL)");
        return -1;
    }

    int msg_id = esp_mqtt_client_subscribe(mqtt_client, topic, qos);
    
    if (msg_id < 0) {
        ESP_LOGE(TAG, "Đăng ký theo dõi thất bại topic: %s", topic);
    } else {
        ESP_LOGI(TAG, "Gửi yêu cầu đăng ký thành công, msg_id=%d, Topic=%s", msg_id, topic);
    }

    return msg_id;
}

bool mqtt_is_connected(void) {
    return is_connected;
}

esp_mqtt_client_handle_t mqtt_get_client(void) {
    return mqtt_client;
}