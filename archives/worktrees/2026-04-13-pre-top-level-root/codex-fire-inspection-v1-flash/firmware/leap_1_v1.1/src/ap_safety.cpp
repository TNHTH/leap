#include "ap_safety.h"

namespace
{
constexpr uint32_t kCmdVelTimeoutMs = 1000;

states agent_state = WAITING_AGENT;
uint8_t pump_gpio_in_use = CONFIG_DEFAULT_SERVP05_GPIO;
uint32_t last_cmd_vel_ms = 0;
bool pump_output_state = false;
bool pump_commanded_on = false;
uint32_t pump_last_command_ms = 0;

uint8_t pump_active_level()
{
    return config.pump_active_level() ? HIGH : LOW;
}

uint8_t pump_inactive_level()
{
    return config.pump_active_level() ? LOW : HIGH;
}

void write_pump_output(bool enabled)
{
    digitalWrite(pump_gpio_in_use, enabled ? pump_active_level() : pump_inactive_level());
    pump_output_state = enabled;
}
} // namespace

void safety_init()
{
    const uint8_t configured_gpio = static_cast<uint8_t>(config.pump_gpio());
    if (pump_gpio_in_use != configured_gpio) {
        pinMode(pump_gpio_in_use, INPUT);
        pump_gpio_in_use = configured_gpio;
    }

    pinMode(pump_gpio_in_use, OUTPUT);
    pump_commanded_on = false;
    pump_last_command_ms = millis();
    last_cmd_vel_ms = millis();
    write_pump_output(false);
    safety_stop_motion();
}

void safety_loop()
{
    const uint32_t now = millis();

    if (agent_state != AGENT_CONNECTED) {
        safety_stop_motion();
        safety_force_pump_off();
        return;
    }

    if (pump_output_state && config.pump_timeout_ms() > 0 &&
        (now - pump_last_command_ms) > config.pump_timeout_ms()) {
        log_debug("safety", "pump timeout, force off");
        safety_force_pump_off();
    }

    if ((now - last_cmd_vel_ms) > kCmdVelTimeoutMs) {
        safety_stop_motion();
    }
}

void safety_stop_motion()
{
    pid_controller[0].update_target(0.0f);
    pid_controller[1].update_target(0.0f);
    motor.updateMotorSpeed(0, 0.0f);
    motor.updateMotorSpeed(1, 0.0f);
}

void safety_force_pump_off()
{
    pump_commanded_on = false;
    pump_last_command_ms = millis();
    write_pump_output(false);
}

void safety_set_pump_command(bool enabled)
{
    pump_commanded_on = enabled;
    pump_last_command_ms = millis();
    if (enabled && agent_state != AGENT_CONNECTED) {
        safety_force_pump_off();
        return;
    }

    if (enabled) {
        write_pump_output(true);
        return;
    }

    safety_force_pump_off();
}

bool safety_pump_enabled()
{
    return pump_output_state;
}

void safety_on_cmd_vel_received()
{
    last_cmd_vel_ms = millis();
}

void safety_on_agent_state_changed(states new_state)
{
    agent_state = new_state;
    if (agent_state == AGENT_CONNECTED) {
        last_cmd_vel_ms = millis();
        return;
    }

    safety_stop_motion();
    safety_force_pump_off();
}

bool safety_serial_config_enabled()
{
    return config.microros_transport_mode() != CONFIG_TRANSPORT_MODE_SERIAL;
}
