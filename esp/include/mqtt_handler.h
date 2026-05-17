#pragma once

/// ======================================================
/// MQTT INIT
///
/// Khởi tạo MQTT client
/// connect tới broker
/// subscribe topic
/// ======================================================
void mqtt_init(void);


/// ======================================================
/// MQTT SEND
///
/// Publish dữ liệu lên broker
///
/// topic : MQTT topic
/// data  : payload
///
/// return:
/// 0  -> success
/// -1 -> fail
/// ======================================================
int mqtt_send(
    const char *topic,
    const char *data
);