#include "ap_global.h"


// // MicroROS执行器&节点初始化
rclc_executor_t executor = {};

// 状态&硬件相关初始化（关键：初始化全局变量）
enum states state = WAITING_AGENT;
wifi_status_t wifi_status = WIFI_STATUS_WAIT_CONNECT;  // 初始化
PidController pid_controller[2] = {};
Esp32PcntEncoder encoders[2] = {};
Esp32McpwmMotor motor = {};
Kinematics kinematics = {};
LeapBotConfig config = {};
OledDisplay display = {};
BluetoothSerial SerialBT = {};
float battery_voltage = 0.0f;
OneButton button(0, true);
MPU6050 mpu(Wire);
ImuDriver imu(mpu);
imu_t imu_data = {};
Battery battery(34, 5.02f);
volatile int32_t debug_cmd_vel_count = 0;
volatile float debug_target_motor_speed[2] = {0.0f, 0.0f};
volatile float debug_motor_output[2] = {0.0f, 0.0f};
volatile float debug_motor_speed[2] = {0.0f, 0.0f};
