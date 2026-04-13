#include "ap_hw_init.h"

#include <WebServer.h>

#include "ap_global.h"

namespace
{
WebServer server(80);
bool web_server_started = false;

const char html_page[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>XuegeBot Web Control</title>
<style>
body { font-family: sans-serif; text-align: center; background: #f4f4f4; }
button { width: 80px; height: 80px; font-size: 32px; margin: 10px; border-radius: 20px; border: none; background: #4285f4; color: white; }
#panel { display: inline-grid; grid-template-columns: 100px 100px 100px; grid-template-rows: 100px 100px 100px; justify-content: center; align-items: center; margin-top: 40px; }
</style>
</head>
<body>
  <h2>XuegeBot Direction Control</h2>
  <div id="panel">
    <div></div>
    <button id="up">^</button>
    <div></div>
    <button id="left"><</button>
    <button id="stop">o</button>
    <button id="right">></button>
    <div></div>
    <button id="down">v</button>
    <div></div>
  </div>
  <p id="val">vx=0.00, vz=0.00</p>
<script>
let vx = 0.0, vz = 0.0;
const step = 0.1;
function update() {
  document.getElementById("val").innerText = `vx=${vx.toFixed(2)}, vz=${vz.toFixed(2)}`;
  fetch(`/set?vx=${vx.toFixed(2)}&vz=${vz.toFixed(2)}`);
}
document.getElementById("up").onclick = () => { vx += step; update(); };
document.getElementById("down").onclick = () => { vx -= step; update(); };
document.getElementById("left").onclick = () => { vz += step; update(); };
document.getElementById("right").onclick = () => { vz -= step; update(); };
document.getElementById("stop").onclick = () => { vx = 0; vz = 0; update(); };
</script>
</body>
</html>
)rawliteral";

void handle_root()
{
    server.send(200, "text/html", html_page);
}

void handle_set()
{
    static float http_vx = 0.0f;
    static float http_vz = 0.0f;
    static float target_motor_speed1 = 0.0f;
    static float target_motor_speed2 = 0.0f;

    if (server.hasArg("vx")) {
        http_vx = server.arg("vx").toFloat();
    }
    if (server.hasArg("vz")) {
        http_vz = server.arg("vz").toFloat();
    }

    kinematics.kinematic_inverse(http_vx * 1000.0f, http_vz, target_motor_speed1, target_motor_speed2);
    pid_controller[0].update_target(target_motor_speed1);
    pid_controller[1].update_target(target_motor_speed2);

    log_debug(
        "web",
        "recv vx=%.2f vz=%.2f l1=%.2f l2=%.2f",
        http_vx,
        http_vz,
        target_motor_speed1,
        target_motor_speed2);
    server.send(
        200,
        "text/html",
        "<h3>OK</h3><p>vx=" + String(http_vx) + ", vz=" + String(http_vz) + "</p><a href='/'>back</a>");
}

void start_web_server()
{
    if (!config.web_control_enabled() || web_server_started) {
        return;
    }

    server.on("/", handle_root);
    server.on("/set", handle_set);
    server.begin();
    web_server_started = true;
    log_debug("web", "WebServer started at http://%s", WiFi.localIP().toString().c_str());
}
} // namespace

void wifi_server_loop()
{
    if (config.web_control_enabled() && wifi_status == WIFI_STATUS_GOT_IP) {
        server.handleClient();
    }
}

bool Board::board_init()
{
    pinMode(CONFIG_DEFAULT_SERVP05_GPIO, OUTPUT);
    digitalWrite(CONFIG_DEFAULT_SERVP05_GPIO, LOW);
    pinMode(2, OUTPUT);

    if (!serial_init()) {
        while (true) {
        }
    }
    if (!oled_init()) {
        while (true) {
        }
    }
    if (!motor_init()) {
        while (true) {
        }
    }
    if (!encoder_init()) {
        while (true) {
        }
    }
    if (!button_init()) {
        while (true) {
        }
    }
    if (!battery_init()) {
        while (true) {
        }
    }

    safety_init();
    imu.begin(18, 19);

    pid_controller[0].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), config.kinematics_pid_kd());
    pid_controller[1].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), config.kinematics_pid_kd());
    pid_controller[0].out_limit(-config.kinematics_pid_out_limit(), config.kinematics_pid_out_limit());
    pid_controller[1].out_limit(-config.kinematics_pid_out_limit(), config.kinematics_pid_out_limit());

    kinematics.set_motor_param(
        0, config.motor_reducation_ration(0), config.motor_pulse_ration(0), config.motor_wheel_diameter(0));
    kinematics.set_motor_param(
        1, config.motor_reducation_ration(1), config.motor_pulse_ration(1), config.motor_wheel_diameter(1));
    kinematics.set_kinematic_param(config.kinematics_wheel_distance());
    refresh_control_config();
    return true;
}

bool Board::serial_init()
{
    Serial.begin(115200);
    log_set_target(Serial);
    config.init(CONFIG_NAME_NAMESPACE);
    if (config.microros_transport_mode() != CONFIG_TRANSPORT_MODE_SERIAL) {
        config.config(CONFIG_NAME_TRANSPORT_MODE, CONFIG_TRANSPORT_MODE_SERIAL);
        config.config("microros_mode", CONFIG_TRANSPORT_MODE_SERIAL);
        log_debug("serial", "force transport_mode=serial in fire mode");
    }
    if (config.microros_serial_id() == 2) {
        config.config(CONFIG_NAME_TRANSPORT_SERIAL_ID, "0");
        config.config("serial_id", "0");
        log_debug("serial", "serial_id=2 disabled in fire mode; forcing USB serial control link");
    }
    if (config.lidar_wifi_bridge_enabled()) {
        config.config(CONFIG_NAME_LIDAR_WIFI_BRIDGE_ENABLED, "0");
        log_debug("serial", "disable lidar WiFi bridge in serial mode to keep USB transport clean");
    }
    Serial.println(FIRST_START_TIP);
    Serial.println(config.config_str());
    return true;
}

bool Board::battery_init()
{
    battery.init();
    return true;
}

bool Board::oled_init()
{
    display.updateVersionCode(VERSION_CODE);
    display.init();
    display.updateTransMode(config.microros_transport_mode());
    display.updateBaudRate(config.serial_baudrate());
    display.updateStartupInfo();
    return true;
}

bool Board::motor_init()
{
    motor.attachMotor(0, CONFIG_DEFAULT_MOTOR0_A_GPIO, CONFIG_DEFAULT_MOTOR0_B_GPIO);
    motor.attachMotor(1, CONFIG_DEFAULT_MOTOR1_A_GPIO, CONFIG_DEFAULT_MOTOR1_B_GPIO);
    return true;
}

bool Board::button_init()
{
    button.attachDoubleClick(doubleClick);
    button.attachClick(oneClick);
    return true;
}

bool Board::encoder_init()
{
    encoders[0].init(CONFIG_DEFAULT_PCNT_UTIL_00, CONFIG_DEFAULT_ENCODER0_A_GPIO, CONFIG_DEFAULT_ENCODER0_B_GPIO);
    encoders[1].init(CONFIG_DEFAULT_PCNT_UTIL_01, CONFIG_DEFAULT_ENCODER1_A_GPIO, CONFIG_DEFAULT_ENCODER1_B_GPIO);
    return true;
}

bool ensure_wifi_sta_connected()
{
    if (WiFi.status() == WL_CONNECTED) {
        return true;
    }

    const String ssid = config.wifi_sta_ssid();
    const String password = config.wifi_sta_pswd();
    if (ssid.length() == 0) {
        log_debug("wifi", "wifi ssid empty, skip station connect");
        return false;
    }

    wifi_status = WIFI_STATUS_WAIT_CONNECT;
    display.updateWIFISSID(ssid);
    display.updateWIFIPSWD(password);
    display.updateWIFIInfo("wait connect", WIFI_STATUS_WAIT_CONNECT);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());
    return true;
}

void WiFiEventCB(WiFiEvent_t event, WiFiEventInfo_t info)
{
    switch (event) {
    case SYSTEM_EVENT_STA_DISCONNECTED:
        log_debug("wifi", "WIFI DISCONNECTED REASON:%d", info.wifi_sta_disconnected.reason);
        if (info.wifi_sta_disconnected.reason == 15) {
            display.updateWIFIInfo("password error", WIFI_STATUS_PASD_ERROR);
            wifi_status = WIFI_STATUS_PASD_ERROR;
        } else if (info.wifi_sta_disconnected.reason == 201) {
            display.updateWIFIInfo("wifi not found", WIFI_STATUS_NO_FOUND);
            wifi_status = WIFI_STATUS_NO_FOUND;
        } else {
            display.updateWIFIInfo(
                String("unknown:") + String(int(info.wifi_sta_disconnected.reason)), WIFI_STATUS_UNKNOW);
            wifi_status = WIFI_STATUS_UNKNOW;
        }
        break;
    case SYSTEM_EVENT_STA_GOT_IP:
        wifi_status = WIFI_STATUS_GOT_IP;
        display.updateWIFIInfo("got ip", WIFI_STATUS_GOT_IP);
        display.updateWIFIIp(WiFi.localIP().toString());
        start_web_server();
        break;
    case SYSTEM_EVENT_STA_LOST_IP:
        wifi_status = WIFI_STATUS_WAIT_CONNECT;
        display.updateWIFIInfo("wait connect", WIFI_STATUS_WAIT_CONNECT);
        break;
    default:
        break;
    }
}

void doubleClick()
{
    log_debug("key", "doubleClick() detected.");
    if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT) {
        config.config("microros_mode", "serial");
    } else {
        config.config("microros_mode", "udp_client");
    }
    safety_force_pump_off();
    safety_stop_motion();
    esp_restart();
}

void oneClick()
{
    static uint8_t display_mode = 0;
    display.updateDisplayMode(display_mode++);
}
