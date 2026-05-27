#include "wifi_core.h"
#include "config.h"
#include "esp_wifi.h"
#include "system_state.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include <math.h>

static const char *TAG = "WIFI_CORE";


/* Khai báo Event Group
 * Dung co che dong bo, giup cac Task giao tiep voi nhau 
 * EventGroup giong nhu mot bien 32 bit, moi bit la mot su kien
 * Cac task co the set nhieu bit, va cho nhieu bit thi moi thuc hien
 * Cac ham dang su dung:
 * xEventGroupCreate(), xEventGroupSetBits(), xEventGroupClearBits(), xEventGroupWaitBits()
*/ 
static EventGroupHandle_t wifi_event_group;
#define WIFI_CONNECTED_BIT BIT0

/*
 * Tich hop may trang thai tu ham main.cpp
 * SYS_OFFLINE = 1, SYS_WIFI_OK = 2
 */
static int retry_num = 0;
static TimerHandle_t wifi_reconnect_timer = NULL;   // Retry luy tien

// Callback cua Wifi_Timer: Het thoi gian cho se goi callback nay
static void wifi_reconnect_timer_cb(TimerHandle_t xTimer){
    ESP_LOGI(TAG, "Dang thu ket noi WIFI (lan %d)...", retry_num);
    esp_wifi_connect();
}

// Callback xử lý sự kiện WiFi và IP
static void event_handler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } 
    else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        // Neu mat ket noi 
        // Thu ket noi lai theo kieu luy tien 
        xEventGroupClearBits(wifi_event_group, WIFI_CONNECTED_BIT); // Xoa bit wifi connected

        set_sys_state(SYS_OFFLINE); // Ngay lap tuc dua ve trang thai offline
        retry_num++;

        // Thoi gian cho ket noi lai tinh theo cong thuc
        // Delay = BaseTime * 2^retry_num
        // Gioi han toi da 300s 
        int backoff_ms = (1000 * pow(2, retry_num)); // base = 1s
        if (backoff_ms > 300000 || backoff_ms <= 0) // <0 de tranh tran so
            backoff_ms = 300000;
        
        ESP_LOGW(TAG, "Mat mang! dang ket noi lai. Thử lại sau %d ms...", backoff_ms);
        // if (retry_num < WIFI_MAX_RETRY) {
        //     esp_wifi_connect();
        //     retry_num++;
        //     ESP_LOGW(TAG, "Mất kết nối. Đang thử lại (%d/%d)...", retry_num, WIFI_MAX_RETRY);
        // } else {
        //     ESP_LOGE(TAG, "Kết nối thất bại sau %d lần. Cần khởi động lại hoặc chạy offline.", WIFI_MAX_RETRY);
        //     // Tùy chọn: esp_restart(); 
        // }

        /*
        * Khoi dong lai timer cho ket noi lai
        * Thay doi thoi chu ki cua timer, cu the la reconnect timer
        * Neu timer dang chay -> dem chu ki moi. Khong chay thi khoi dong timer
        * Day la API goi lenh, lenh se day vao timer command queue cho Timer Service Task xu li
        * xTicksToWait = 0 => khong cho, neu timer command queue day tra ve pdFAIL
        */
        xTimerChangePeriod(wifi_reconnect_timer, pdMS_TO_TICKS(backoff_ms), 0);
    } 
    else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "Kết nối thành công! Lấy được IP: " IPSTR, IP2STR(&event->ip_info.ip));
        retry_num = 0;
        xTimerStop(wifi_reconnect_timer, 0); // Tat timer

        set_sys_state(SYS_WIFI_OK);

        // Đánh thức tất cả các Task đang chờ WiFi (Ví dụ: MQTT, NTP)
        xEventGroupSetBits(wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

/*Khoi tao wifi
 * NVS -> Netif -> EventLoop
 * NVS: Luu thong tin hieu chinh phan cung 
 * Netif: Quan li network interface trong idf   WiFi Driver <-> esp_netif <-> lwIP/TCP-IP <-> app
 * Wifi Driver:
 *  
*/
void wifi_init_sta(void) {
    // NVS là BẮT BUỘC để driver WiFi lưu thông số Calibration RF
    // nvs: Non-Volatile Storage
    esp_err_t ret = nvs_flash_init();// Khoi tao phan vung mac dinh, label "nvs" trong bang phan vung
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        // Het trang hoac code nay khong dung format (cu)
        ESP_ERROR_CHECK(nvs_flash_erase()); // Xoa toan bo NVS
        ret = nvs_flash_init(); // Khoi tao lai
    }
    ESP_ERROR_CHECK(ret); // Kiem tra ket qua cuoi cung

    wifi_event_group = xEventGroupCreate();

    // Khoi tao timer
    // pdFalse chi ket noi mot lan
    wifi_reconnect_timer = xTimerCreate("WiFi_Reconnect_Timer", pdMS_TO_TICKS(1000), pdFALSE, (void *)0, wifi_reconnect_timer_cb);


    // Khoi tao TCP/IP stack va he thong mang (lwIP, tcpip task,...)
    ESP_ERROR_CHECK(esp_netif_init());  // Goi mot lan, khoi dong toan bo he thong mang
    
    // Tao event loop mac dinh de xu li su kien WiFi/IP
    ESP_ERROR_CHECK(esp_event_loop_create_default()); 

    // Tao interface WiFi STA, tu dong gan DHCP va TCP/IP stack
    esp_netif_create_default_wifi_sta(); // Wifi STA san co, da cau hinh dhcp, tcp/ip

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

bool wifi_is_connected(void){
    EventBits_t bits = xEventGroupGetBits(wifi_event_group);
    return (bits & WIFI_CONNECTED_BIT);
}