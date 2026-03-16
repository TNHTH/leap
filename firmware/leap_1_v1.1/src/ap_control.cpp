#include "ap_control.h"
#include "ap_global.h"
#include <math.h>

namespace
{
struct MotorCompensation
{
    float gain = 1.0f;
    float min_pwm = 0.0f;
    float startup_boost_pwm = 0.0f;
    uint32_t startup_boost_ms = 0;
    float last_target = 0.0f;
    uint32_t startup_deadline_ms = 0;
};

MotorCompensation motor_compensation[2];
float motor_target_epsilon = 5.0f;

float signed_value(float sign_source, float magnitude)
{
    return sign_source >= 0.0f ? magnitude : -magnitude;
}

bool is_motor_compensation_key(const char *key)
{
    return strcmp(key, CONFIG_NAME_MOTOR_TARGET_EPSILON) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR0_COMPENSATION_GAIN) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR1_COMPENSATION_GAIN) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR0_MIN_PWM) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR1_MIN_PWM) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR0_STARTUP_BOOST_PWM) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR1_STARTUP_BOOST_PWM) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR0_STARTUP_BOOST_MS) == 0 ||
           strcmp(key, CONFIG_NAME_MOTOR1_STARTUP_BOOST_MS) == 0;
}

void refresh_motor_compensation_config()
{
    motor_target_epsilon = config.motor_target_epsilon();
    if (motor_target_epsilon < 0.0f) {
        motor_target_epsilon = 0.0f;
    }

    const float output_limit = config.kinematics_pid_out_limit();
    for (uint8_t index = 0; index < 2; ++index) {
        MotorCompensation &item = motor_compensation[index];
        item.gain = config.motor_gain(index);
        if (item.gain <= 0.0f) {
            item.gain = 1.0f;
        }

        item.min_pwm = config.motor_min_pwm(index);
        if (item.min_pwm < 0.0f) {
            item.min_pwm = 0.0f;
        }
        if (item.min_pwm > output_limit) {
            item.min_pwm = output_limit;
        }

        item.startup_boost_pwm = config.motor_startup_boost_pwm(index);
        if (item.startup_boost_pwm < 0.0f) {
            item.startup_boost_pwm = 0.0f;
        }
        if (item.startup_boost_pwm > output_limit) {
            item.startup_boost_pwm = output_limit;
        }

        item.startup_boost_ms = config.motor_startup_boost_ms(index);
    }

    log_debug(
        "motor",
        "compensation eps=%.2f m0[gain=%.2f,min=%.0f,boost=%.0f/%lums] m1[gain=%.2f,min=%.0f,boost=%.0f/%lums]",
        motor_target_epsilon,
        motor_compensation[0].gain,
        motor_compensation[0].min_pwm,
        motor_compensation[0].startup_boost_pwm,
        motor_compensation[0].startup_boost_ms,
        motor_compensation[1].gain,
        motor_compensation[1].min_pwm,
        motor_compensation[1].startup_boost_pwm,
        motor_compensation[1].startup_boost_ms);
}

float apply_motor_compensation(uint8_t index, float target_speed, float current_speed, float pid_output)
{
    MotorCompensation &item = motor_compensation[index];
    const float output_limit = config.kinematics_pid_out_limit();
    const bool target_is_zero = fabsf(target_speed) <= motor_target_epsilon;

    if (target_is_zero) {
        item.last_target = 0.0f;
        item.startup_deadline_ms = 0;
        return 0.0f;
    }

    const bool was_stopped = fabsf(item.last_target) <= motor_target_epsilon;
    const bool direction_changed = item.last_target * target_speed < 0.0f;
    const uint32_t now = millis();
    if ((was_stopped || direction_changed) && item.startup_boost_pwm > 0.0f && item.startup_boost_ms > 0) {
        item.startup_deadline_ms = now + item.startup_boost_ms;
    }

    float output = pid_output * item.gain;
    const bool same_direction = output * target_speed >= 0.0f;
    const bool speed_not_following = fabsf(current_speed) + motor_target_epsilon < fabsf(target_speed);

    if (item.startup_boost_pwm > 0.0f && now < item.startup_deadline_ms && same_direction && speed_not_following) {
        if (fabsf(output) < item.startup_boost_pwm) {
            output = signed_value(target_speed, item.startup_boost_pwm);
        }
    }

    if (item.min_pwm > 0.0f && same_direction && speed_not_following) {
        if (fabsf(output) < item.min_pwm) {
            output = signed_value(target_speed, item.min_pwm);
        }
    }

    item.last_target = target_speed;

    if (output > output_limit) {
        output = output_limit;
    }
    if (output < -output_limit) {
        output = -output_limit;
    }
    return output;
}
} // namespace

void refresh_control_config()
{
    refresh_motor_compensation_config();
}

void loop_control() {
    static float out_motor_speed[2];
    static uint64_t last_update_info_time = millis();
    static uint8_t index;
    static float current_motor_speed;

    // 更新运动学和编码器数据
    kinematics.update_motor_ticks(micros(), encoders[0].getTicks(), encoders[1].getTicks());
    // PID控制电机速度
    for (index = 0; index < 2; index++) {
        current_motor_speed = kinematics.motor_speed(index);
        if (fabsf(pid_controller[index].target_) <= motor_target_epsilon) {
            out_motor_speed[index] = 0;
        } else {
            out_motor_speed[index] = pid_controller[index].update(current_motor_speed);
            out_motor_speed[index] = apply_motor_compensation(index, pid_controller[index].target_, current_motor_speed, out_motor_speed[index]);
        }
        motor.updateMotorSpeed(index, out_motor_speed[index]);
    }

    // 电池电压检测（电机停转时更新）
    if (out_motor_speed[0] == 0 && out_motor_speed[1] == 0) {
        battery_voltage = 5.02 * ((float)analogReadMilliVolts(34) * 1e-3);
        display.updateBatteryInfo(battery_voltage);
    }

    // 显示和外设更新
    display.updateCurrentTime(rmw_uros_epoch_millis());
    display.updateDisplay();
    button.tick();
    imu.update();
}

void loop_transport() {
    static char result[10][32];
    static int config_result;

    // 处理串口配置命令
    while (Serial.available()) {
        int c = Serial.read();
        config_result = config.loop_config_uart(c, result);
        if (config_result == CONFIG_PARSE_OK) {
            deal_command(result[0], result[1]);
        } else if (config_result == CONFIG_PARSE_ERROR) {
            Serial.print("$result=error parse\n");
        }
    }

    // ROS代理连接状态管理
    switch (state) {
        case WAITING_AGENT:
            if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT &&
                wifi_status != WIFI_STATUS_GOT_IP &&
                WiFi.status() != WL_CONNECTED) {
                break;
            }
            EXECUTE_EVERY_N_MS(5000, state = (RMW_RET_OK == rmw_uros_ping_agent(300, 5)) ? AGENT_AVAILABLE : WAITING_AGENT;);
            digitalWrite(2, !digitalRead(2));
            if (state == WAITING_AGENT && wifi_status == WIFI_STATUS_GOT_IP) {
                display.updateWIFIInfo("ping timeout", WIFI_STATUS_PING_FAILED);
            }
            break;
        case AGENT_AVAILABLE:
            state = (true == create_transport()) ? AGENT_CONNECTED : WAITING_AGENT;
            if (state == AGENT_CONNECTED) {
                display.updateWIFIInfo("ping ok", WIFI_STATUS_OK);
            } else {
                log_debug("ros2", "create_transport failed, keep waiting agent");
            }
            if (state == WAITING_AGENT) {
                destory_transport();
            }
            break;
        case AGENT_CONNECTED:
            EXECUTE_EVERY_N_MS(5000, state = (RMW_RET_OK == rmw_uros_ping_agent(300, 5)) ? AGENT_CONNECTED : AGENT_DISCONNECTED;);
            if (state == AGENT_DISCONNECTED && wifi_status == WIFI_STATUS_GOT_IP) {
                display.updateWIFIInfo("ping timeout", WIFI_STATUS_PING_FAILED);
            }
            if (state == AGENT_CONNECTED) {
                if (!rmw_uros_epoch_synchronized()) {
                    RCSOFTCHECK(rmw_uros_sync_session(1000));
                    if (rmw_uros_epoch_synchronized()) {
                        setTime(rmw_uros_epoch_millis() / 1000 + SECS_PER_HOUR * 8);
                        log_debug("xuegebot", "current_time:%ld", rmw_uros_epoch_millis());
                    }
                    delay(10);
                    return;
                }
                digitalWrite(2, !digitalRead(2));
                RCSOFTCHECK(rclc_executor_spin_some(&executor, RCL_MS_TO_NS(100)));
            }
            break;
        case AGENT_DISCONNECTED:
            destory_transport();
            state = WAITING_AGENT;
            break;
        default:
            break;
    }

    if (state != AGENT_CONNECTED) {
        delay(10);
    }
}

void deal_command(char key[32], char value[32]) {
    if (strcmp(key, "command") == 0) {
        if (strcmp(value, "restart") == 0) {
            esp_restart();
        } else if (strcmp(value, "read_config") == 0) {
            Serial.print(config.config_str());
        }
        return;
    } else {
        // 更新PID参数
        if (strcmp(key, "pid_kp") == 0) {
            float kp = atof(value);
            pid_controller[0].update_pid(kp, config.kinematics_pid_ki(), config.kinematics_pid_kd());
            pid_controller[1].update_pid(kp, config.kinematics_pid_ki(), config.kinematics_pid_kd());
        } else if (strcmp(key, "pid_ki") == 0) {
            float ki = atof(value);
            pid_controller[0].update_pid(config.kinematics_pid_kp(), ki, config.kinematics_pid_kd());
            pid_controller[1].update_pid(config.kinematics_pid_kp(), ki, config.kinematics_pid_kd());
        } else if (strcmp(key, "pid_kd") == 0) {
            float kd = atof(value);
            pid_controller[0].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), kd);
            pid_controller[1].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), kd);
        }

        // 存储其他配置
        String recv_key(key);
        String recv_value(value);
        config.config(recv_key, recv_value);
        if (is_motor_compensation_key(key)) {
            refresh_motor_compensation_config();
        }
        Serial.print("$result=ok\n");
    }
}
