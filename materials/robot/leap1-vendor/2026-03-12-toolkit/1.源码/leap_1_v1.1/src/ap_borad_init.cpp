#include "ap_hw_init.h"
#include "ap_global.h"
#include <WebServer.h>

// ================= Web服务器定义 =================
WebServer server(80);
// 简单网页（箭头控制）
const char html_page[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>XuegeBot 网页控制</title>
<style>
body {
  font-family: sans-serif;
  text-align: center;
  background: #f4f4f4;
}
button {
  width: 80px;
  height: 80px;
  font-size: 32px;
  margin: 10px;
  border-radius: 20px;
  border: none;
  background: #4285f4;
  color: white;
  box-shadow: 0 4px 10px rgba(0,0,0,0.2);
}
button:active {
  background: #2a5bd7;
}
#panel {
  display: inline-grid;
  grid-template-columns: 100px 100px 100px;
  grid-template-rows: 100px 100px 100px;
  justify-content: center;
  align-items: center;
  margin-top: 40px;
}
#val {
  margin-top: 20px;
  font-size: 20px;
}
</style>
</head>
<body>
  <h2>🕹️ XuegeBot 方向控制</h2>
  <div id="panel">
    <div></div>
    <button id="up">↑</button>
    <div></div>
    <button id="left">←</button>
    <button id="stop">⏹</button>
    <button id="right">→</button>
    <div></div>
    <button id="down">↓</button>
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

// ============= WebServer 相关函数 =============
void handleRoot() {
    server.send(200, "text/html", html_page);
}

float http_vx = 0;
float http_vz = 0;

void handleSet() {
    if (server.hasArg("vx")) http_vx = server.arg("vx").toFloat();
    if (server.hasArg("vz")) http_vz = server.arg("vz").toFloat();
    static float target_motor_speed1, target_motor_speed2;
    // 运动学逆解计算电机目标速度
    kinematics.kinematic_inverse(http_vx* 1000, http_vz, target_motor_speed1, target_motor_speed2);

    pid_controller[0].update_target(target_motor_speed1);
    pid_controller[1].update_target(target_motor_speed2);

    log_debug("web", "recv vx=%.2f vz=%.2f,l1:%.2f,l2:%.2f", http_vx, http_vz,target_motor_speed1,target_motor_speed2);
    server.send(200, "text/html",
                "<h3>接收成功</h3><p>vx=" + String(http_vx) + ", vz=" + String(http_vz) +
                "</p><a href='/'>返回</a>");
}

void startWebServer() {
    server.on("/", handleRoot);
    server.on("/set", handleSet);
    server.begin();
    log_debug("web", "WebServer started at http://%s", WiFi.localIP().toString().c_str());
}

// 供主循环调用
void wifi_server_loop() {
    if (wifi_status == WIFI_STATUS_GOT_IP) {
        server.handleClient();
    }
}

bool Board::board_init() {

    pinMode(2, OUTPUT);
    if (!serial_init()) while (true);  
    if (!oled_init()) while (true);
    if (!motor_init()) while (true);
    if (!encoder_init()) while (true);
    if (!button_init()) while (true);
    if (!battery_init()) while (true);

    imu.begin(18, 19);

    pid_controller[0].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), config.kinematics_pid_kd());
    pid_controller[1].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), config.kinematics_pid_kd());
    pid_controller[0].out_limit(-config.kinematics_pid_out_limit(), config.kinematics_pid_out_limit());
    pid_controller[1].out_limit(-config.kinematics_pid_out_limit(), config.kinematics_pid_out_limit());

    kinematics.set_motor_param(0, config.kinematics_reducation_ration(), config.kinematics_pulse_ration(), config.kinematics_wheel_diameter());
    kinematics.set_motor_param(1, config.kinematics_reducation_ration(), config.kinematics_pulse_ration(), config.kinematics_wheel_diameter());
    kinematics.set_kinematic_param(config.kinematics_wheel_distance());

    return true;
}

bool Board::serial_init(){

    Serial.begin(115200);
    log_set_target(Serial);
    config.init(CONFIG_NAME_NAMESPACE);
    Serial.println(FIRST_START_TIP);
    Serial.println(config.config_str());
    if (config.microros_serial_id() == 2) {
        Serial2.begin(115200);
    }
    return true;
}

bool Board::battery_init(){
    battery.init();

    return true;
}

bool Board::oled_init(){

    display.updateVersionCode(VERSION_CODE);
    display.init();
    display.updateTransMode(config.microros_transport_mode());
    display.updateBaudRate(config.serial_baudrate());
    display.updateStartupInfo();

    return true;
}

bool Board::motor_init(){

    motor.attachMotor(0, CONFIG_DEFAULT_MOTOR0_A_GPIO, CONFIG_DEFAULT_MOTOR0_B_GPIO);
    motor.attachMotor(1, CONFIG_DEFAULT_MOTOR1_A_GPIO, CONFIG_DEFAULT_MOTOR1_B_GPIO);

    return true;
}

bool Board::button_init(){

    button.attachDoubleClick(doubleClick);
    button.attachClick(oneClick);
    return true;

}

bool Board::encoder_init(){

    encoders[0].init(CONFIG_DEFAULT_PCNT_UTIL_00, CONFIG_DEFAULT_ENCODER0_A_GPIO, CONFIG_DEFAULT_ENCODER0_B_GPIO);
    encoders[1].init(CONFIG_DEFAULT_PCNT_UTIL_01, CONFIG_DEFAULT_ENCODER1_A_GPIO, CONFIG_DEFAULT_ENCODER1_B_GPIO);

    return true;
}
// ================= WiFi事件回调 =================
void WiFiEventCB(WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.println("WIFI EVENT!");
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
                display.updateWIFIInfo(String("unknow:") + String(int(info.wifi_sta_disconnected.reason)), WIFI_STATUS_UNKNOW);
                wifi_status = WIFI_STATUS_UNKNOW;
            }
            break;

        case SYSTEM_EVENT_STA_GOT_IP:
            wifi_status = WIFI_STATUS_GOT_IP;
            display.updateWIFIInfo("got ip", WIFI_STATUS_GOT_IP);
            display.updateWIFIIp(WiFi.localIP().toString());
            startWebServer();   // ★ 连接成功后启动网页服务器
            break;

        case SYSTEM_EVENT_STA_LOST_IP:
            wifi_status = WIFI_STATUS_WAIT_CONNECT;
            display.updateWIFIInfo("wait connect", WIFI_STATUS_WAIT_CONNECT);
            break;
    }
}

// ================= 按键回调 =================
void doubleClick() {
    log_debug("key", "doubleClick() detected.");
    if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT) {
        config.config("microros_mode", "serial");
    } else {
        config.config("microros_mode", "udp_client");
    }
    esp_restart();
}

void oneClick() {
    static uint8_t display_mode = 0;
    display.updateDisplayMode(display_mode++);
}
