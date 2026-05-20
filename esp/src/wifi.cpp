#include "wifi_core.h"
#include "config.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

static const char *TAG = "WIFI_CORE";

// Khai báo Event Group
static EventGroupHandle_t wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

static int retry_num = 0;

// Callback xử lý sự kiện WiFi và IP
static void event_handler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } 
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (retry_num < WIFI_MAX_RETRY) {
            esp_wifi_connect();
            retry_num++;
            ESP_LOGW(TAG, "Mất kết nối. Đang thử lại (%d/%d)...", retry_num, WIFI_MAX_RETRY);
        } else {
            ESP_LOGE(TAG, "Kết nối thất bại sau %d lần. Cần khởi động lại hoặc chạy offline.", WIFI_MAX_RETRY);
            // Tùy chọn: esp_restart(); 
        }
        xEventGroupClearBits(wifi_event_group, WIFI_CONNECTED_BIT);
    } 
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Kết nối thành công! Lấy được IP: " IPSTR, IP2STR(&event->ip_info.ip));
        retry_num = 0;
        
        // Đánh thức tất cả các Task đang chờ WiFi (Ví dụ: MQTT, NTP)
        xEventGroupSetBits(wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

void wifi_init_sta(void) {
    // NVS là BẮT BUỘC để driver WiFi lưu thông số Calibration RF
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    // Đăng ký Event Handler
    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &event_handler, NULL, &instance_got_ip));

    // Cấu hình mạng từ config.h
    wifi_config_t wifi_config = {};
    snprintf((char*)wifi_config.sta.ssid, sizeof(wifi_config.sta.ssid), "%s", WIFI_SSID);
    snprintf((char*)wifi_config.sta.password, sizeof(wifi_config.sta.password), "%s", WIFI_PASSWORD);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Hoàn tất khởi tạo WiFi Station.");
}

void wifi_wait_for_connection(void) {
    // OS sẽ block Task gọi hàm này tại đây, không tốn 1 chu kỳ CPU nào
    // cho đến khi WIFI_CONNECTED_BIT được set bởi event_handler.
    xEventGroupWaitBits(wifi_event_group, WIFI_CONNECTED_BIT, pdFALSE, pdTRUE, portMAX_DELAY);
}