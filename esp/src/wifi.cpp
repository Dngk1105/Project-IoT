#include "wifi.h"

/// string.h dùng cho strcpy()
#include <string.h>

/// FreeRTOS
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

/// ESP-IDF WiFi
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"

/// NVS Flash
#include "nvs_flash.h"



/// ======================================================
/// WIFI CONFIG
/// ======================================================

/// Đổi thành WiFi thật của bạn
#define WIFI_SSID      "DangDat"

/// Password WiFi
#define WIFI_PASSWORD  "15042005"

/// ======================================================



/// Tag dùng cho ESP_LOGI()
static const char *TAG = "WIFI";



/// Event group để đồng bộ trạng thái WiFi
static EventGroupHandle_t wifi_event_group;



/// Bit báo đã connect WiFi
#define WIFI_CONNECTED_BIT BIT0



/// ======================================================
/// WIFI EVENT HANDLER
///
/// Hàm callback được ESP-IDF gọi khi:
/// - WiFi start
/// - disconnect
/// - nhận IP
/// ======================================================
static void wifi_event_handler(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data
) {

    /// --------------------------------------------------
    /// WIFI START
    /// --------------------------------------------------
    if (event_base == WIFI_EVENT &&
        event_id == WIFI_EVENT_STA_START) {

        ESP_LOGI(TAG, "Connecting to WiFi...");

        /// Bắt đầu connect router
        esp_wifi_connect();
    }

    /// --------------------------------------------------
    /// WIFI DISCONNECTED
    /// --------------------------------------------------
    else if (event_base == WIFI_EVENT &&
             event_id == WIFI_EVENT_STA_DISCONNECTED) {

        ESP_LOGW(TAG, "WiFi disconnected");

        ESP_LOGI(TAG, "Retry connecting...");

        /// Tự reconnect
        esp_wifi_connect();
    }

    /// --------------------------------------------------
    /// GOT IP
    /// --------------------------------------------------
    else if (event_base == IP_EVENT &&
             event_id == IP_EVENT_STA_GOT_IP) {

        /// Lấy thông tin IP
        ip_event_got_ip_t *event =
            (ip_event_got_ip_t *) event_data;

        ESP_LOGI(
            TAG,
            "GOT IP: " IPSTR,
            IP2STR(&event->ip_info.ip)
        );

        /// Set bit báo đã connect thành công
        xEventGroupSetBits(
            wifi_event_group,
            WIFI_CONNECTED_BIT
        );
    }
}



/// ======================================================
/// WIFI INIT
///
/// Hàm khởi tạo toàn bộ WiFi subsystem
/// ======================================================
void wifi_init(void)
{
    /// --------------------------------------------------
    /// INIT NVS
    /// --------------------------------------------------
    esp_err_t ret = nvs_flash_init();

    /// Nếu NVS lỗi
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES ||
        ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {

        /// Xóa NVS
        nvs_flash_erase();

        /// Init lại
        nvs_flash_init();
    }



    /// --------------------------------------------------
    /// NETWORK INTERFACE
    /// --------------------------------------------------
    esp_netif_init();



    /// --------------------------------------------------
    /// EVENT LOOP
    /// --------------------------------------------------
    esp_event_loop_create_default();



    /// --------------------------------------------------
    /// CREATE WIFI STATION
    /// --------------------------------------------------
    esp_netif_create_default_wifi_sta();



    /// --------------------------------------------------
    /// WIFI INIT CONFIG
    /// --------------------------------------------------
    wifi_init_config_t cfg =
        WIFI_INIT_CONFIG_DEFAULT();

    esp_wifi_init(&cfg);



    /// --------------------------------------------------
    /// CREATE EVENT GROUP
    /// --------------------------------------------------
    wifi_event_group =
        xEventGroupCreate();



    /// --------------------------------------------------
    /// REGISTER WIFI EVENT
    /// --------------------------------------------------
    esp_event_handler_instance_register(
        WIFI_EVENT,
        ESP_EVENT_ANY_ID,
        &wifi_event_handler,
        NULL,
        NULL
    );



    /// --------------------------------------------------
    /// REGISTER IP EVENT
    /// --------------------------------------------------
    esp_event_handler_instance_register(
        IP_EVENT,
        IP_EVENT_STA_GOT_IP,
        &wifi_event_handler,
        NULL,
        NULL
    );



    /// --------------------------------------------------
    /// WIFI CONFIG
    /// --------------------------------------------------
    wifi_config_t wifi_config = {};



    /// Copy SSID
    strcpy(
        (char *)wifi_config.sta.ssid,
        WIFI_SSID
    );



    /// Copy password
    strcpy(
        (char *)wifi_config.sta.password,
        WIFI_PASSWORD
    );



    /// --------------------------------------------------
    /// WIFI MODE
    /// --------------------------------------------------
    esp_wifi_set_mode(WIFI_MODE_STA);



    /// --------------------------------------------------
    /// APPLY WIFI CONFIG
    /// --------------------------------------------------
    esp_wifi_set_config(
        WIFI_IF_STA,
        &wifi_config
    );



    /// --------------------------------------------------
    /// START WIFI
    /// --------------------------------------------------
    esp_wifi_start();

    ESP_LOGI(TAG, "wifi_init finished");



    /// --------------------------------------------------
    /// WAIT UNTIL CONNECTED
    /// --------------------------------------------------
    xEventGroupWaitBits(
        wifi_event_group,
        WIFI_CONNECTED_BIT,
        pdFALSE,
        pdTRUE,
        portMAX_DELAY
    );



    ESP_LOGI(TAG, "WIFI CONNECTED SUCCESS");
}