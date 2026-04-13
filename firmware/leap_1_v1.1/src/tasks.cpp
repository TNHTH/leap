#include "tasks.h"
#include "leapbot.h"
#include <WiFi.h>
#include <WiFiUdp.h>

// 全局任务句柄
static TaskHandle_t transport_task = NULL;
static TaskHandle_t control_task = NULL;
static TaskHandle_t wifi_task = NULL;
static TaskHandle_t lidar_task = NULL;

// ------------------- transport task -------------------
void loop_transport_task(void *param) {
    if (!setup_transport()) {
        vTaskDelete(NULL);
        return;
    }
    while (true) {
        loop_transport();
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ------------------- control task -------------------
void loop_control_task(void *param) {
    while (true) {
        loop_control();
        vTaskDelay(pdMS_TO_TICKS(10));  // 控制循环 100Hz
    }
}

// ------------------- wifi server task -------------------
extern void wifi_server_loop();
void loop_wifi_task(void *param) {
    while (true) {
        wifi_server_loop();
        vTaskDelay(pdMS_TO_TICKS(20));  // 网页循环 50Hz
    }
}

// ------------------- LIDAR UART2 + PWM任务 -------------------
void loop_lidar_task(void *param) {
    const bool serial_transport_active = config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_SERIAL;
    HardwareSerial Serial2(2);
    Serial2.begin(115200, SERIAL_8N1, 35, -1); // 只使用 RX=35，无 TX
    if (!serial_transport_active) {
        Serial.println("[LIDAR] UART2 RX=21 started (no TX)");
    }

    // // PWM 控制引脚
    // const int LIDAR_PWM_PIN = 27;
    // const int LIDAR_PWM_CHANNEL = 0;
    // const int LIDAR_PWM_FREQ = 20000;   // 20kHz 高频避免噪音
    // const int LIDAR_PWM_RES = 8;        // 8位分辨率 (0~255)
    // int lidar_speed = 185;              // 初始占空比（速度）

    // ledcSetup(LIDAR_PWM_CHANNEL, LIDAR_PWM_FREQ, LIDAR_PWM_RES);
    // ledcAttachPin(LIDAR_PWM_PIN, LIDAR_PWM_CHANNEL);
    // ledcWrite(LIDAR_PWM_CHANNEL, lidar_speed);
    // Serial.printf("[LIDAR] PWM started on GPIO %d, speed=%d\n", LIDAR_PWM_PIN, lidar_speed);

    WiFiUDP udp;
    String ip = config.microros_uclient_server_ip();
    ip.trim();
    IPAddress remoteIP;
    if (!remoteIP.fromString(ip)) {
        Serial.printf("[LIDAR] Invalid remote IP: %s\n", ip.c_str());
        vTaskDelete(NULL);
        return;
    }
    const uint16_t remotePort = 8889;

    // 等待 WiFi 连接
    if (!serial_transport_active) {
        Serial.println("[LIDAR] Waiting for WiFi connection...");
    }
    while (WiFi.status() != WL_CONNECTED) {
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    if (!serial_transport_active) {
        Serial.println("[LIDAR] WiFi connected, start data forwarding.");
    }

    uint8_t buf[512];
    while (true) {
        int len = Serial2.available();
        if (len > 0) {
            if (len > sizeof(buf)) len = sizeof(buf);
            int readLen = Serial2.readBytes(buf, len);

            // UDP 透传雷达数据
            udp.beginPacket(remoteIP, remotePort);
            udp.write(buf, readLen);
            udp.endPacket();

            if (!serial_transport_active) {
                Serial.printf("[LIDAR] Sent %d bytes\n", readLen);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ------------------- 统一任务启动接口 -------------------
void start_all_tasks() {
    // 启动 ros2 线程
    xTaskCreatePinnedToCore(loop_transport_task, "transport", 16384, NULL, 2, &transport_task, 0);
    // 启动控制线程
    xTaskCreatePinnedToCore(loop_control_task, "control", 8192, NULL, 2, &control_task, 1);
    // 启动 WiFi 服务线程
    xTaskCreatePinnedToCore(loop_wifi_task, "wifi", 8192, NULL, 1, &wifi_task, 1);
    // 启动 LIDAR 任务
    xTaskCreatePinnedToCore(loop_lidar_task, "lidar", 8192, NULL, 1, &lidar_task, 0);
}
