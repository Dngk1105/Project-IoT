/**
 * @file mqtt_handler.h
 * @brief Header cho module MQTT Handler
 */

#pragma once

#include "mqtt_client.h"
#include <stdbool.h>

/* =========================================================================
 * KHỞI TẠO & ĐIỀU KHIỂN MQTT
 * ========================================================================= */
void mqtt_handler_init(void);
void mqtt_handler_start(void);

/* =========================================================================
 * PUBLISH & SUBSCRIBE
 * ========================================================================= */
int mqtt_handler_publish(const char *topic, const char* payload, 
                        int len, int qos, int retain, int noti = 1);

int mqtt_handler_subscribe(const char *topic, int qos);

/* =========================================================================
 * GETTER FUNCTIONS
 * ========================================================================= */
const char* mqtt_get_device_id(void);
esp_mqtt_client_handle_t mqtt_get_client(void);
bool mqtt_is_connected(void);
