#include "tasks.h"
#include "leapbot.h"
#include <WiFi.h>
#include <WiFiUdp.h>

// 全局任务句柄
static TaskHandle_t transport_task = NULL;
static TaskHandle_t control_task = NULL;
static TaskHandle_t wifi_task = NULL;
static TaskHandle_t lidar_task = NULL;

namespace
{
constexpr const char* kFallbackWifiSsid = "Redmi K70 Pro";
constexpr const char* kFallbackWifiPassword = "17367057680";
constexpr uint32_t kWifiConnectAttemptTimeoutMs = 8000;
constexpr uint32_t kWifiConnectRetryCooldownMs = 500;
constexpr uint32_t kWifiConnectProgressLogIntervalMs = 3000;
constexpr uint32_t kWifiConnectWaitLogIntervalMs = 5000;

bool ip_on_same_subnet(const IPAddress& left, const IPAddress& right, const IPAddress& mask)
{
    for (uint8_t index = 0; index < 4; ++index) {
        if ((left[index] & mask[index]) != (right[index] & mask[index])) {
            return false;
        }
    }
    return true;
}

const char* wifi_status_to_string(wl_status_t status)
{
    switch (status) {
        case WL_IDLE_STATUS:
            return "IDLE";
        case WL_NO_SSID_AVAIL:
            return "NO_SSID";
        case WL_SCAN_COMPLETED:
            return "SCAN_DONE";
        case WL_CONNECTED:
            return "CONNECTED";
        case WL_CONNECT_FAILED:
            return "CONNECT_FAILED";
        case WL_CONNECTION_LOST:
            return "CONNECTION_LOST";
        case WL_DISCONNECTED:
            return "DISCONNECTED";
        default:
            return "UNKNOWN";
    }
}

bool wait_for_wifi_connection(const String& ssid, const char* attempt_label, uint32_t timeout_ms)
{
    const uint32_t start = millis();
    uint32_t last_log_elapsed = 0;
    wl_status_t last_status = WiFi.status();

    Serial.printf(
        "[LIDAR] Serial WiFi waiting (%s): SSID=%s status=%s(%d)\n",
        attempt_label,
        ssid.c_str(),
        wifi_status_to_string(last_status),
        static_cast<int>(last_status));

    while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeout_ms) {
        const uint32_t elapsed = millis() - start;
        const wl_status_t current_status = WiFi.status();
        if (current_status != last_status || (elapsed - last_log_elapsed) >= kWifiConnectProgressLogIntervalMs) {
            Serial.printf(
                "[LIDAR] Serial WiFi waiting (%s): SSID=%s elapsed=%lu ms status=%s(%d)\n",
                attempt_label,
                ssid.c_str(),
                static_cast<unsigned long>(elapsed),
                wifi_status_to_string(current_status),
                static_cast<int>(current_status));
            last_status = current_status;
            last_log_elapsed = elapsed;
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }

    if (WiFi.status() == WL_CONNECTED) {
        const String local_ip = WiFi.localIP().toString();
        Serial.printf(
            "[LIDAR] Serial WiFi connected (%s): SSID=%s localIP=%s RSSI=%d\n",
            attempt_label,
            WiFi.SSID().c_str(),
            local_ip.c_str(),
            WiFi.RSSI());
        return true;
    }

    const wl_status_t final_status = WiFi.status();
    Serial.printf(
        "[LIDAR] Serial WiFi failed (%s): SSID=%s timeout=%lu ms finalStatus=%s(%d)\n",
        attempt_label,
        ssid.c_str(),
        static_cast<unsigned long>(timeout_ms),
        wifi_status_to_string(final_status),
        static_cast<int>(final_status));
    return false;
}

bool try_connect_wifi_station(const String& ssid, const String& password, const char* attempt_label, uint32_t timeout_ms)
{
    if (ssid.length() == 0) {
        Serial.printf("[LIDAR] Serial WiFi skip (%s): empty SSID\n", attempt_label);
        return false;
    }

    const wl_status_t current_status = WiFi.status();
    Serial.printf(
        "[LIDAR] Serial WiFi attempt (%s): SSID=%s mode=%d status=%s(%d)\n",
        attempt_label,
        ssid.c_str(),
        static_cast<int>(WiFi.getMode()),
        wifi_status_to_string(current_status),
        static_cast<int>(current_status));

    // 只重置本次 STA 尝试，不擦除 NVS 中保存的原始 WiFi 凭据。
    WiFi.disconnect(true, false);
    vTaskDelay(pdMS_TO_TICKS(kWifiConnectRetryCooldownMs));
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());

    return wait_for_wifi_connection(ssid, attempt_label, timeout_ms);
}
} // namespace

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
    String configured_ip = config.microros_uclient_server_ip();
    configured_ip.trim();
    IPAddress configuredRemoteIP;
    const bool configured_ip_valid = configuredRemoteIP.fromString(configured_ip);
    const uint16_t remotePort = 8889;

    if (serial_transport_active) {
        const String configured_ssid = config.wifi_sta_ssid();
        const String configured_pswd = config.wifi_sta_pswd();
        WiFi.onEvent(WiFiEventCB);
        if (WiFi.getMode() == WIFI_MODE_NULL) {
            WiFi.mode(WIFI_STA);
        }

        bool wifi_connected = WiFi.status() == WL_CONNECTED;
        if (wifi_connected) {
            const String local_ip = WiFi.localIP().toString();
            Serial.printf(
                "[LIDAR] Serial WiFi already connected: SSID=%s localIP=%s\n",
                WiFi.SSID().c_str(),
                local_ip.c_str());
        } else {
            wifi_connected = try_connect_wifi_station(
                configured_ssid,
                configured_pswd,
                "configured",
                kWifiConnectAttemptTimeoutMs);

            const bool fallback_matches_config =
                configured_ssid == kFallbackWifiSsid && configured_pswd == kFallbackWifiPassword;
            if (!wifi_connected && !fallback_matches_config) {
                Serial.printf(
                    "[LIDAR] Serial WiFi fallback: configured SSID=%s failed, retry hotspot SSID=%s\n",
                    configured_ssid.c_str(),
                    kFallbackWifiSsid);
                wifi_connected = try_connect_wifi_station(
                    kFallbackWifiSsid,
                    kFallbackWifiPassword,
                    "fallback",
                    kWifiConnectAttemptTimeoutMs);
            } else if (!wifi_connected) {
                Serial.printf(
                    "[LIDAR] Serial WiFi fallback skipped: configured credentials already match hotspot SSID=%s\n",
                    kFallbackWifiSsid);
            }

            if (!wifi_connected) {
                Serial.println("[LIDAR] Serial WiFi still offline after configured + fallback attempts; keep waiting.");
            }
        }
    }

    // 等待 WiFi 连接
    if (!serial_transport_active) {
        Serial.println("[LIDAR] Waiting for WiFi connection...");
    } else if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[LIDAR] Serial WiFi waiting for connection before starting UDP forwarding...");
    }

    uint32_t last_wait_log = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (serial_transport_active && (millis() - last_wait_log) >= kWifiConnectWaitLogIntervalMs) {
            const wl_status_t current_status = WiFi.status();
            Serial.printf(
                "[LIDAR] Serial WiFi still waiting: status=%s(%d)\n",
                wifi_status_to_string(current_status),
                static_cast<int>(current_status));
            last_wait_log = millis();
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    if (!serial_transport_active) {
        Serial.println("[LIDAR] WiFi connected, start data forwarding.");
    } else {
        const String local_ip = WiFi.localIP().toString();
        Serial.printf(
            "[LIDAR] Serial WiFi ready for UDP forwarding: SSID=%s localIP=%s\n",
            WiFi.SSID().c_str(),
            local_ip.c_str());
    }

    IPAddress targetIP = configuredRemoteIP;
    const IPAddress localIP = WiFi.localIP();
    const IPAddress subnetMask = WiFi.subnetMask();

    if (!configured_ip_valid) {
        targetIP = WiFi.broadcastIP();
        Serial.printf(
            "[LIDAR] Invalid configured IP %s, fallback to broadcast %s\n",
            configured_ip.c_str(),
            targetIP.toString().c_str());
    } else if (serial_transport_active && !ip_on_same_subnet(configuredRemoteIP, localIP, subnetMask)) {
        targetIP = WiFi.broadcastIP();
        Serial.printf(
            "[LIDAR] Configured IP %s not in subnet %s/%s, fallback to broadcast %s\n",
            configuredRemoteIP.toString().c_str(),
            localIP.toString().c_str(),
            subnetMask.toString().c_str(),
            targetIP.toString().c_str());
    } else if (!serial_transport_active) {
        Serial.printf(
            "[LIDAR] Forward target %s:%u\n",
            targetIP.toString().c_str(),
            remotePort);
    }

    uint8_t buf[512];
    while (true) {
        int len = Serial2.available();
        if (len > 0) {
            if (len > sizeof(buf)) len = sizeof(buf);
            int readLen = Serial2.readBytes(buf, len);

            // UDP 透传雷达数据
            udp.beginPacket(targetIP, remotePort);
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
