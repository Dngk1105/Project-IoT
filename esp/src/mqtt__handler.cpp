#include "mqtt_handler.h"

#include <string.h>

/// ESP MQTT
#include "mqtt_client.h"

/// ESP LOG
#include "esp_log.h"



/// ======================================================
/// TAG
/// ======================================================
static const char *TAG = "MQTT";



/// ======================================================
/// MQTT CLIENT HANDLE
/// ======================================================
static esp_mqtt_client_handle_t client = NULL;



/// ======================================================
/// MQTT DATA HANDLER
///
/// Hàm xử lý dữ liệu MQTT nhận được
/// ======================================================
static void mqtt_data_handler(
    const char *topic,
    const char *data,
    int data_len
) {

    /// Buffer chứa payload
    char msg[128] = {0};



    /// Copy payload
    memcpy(msg, data, data_len);



    /// In topic
    ESP_LOGI(TAG, "TOPIC: %s", topic);



    /// In payload
    ESP_LOGI(TAG, "DATA : %s", msg);



    /// ==================================================
    /// TODO:
    /// xử lý command ở đây
    /// ==================================================
}



/// ======================================================
/// MQTT EVENT HANDLER
///
/// Callback do ESP-IDF gọi
/// ======================================================
static void mqtt_event_handler(
    void *handler_args,
    esp_event_base_t base,
    int32_t event_id,
    void *event_data
) {

    esp_mqtt_event_handle_t event =
        (esp_mqtt_event_handle_t) event_data;



    switch ((esp_mqtt_event_id_t)event_id) {

        /// ------------------------------------------------
        /// MQTT CONNECTED
        /// ------------------------------------------------
        case MQTT_EVENT_CONNECTED:

            ESP_LOGI(TAG, "MQTT CONNECTED");



            /// Subscribe topic command
            esp_mqtt_client_subscribe(
                client,
                "hust_iot/cmd",
                1
            );

            ESP_LOGI(TAG, "SUBSCRIBED");

            break;



        /// ------------------------------------------------
        /// MQTT DISCONNECTED
        /// ------------------------------------------------
        case MQTT_EVENT_DISCONNECTED:

            ESP_LOGW(TAG, "MQTT DISCONNECTED");

            break;



        /// ------------------------------------------------
        /// MQTT DATA RECEIVED
        /// ------------------------------------------------
        case MQTT_EVENT_DATA:

            mqtt_data_handler(
                event->topic,
                event->data,
                event->data_len
            );

            break;



        default:
            break;
    }
}



/// ======================================================
/// MQTT INIT
/// ======================================================
void mqtt_init(void)
{
    /// MQTT config
    esp_mqtt_client_config_t mqtt_cfg = {};



    /// ==================================================
    /// ĐỔI THÀNH IP MÁY TÍNH CHẠY DOCKER
    /// ==================================================
    mqtt_cfg.broker.address.uri =
        "mqtt://192.168.1.2:1883";



    /// Create client
    client = esp_mqtt_client_init(&mqtt_cfg);



    /// Register callback event
    esp_mqtt_client_register_event(
        client,
        MQTT_EVENT_ANY,
        mqtt_event_handler,
        NULL
    );



    /// Start MQTT
    esp_mqtt_client_start(client);

    ESP_LOGI(TAG, "MQTT START");
}



/// ======================================================
/// MQTT SEND
///
/// Publish message lên broker
/// ======================================================
int mqtt_send(
    const char *topic,
    const char *data
) {

    /// Kiểm tra client
    if (client == NULL) {

        ESP_LOGE(TAG, "CLIENT NULL");

        return -1;
    }



    /// Publish message
    int msg_id = esp_mqtt_client_publish(
        client,
        topic,
        data,
        0,
        1,
        0
    );



    /// Publish fail
    if (msg_id == -1) {

        ESP_LOGE(TAG, "PUBLISH FAILED");

        return -1;
    }



    ESP_LOGI(TAG, "PUBLISH SUCCESS");

    return 0;
}