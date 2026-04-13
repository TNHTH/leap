#ifndef AP_GLOBAL_H
#define AP_GLOBAL_H

// 先声明状态枚举，避免与 leapbot.h 的循环包含导致类型不可见。
enum states
{
    WAITING_AGENT,
    AGENT_AVAILABLE,
    AGENT_CONNECTED,
    AGENT_DISCONNECTED
};

#include "leapbot.h"
// // MicroROS执行器&节点全局变量
extern rclc_executor_t executor;

// 状态&硬件相关全局变量（关键：添加 extern 声明）
extern enum states state;  // 仅声明，不定义
extern wifi_status_t wifi_status;  // 确保声明
extern PidController pid_controller[2];
extern Esp32PcntEncoder encoders[2];
extern Esp32McpwmMotor motor;
extern Kinematics kinematics;
extern LeapBotConfig config;
extern OledDisplay display;
extern BluetoothSerial SerialBT;
extern float battery_voltage;
extern OneButton button;
extern MPU6050 mpu;
extern ImuDriver imu;
extern imu_t imu_data;
extern Battery battery;
extern volatile int32_t debug_cmd_vel_count;
extern volatile float debug_target_motor_speed[2];
extern volatile float debug_motor_output[2];
extern volatile float debug_motor_speed[2];

#endif // AP_GLOBAL_H
