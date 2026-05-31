#include "local_storage.h"
#include "esp_log.h"
#include "esp_littlefs.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static const char *TAG = "LOCAL_STORAGE";
static const char *SCHEDULE_FILE = "/littlefs/schedule.json";

static esp_calendar_event_t event_cache[MAX_CACHED_EVENTS];
static int event_count = 0;

static event_action_t action_str_to_enum(const char* action_str) {
    if (strcmp(action_str, "CLASS") == 0) return ACTION_CLASS;
    if (strcmp(action_str, "MEET") == 0) return ACTION_MEET;
    if (strcmp(action_str, "VOICE") == 0) return ACTION_VOICE;
    return ACTION_ALARM; // Default
}

static const char* action_enum_to_str(event_action_t action) {
    switch (action) {
        case ACTION_CLASS: return "CLASS";
        case ACTION_MEET:  return "MEET";
        case ACTION_VOICE: return "VOICE";
        default:           return "ALARM";
    }
}

//bubble sort
static void sort_cache_by_time() {
    for (int i = 0; i < event_count - 1; i++) {
        for (int j = 0; j < event_count - i - 1; j++) {
            if (event_cache[j].timestamp > event_cache[j + 1].timestamp) {
                esp_calendar_event_t temp = event_cache[j];
                event_cache[j] = event_cache[j + 1];
                event_cache[j + 1] = temp;
            }
        }
    }
}

static bool save_cache_to_flash(){
    cJSON *root_array = cJSON_CreateArray();
    for (int i = 0; i < event_count; i++) {
        cJSON *item = cJSON_CreateObject();
        cJSON_AddStringToObject(item, "id", event_cache[i].id);
        cJSON_AddNumberToObject(item, "t", event_cache[i].timestamp);
        cJSON_AddStringToObject(item, "a", action_enum_to_str(event_cache[i].action));
        cJSON_AddStringToObject(item, "msg", event_cache[i].msg);
        cJSON_AddItemToArray(root_array, item);
    }

    char *json_str = cJSON_PrintUnformatted(root_array);
    cJSON_Delete(root_array);
    if (!json_str) return false;

    FILE *f = fopen(SCHEDULE_FILE, "w");
    if (f == NULL) {
        ESP_LOGE(TAG, "Không thể mở file để ghi: %s", SCHEDULE_FILE);
        free(json_str);
        return false;
    }

    fprintf(f, "%s", json_str);
    fclose(f);
    free(json_str);
    
    ESP_LOGI(TAG, "Đã lưu thành công %d sự kiện xuống Flash.", event_count);
    return true;
}

void local_storage_init(){
    ESP_LOGI(TAG, "Khởi tạo LittleFS...");
    esp_vfs_littlefs_conf_t conf = {
        .base_path = "/littlefs",
        .partition_label = "storage",
        .format_if_mount_failed = true,
        .dont_mount = false,
    };

    esp_err_t ret = esp_vfs_littlefs_register(&conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Lỗi mount LittleFS (%s)", esp_err_to_name(ret));
        return;
    }

    // Mo file flash -> nap len RAM
    FILE *f = fopen(SCHEDULE_FILE, "r");
    if (f == NULL) {
        ESP_LOGW(TAG, "File lịch trình chưa tồn tại, bắt đầu với kho rỗng.");
        return;
    }

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size > 0){
        char *json_str = (char*)malloc(size+1);
        fread(json_str, 1, size, f);
        json_str[size] = '\0';

        cJSON *root = cJSON_Parse(json_str);
        if (root && cJSON_IsArray(root)){
            event_count = 0;
            cJSON *item = NULL;
            cJSON_ArrayForEach(item, root){
                if (event_count >= MAX_CACHED_EVENTS) break;

                strncpy(event_cache[event_count].id, cJSON_GetObjectItem(item, "id")->valuestring, 39);
                event_cache[event_count].timestamp = (uint32_t)cJSON_GetObjectItem(item, "t")->valuedouble;
                event_cache[event_count].action = action_str_to_enum(cJSON_GetObjectItem(item, "a")->valuestring);
                strncpy(event_cache[event_count].msg, cJSON_GetObjectItem(item, "msg")->valuestring, 35);

                event_count++;
            }
            ESP_LOGI(TAG, "Nap %d su kien vao RAM Cache.", event_count);
        }
        if (root) cJSON_Delete(root);
        free(json_str);
    }
    fclose(f);
}

bool local_storage_sync_schedule(cJSON *delta_data) {
    if (!delta_data) return false;
    bool cache_changed = false;

    // DEL
    cJSON *del_array = cJSON_GetObjectItem(delta_data, "del");
    if (del_array && cJSON_IsArray(del_array)) {
        cJSON *del_id = NULL;
        cJSON_ArrayForEach(del_id, del_array) {
            for (int i = 0; i < event_count; i++) {
                if (strcmp(event_cache[i].id, del_id->valuestring) == 0) {
                    // Dịch trái mảng để xóa
                    for (int j = i; j < event_count - 1; j++) {
                        event_cache[j] = event_cache[j + 1];
                    }
                    event_count--;
                    cache_changed = true;
                    break;
                }
            }
        }
    }

    // ADD/UPDATE
    const char* target_arrays[] = {"add", "upd"};
    for (int arr_idx = 0; arr_idx < 2; arr_idx++) {
        cJSON *arr = cJSON_GetObjectItem(delta_data, target_arrays[arr_idx]);
        if (arr && cJSON_IsArray(arr)) {
            cJSON *item = NULL;
            cJSON_ArrayForEach(item, arr) {
                const char* id = cJSON_GetObjectItem(item, "id")->valuestring;
                
                // Tim xem da co trong cached chua
                int found_idx = -1;
                for (int i = 0; i < event_count; i++) {
                    if (strcmp(event_cache[i].id, id) == 0) {
                        found_idx = i;
                        break;
                    }
                }

                // Khong co -> them moi
                if (found_idx == -1) {
                    if (event_count < MAX_CACHED_EVENTS) {
                        found_idx = event_count++;
                    } else {
                        ESP_LOGW(TAG, "Cache đầy, bỏ qua sự kiện mới.");
                        continue;
                    }
                }

                strncpy(event_cache[found_idx].id, id, 39);
                event_cache[found_idx].timestamp = (uint32_t)cJSON_GetObjectItem(item, "t")->valuedouble;
                event_cache[found_idx].action = action_str_to_enum(cJSON_GetObjectItem(item, "a")->valuestring);
                strncpy(event_cache[found_idx].msg, cJSON_GetObjectItem(item, "msg")->valuestring, 35);
                
                cache_changed = true;
            }
        }
    }

    // Neu co thay doi -> Sort -> Nap vao FLASH
    if (cache_changed) {
        sort_cache_by_time();
        return save_cache_to_flash();
    }
    
    return true; // Khong co ngoai le -> thanh cong
}

bool local_storage_get_next_event(esp_calendar_event_t *out_event) {
    if (event_count > 0 && out_event != NULL) {
        // Sort ^ nen event gan nhat la 0
        *out_event = event_cache[0]; 
        return true;
    }
    return false;
}

void local_storage_remove_event(const char* event_id) {
    for (int i = 0; i < event_count; i++) {
        if (strcmp(event_cache[i].id, event_id) == 0) {
            for (int j = i; j < event_count - 1; j++) {
                event_cache[j] = event_cache[j + 1];
            }
            event_count--;
            save_cache_to_flash();
            return;
        }
    }
}