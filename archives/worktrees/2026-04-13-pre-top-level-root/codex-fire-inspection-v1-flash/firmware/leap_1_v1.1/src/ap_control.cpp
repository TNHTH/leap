#include "ap_control.h"

#include <math.h>

#include "ap_global.h"
#include "ap_safety.h"

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

void update_agent_state(states new_state)
{
    if (state == new_state) {
        return;
    }
    state = new_state;
    safety_on_agent_state_changed(new_state);
}
} // namespace

void refresh_control_config()
{
    refresh_motor_compensation_config();
}

void loop_control()
{
    static float out_motor_speed[2];
    static uint8_t index = 0;
    static float current_motor_speed = 0.0f;

    kinematics.update_motor_ticks(micros(), encoders[0].getTicks(), encoders[1].getTicks());
    for (index = 0; index < 2; index++) {
        current_motor_speed = kinematics.motor_speed(index);
        debug_motor_speed[index] = current_motor_speed;
        if (fabsf(pid_controller[index].target_) <= motor_target_epsilon) {
            out_motor_speed[index] = 0.0f;
        } else {
            out_motor_speed[index] = pid_controller[index].update(current_motor_speed);
            out_motor_speed[index] =
                apply_motor_compensation(index, pid_controller[index].target_, current_motor_speed, out_motor_speed[index]);
        }
        debug_motor_output[index] = out_motor_speed[index];
        motor.updateMotorSpeed(index, out_motor_speed[index]);
    }

    if (out_motor_speed[0] == 0.0f && out_motor_speed[1] == 0.0f) {
        battery_voltage = 5.02f * (static_cast<float>(analogReadMilliVolts(34)) * 1e-3f);
        display.updateBatteryInfo(battery_voltage);
    }

    safety_loop();
    display.updateCurrentTime(rmw_uros_epoch_millis());
    display.updateDisplay();
    button.tick();
    imu.update();
}

void loop_transport()
{
    static char result[10][32];
    static int config_result = CONFIG_PARSE_NODATA;

    if (safety_serial_config_enabled()) {
        while (Serial.available()) {
            const int c = Serial.read();
            config_result = config.loop_config_uart(c, result);
            if (config_result == CONFIG_PARSE_OK) {
                deal_command(result[0], result[1]);
            } else if (config_result == CONFIG_PARSE_ERROR) {
                Serial.print("$result=error parse\n");
            }
        }
    }

    switch (state) {
    case WAITING_AGENT:
        if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT &&
            wifi_status != WIFI_STATUS_GOT_IP && WiFi.status() != WL_CONNECTED) {
            break;
        }
        EXECUTE_EVERY_N_MS(
            5000,
            update_agent_state((RMW_RET_OK == rmw_uros_ping_agent(300, 5)) ? AGENT_AVAILABLE : WAITING_AGENT););
        digitalWrite(2, !digitalRead(2));
        if (state == WAITING_AGENT && wifi_status == WIFI_STATUS_GOT_IP) {
            display.updateWIFIInfo("ping timeout", WIFI_STATUS_PING_FAILED);
        }
        break;
    case AGENT_AVAILABLE:
        if (create_transport()) {
            update_agent_state(AGENT_CONNECTED);
            display.updateWIFIInfo("ping ok", WIFI_STATUS_OK);
        } else {
            log_debug("ros2", "create_transport failed, keep waiting agent");
            destory_transport();
            update_agent_state(WAITING_AGENT);
        }
        break;
    case AGENT_CONNECTED:
        EXECUTE_EVERY_N_MS(
            5000,
            update_agent_state((RMW_RET_OK == rmw_uros_ping_agent(300, 5)) ? AGENT_CONNECTED : AGENT_DISCONNECTED););
        if (state == AGENT_DISCONNECTED && wifi_status == WIFI_STATUS_GOT_IP) {
            display.updateWIFIInfo("ping timeout", WIFI_STATUS_PING_FAILED);
            break;
        }
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
        break;
    case AGENT_DISCONNECTED:
        destory_transport();
        update_agent_state(WAITING_AGENT);
        break;
    default:
        break;
    }

    if (state != AGENT_CONNECTED) {
        delay(10);
    }
}

void deal_command(char key[32], char value[32])
{
    if (strcmp(key, "command") == 0) {
        if (strcmp(value, "restart") == 0) {
            safety_force_pump_off();
            stop_motion();
            esp_restart();
        } else if (strcmp(value, "read_config") == 0) {
            Serial.print(config.config_str());
        }
        return;
    }

    if (strcmp(key, "pid_kp") == 0) {
        const float kp = atof(value);
        pid_controller[0].update_pid(kp, config.kinematics_pid_ki(), config.kinematics_pid_kd());
        pid_controller[1].update_pid(kp, config.kinematics_pid_ki(), config.kinematics_pid_kd());
    } else if (strcmp(key, "pid_ki") == 0) {
        const float ki = atof(value);
        pid_controller[0].update_pid(config.kinematics_pid_kp(), ki, config.kinematics_pid_kd());
        pid_controller[1].update_pid(config.kinematics_pid_kp(), ki, config.kinematics_pid_kd());
    } else if (strcmp(key, "pid_kd") == 0) {
        const float kd = atof(value);
        pid_controller[0].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), kd);
        pid_controller[1].update_pid(config.kinematics_pid_kp(), config.kinematics_pid_ki(), kd);
    }

    config.config(String(key), String(value));
    if (is_motor_compensation_key(key)) {
        refresh_motor_compensation_config();
    }
    if (strcmp(key, CONFIG_NAME_PUMP_TIMEOUT_MS) == 0 || strcmp(key, CONFIG_NAME_PUMP_ACTIVE_LEVEL) == 0 ||
        strcmp(key, CONFIG_NAME_PUMP_GPIO) == 0) {
        pump_init();
    }
    Serial.print("$result=ok\n");
}

void stop_motion()
{
    safety_stop_motion();
}

void pump_init()
{
    safety_init();
}

void pump_set(bool enabled)
{
    safety_set_pump_command(enabled);
}

void pump_force_off()
{
    safety_force_pump_off();
}

bool pump_is_enabled()
{
    return safety_pump_enabled();
}

void pump_watchdog_check()
{
    safety_loop();
}

uint32_t pump_timeout_ms()
{
    return config.pump_timeout_ms();
}
