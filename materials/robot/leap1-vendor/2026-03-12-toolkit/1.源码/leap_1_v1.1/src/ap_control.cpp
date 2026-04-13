#include "ap_control.h"
#include "ap_global.h"


void loop_control() {
    static float out_motor_speed[2];
    static uint64_t last_update_info_time = millis();
    static uint8_t index;

    // 更新运动学和编码器数据
    kinematics.update_motor_ticks(micros(), encoders[0].getTicks(), encoders[1].getTicks());
    // PID控制电机速度
    for (index = 0; index < 2; index++) {
        if (pid_controller[index].target_ == 0) {
            out_motor_speed[index] = 0;
        } else {
            out_motor_speed[index] = pid_controller[index].update(kinematics.motor_speed(index));
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
        Serial.print("$result=ok\n");
    }
}