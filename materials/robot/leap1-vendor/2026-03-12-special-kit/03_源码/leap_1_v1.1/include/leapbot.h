#ifndef __LEAPBOT_H__
#define __LEAPBOT_H__

/* ESP32核心依赖 */
#include <WiFi.h>
#include <Esp32PcntEncoder.h>
#include <Esp32McpwmMotor.h>
#include <PidController.h>
#include <Kinematics.h>
#include <BluetoothSerial.h>
#include <OneButton.h>
#include <ImuDriver.h>
#include "bsp_battery.h"

/* MicroROS核心依赖 */
#include <micro_ros_platformio.h>
#include <rcl/rcl.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <rclc_parameter/rclc_parameter.h>
#include <nav_msgs/msg/odometry.h>
#include <geometry_msgs/msg/twist.h>
#include <micro_ros_utilities/type_utilities.h>
#include <micro_ros_utilities/string_utilities.h>
#include "micro_ros_transport_serial.h"
#include "micro_ros_transport_wifi_udp.h"
#include "sensor_msgs/msg/imu.h"
#include "sensor_msgs/msg/battery_state.h"

/* 自定义依赖 */
#include "log.h"
#include "ap_config.h"
#include "oled_display.h"
#include "leapbot_utils.h"

/* 模块接口声明 */
#include "ap_global.h"
#include "ap_hw_init.h"
#include "ap_ros_transport.h"
#include "ap_control.h"

/* 宏定义 */
#define RCSOFTCHECK(fn)                                                                           \
    {                                                                                             \
        rcl_ret_t temp_rc = fn;                                                                   \
        if ((temp_rc != RCL_RET_OK))                                                              \
        {                                                                                         \
            log_debug("ros2",                                                                 \
                          "Failed status on line %d: %d. Continuing.\n", __LINE__, (int)temp_rc); \
        }                                                                                         \
    }

#define EXECUTE_EVERY_N_MS(MS, X)          \
    do                                     \
    {                                      \
        static volatile int64_t init = -1; \
        if (init == -1)                    \
        {                                  \
            init = millis();               \
        }                                  \
        if (millis() - init > MS)          \
        {                                  \
            X;                             \
            init = millis();               \
        }                                  \
    } while (0);

#endif // __LEAPBOT_H__