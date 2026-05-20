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
constexpr uint32_t kWifiConnectAttemptTimeoutMs = 8000;
constexpr uint32_t kWifiConnectRetryCooldownMs = 500;
constexpr uint32_t kWifiConnectProgressLogIntervalMs = 3000;
constexpr uint32_t kWifiConnectWaitLogIntervalMs = 5000;
constexpr uint32_t kLidarStatsLogIntervalMs = 1000;
constexpr int kLidarUartRxGpio = 35;
constexpr int kLidarUartTxGpio = -1;
constexpr uint16_t kLidarUdpPort = 8889;

struct LidarUdpStats
{
    uint32_t packets_sent = 0;
    uint32_t bytes_sent = 0;
    uint32_t begin_failures = 0;
    uint32_t write_failures = 0;
    uint32_t end_failures = 0;
    uint32_t last_log_ms = 0;
};

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

bool wait_for_wifi_connection(
    const String& ssid,
    const char* attempt_label,
    uint32_t timeout_ms,
    bool log_enabled)
{
    const uint32_t start = millis();
    uint32_t last_log_elapsed = 0;
    wl_status_t last_status = WiFi.status();

    if (log_enabled) {
        Serial.printf(
            "[LIDAR] Serial WiFi waiting (%s): SSID=%s status=%s(%d)\n",
            attempt_label,
            ssid.c_str(),
            wifi_status_to_string(last_status),
            static_cast<int>(last_status));
    }

    while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeout_ms) {
        const uint32_t elapsed = millis() - start;
        const wl_status_t current_status = WiFi.status();
        if (log_enabled &&
            (current_status != last_status || (elapsed - last_log_elapsed) >= kWifiConnectProgressLogIntervalMs)) {
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
        if (log_enabled) {
            const String local_ip = WiFi.localIP().toString();
            Serial.printf(
                "[LIDAR] Serial WiFi connected (%s): SSID=%s localIP=%s RSSI=%d\n",
                attempt_label,
                WiFi.SSID().c_str(),
                local_ip.c_str(),
                WiFi.RSSI());
        }
        return true;
    }

    if (log_enabled) {
        const wl_status_t final_status = WiFi.status();
        Serial.printf(
            "[LIDAR] Serial WiFi failed (%s): SSID=%s timeout=%lu ms finalStatus=%s(%d)\n",
            attempt_label,
            ssid.c_str(),
            static_cast<unsigned long>(timeout_ms),
            wifi_status_to_string(final_status),
            static_cast<int>(final_status));
    }
    return false;
}

bool try_connect_wifi_station(
    const String& ssid,
    const String& password,
    const char* attempt_label,
    uint32_t timeout_ms,
    bool log_enabled)
{
    if (ssid.length() == 0) {
        if (log_enabled) {
            Serial.printf("[LIDAR] Serial WiFi skip (%s): empty SSID\n", attempt_label);
        }
        return false;
    }

    const wl_status_t current_status = WiFi.status();
    if (log_enabled) {
        Serial.printf(
            "[LIDAR] Serial WiFi attempt (%s): SSID=%s mode=%d status=%s(%d)\n",
            attempt_label,
            ssid.c_str(),
            static_cast<int>(WiFi.getMode()),
            wifi_status_to_string(current_status),
            static_cast<int>(current_status));
    }

    // 只重置本次 STA 尝试，不擦除 NVS 中保存的原始 WiFi 凭据。
    WiFi.disconnect(true, false);
    vTaskDelay(pdMS_TO_TICKS(kWifiConnectRetryCooldownMs));
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());

    return wait_for_wifi_connection(ssid, attempt_label, timeout_ms, log_enabled);
}

void send_lidar_udp_packet(
    WiFiUDP& udp,
    const IPAddress& target_ip,
    uint16_t remote_port,
    const uint8_t* data,
    int data_len,
    LidarUdpStats& stats)
{
    if (!udp.beginPacket(target_ip, remote_port)) {
        stats.begin_failures++;
        return;
    }

    const size_t written = udp.write(data, data_len);
    if (written != static_cast<size_t>(data_len)) {
        stats.write_failures++;
    }

    if (!udp.endPacket()) {
        stats.end_failures++;
        return;
    }

    stats.packets_sent++;
    stats.bytes_sent += static_cast<uint32_t>(data_len);
}

void log_lidar_udp_stats(LidarUdpStats& stats, bool log_enabled)
{
    const uint32_t now = millis();
    if ((now - stats.last_log_ms) < kLidarStatsLogIntervalMs) {
        return;
    }

    if (log_enabled) {
        Serial.printf(
            "[LIDAR] UDP stats packets=%lu bytes=%lu begin_fail=%lu write_fail=%lu end_fail=%lu\n",
            static_cast<unsigned long>(stats.packets_sent),
            static_cast<unsigned long>(stats.bytes_sent),
            static_cast<unsigned long>(stats.begin_failures),
            static_cast<unsigned long>(stats.write_failures),
            static_cast<unsigned long>(stats.end_failures));
    }

    stats = LidarUdpStats{};
    stats.last_log_ms = now;
}

bool start_pinned_task(
    TaskFunction_t task_func,
    const char* task_name,
    uint32_t stack_depth,
    UBaseType_t priority,
    TaskHandle_t* task_handle,
    BaseType_t core_id)
{
    const BaseType_t ok = xTaskCreatePinnedToCore(
        task_func,
        task_name,
        stack_depth,
        NULL,
        priority,
        task_handle,
        core_id);
    if (ok != pdPASS) {
        Serial.printf("[TASK] failed to create %s task\n", task_name);
        return false;
    }
    return true;
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
    const uint32_t microros_serial_id = config.microros_serial_id();
    const bool serial_transport_uses_uart0 = serial_transport_active && microros_serial_id != 2;
    const bool log_enabled = !serial_transport_uses_uart0;

    if (serial_transport_active && microros_serial_id == 2) {
        Serial.println("[LIDAR] disabled: micro-ROS serial_id=2 uses UART2 reserved for lidar.");
        vTaskDelete(NULL);
        return;
    }

    HardwareSerial lidar_serial(2);
    lidar_serial.begin(115200, SERIAL_8N1, kLidarUartRxGpio, kLidarUartTxGpio);
    if (log_enabled) {
        Serial.printf("[LIDAR] UART2 RX=%d started (no TX)\n", kLidarUartRxGpio);
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
    const uint16_t remotePort = kLidarUdpPort;

    if (serial_transport_active) {
        const String configured_ssid = config.wifi_sta_ssid();
        const String configured_pswd = config.wifi_sta_pswd();
        WiFi.onEvent(WiFiEventCB);
        if (WiFi.getMode() == WIFI_MODE_NULL) {
            WiFi.mode(WIFI_STA);
        }

        bool wifi_connected = WiFi.status() == WL_CONNECTED;
        if (wifi_connected) {
            if (log_enabled) {
                const String local_ip = WiFi.localIP().toString();
                Serial.printf(
                    "[LIDAR] Serial WiFi already connected: SSID=%s localIP=%s\n",
                    WiFi.SSID().c_str(),
                    local_ip.c_str());
            }
        } else {
            wifi_connected = try_connect_wifi_station(
                configured_ssid,
                configured_pswd,
                "configured",
                kWifiConnectAttemptTimeoutMs,
                log_enabled);

            if (!wifi_connected && log_enabled) {
                Serial.println("[LIDAR] Serial WiFi still offline after configured attempt; keep waiting.");
            }
        }
    }

    // 等待 WiFi 连接
    if (!serial_transport_active) {
        Serial.println("[LIDAR] Waiting for WiFi connection...");
    } else if (WiFi.status() != WL_CONNECTED && log_enabled) {
        Serial.println("[LIDAR] Serial WiFi waiting for connection before starting UDP forwarding...");
    }

    uint32_t last_wait_log = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (serial_transport_active && log_enabled && (millis() - last_wait_log) >= kWifiConnectWaitLogIntervalMs) {
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
    } else if (log_enabled) {
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
        if (log_enabled) {
            Serial.printf(
                "[LIDAR] Invalid configured IP %s, fallback to broadcast %s\n",
                configured_ip.c_str(),
                targetIP.toString().c_str());
        }
    } else if (serial_transport_active && !ip_on_same_subnet(configuredRemoteIP, localIP, subnetMask)) {
        targetIP = WiFi.broadcastIP();
        if (log_enabled) {
            Serial.printf(
                "[LIDAR] Configured IP %s not in subnet %s/%s, fallback to broadcast %s\n",
                configuredRemoteIP.toString().c_str(),
                localIP.toString().c_str(),
                subnetMask.toString().c_str(),
                targetIP.toString().c_str());
        }
    } else if (!serial_transport_active) {
        Serial.printf(
            "[LIDAR] Forward target %s:%u\n",
            targetIP.toString().c_str(),
            remotePort);
    }

    uint8_t buf[512];
    LidarUdpStats udp_stats;
    udp_stats.last_log_ms = millis();
    while (true) {
        int len = lidar_serial.available();
        if (len > 0) {
            if (static_cast<size_t>(len) > sizeof(buf)) {
                len = static_cast<int>(sizeof(buf));
            }
            int readLen = lidar_serial.readBytes(buf, len);
            if (readLen > 0) {
                send_lidar_udp_packet(udp, targetIP, remotePort, buf, readLen, udp_stats);
            }
        }

        log_lidar_udp_stats(udp_stats, log_enabled);
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ------------------- 统一任务启动接口 -------------------
void start_all_tasks() {
    start_pinned_task(loop_transport_task, "transport", 16384, 2, &transport_task, 0);
    start_pinned_task(loop_control_task, "control", 8192, 2, &control_task, 1);
    start_pinned_task(loop_wifi_task, "wifi", 8192, 1, &wifi_task, 1);
    start_pinned_task(loop_lidar_task, "lidar", 8192, 1, &lidar_task, 0);
}
