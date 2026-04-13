#include "tasks.h"
#include "leapbot.h"

#include <WiFi.h>
#include <WiFiUdp.h>

static TaskHandle_t transport_task = NULL;
static TaskHandle_t control_task = NULL;
static TaskHandle_t wifi_task = NULL;
static TaskHandle_t lidar_task = NULL;

void loop_transport_task(void *param)
{
    if (!setup_transport()) {
        vTaskDelete(NULL);
        return;
    }

    while (true) {
        loop_transport();
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

void loop_control_task(void *param)
{
    while (true) {
        loop_control();
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

extern void wifi_server_loop();

void loop_wifi_task(void *param)
{
    while (true) {
        wifi_server_loop();
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void loop_lidar_task(void *param)
{
    if (!config.lidar_wifi_bridge_enabled()) {
        Serial.println("[LIDAR] WiFi UDP bridge disabled by config.");
        vTaskDelete(NULL);
        return;
    }

    HardwareSerial lidar_serial(2);
    lidar_serial.begin(115200, SERIAL_8N1, 35, -1);
    Serial.println("[LIDAR] UART2 RX=35 started (no TX)");

    WiFiUDP udp;
    String ip = config.microros_uclient_server_ip();
    ip.trim();
    IPAddress remote_ip;
    if (!remote_ip.fromString(ip)) {
        Serial.printf("[LIDAR] Invalid remote IP: %s\n", ip.c_str());
        vTaskDelete(NULL);
        return;
    }

    const uint16_t remote_port = 8889;
    ensure_wifi_station_connection(config.wifi_sta_ssid().c_str(), config.wifi_sta_pswd().c_str(), config.board_name());
    Serial.println("[LIDAR] Waiting for WiFi connection...");
    while (WiFi.status() != WL_CONNECTED) {
        ensure_wifi_station_connection(config.wifi_sta_ssid().c_str(), config.wifi_sta_pswd().c_str(), config.board_name());
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    Serial.println("[LIDAR] WiFi connected, start data forwarding.");

    uint8_t buf[512];
    while (true) {
        if (WiFi.status() != WL_CONNECTED) {
            ensure_wifi_station_connection(config.wifi_sta_ssid().c_str(), config.wifi_sta_pswd().c_str(), config.board_name());
            vTaskDelay(pdMS_TO_TICKS(500));
            continue;
        }

        int len = lidar_serial.available();
        if (len > 0) {
            if (len > static_cast<int>(sizeof(buf))) {
                len = sizeof(buf);
            }
            const int read_len = lidar_serial.readBytes(buf, len);
            udp.beginPacket(remote_ip, remote_port);
            udp.write(buf, read_len);
            udp.endPacket();
        }

        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

void start_all_tasks()
{
    xTaskCreatePinnedToCore(loop_transport_task, "transport", 16384, NULL, 2, &transport_task, 0);
    xTaskCreatePinnedToCore(loop_control_task, "control", 8192, NULL, 2, &control_task, 1);
    xTaskCreatePinnedToCore(loop_wifi_task, "wifi", 8192, NULL, 1, &wifi_task, 1);
    xTaskCreatePinnedToCore(loop_lidar_task, "lidar", 8192, NULL, 1, &lidar_task, 0);
}
