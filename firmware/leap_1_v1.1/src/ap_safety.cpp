#include "ap_safety.h"

#include <math.h>

namespace
{
enum PumpCommandSource
{
    PUMP_SOURCE_NONE = 0,
    PUMP_SOURCE_AGENT = 1,
    PUMP_SOURCE_WEB = 2,
};

enum MotionCommandSource
{
    MOTION_SOURCE_NONE = 0,
    MOTION_SOURCE_AGENT = 1,
    MOTION_SOURCE_WEB = 2,
};

constexpr uint32_t CMD_VEL_TIMEOUT_MS = 500;

states agent_state = WAITING_AGENT;
uint8_t pump_gpio_in_use = 255;
bool pump_output_state = false;
uint32_t pump_last_command_ms = 0;
PumpCommandSource pump_command_source = PUMP_SOURCE_NONE;
uint32_t motion_last_command_ms = 0;
MotionCommandSource motion_command_source = MOTION_SOURCE_NONE;

bool motion_targets_active()
{
    return fabsf(pid_controller[0].target_) > 1e-3f || fabsf(pid_controller[1].target_) > 1e-3f;
}

uint8_t pump_active_level_gpio()
{
    return config.pump_active_level() ? HIGH : LOW;
}

uint8_t pump_inactive_level_gpio()
{
    return config.pump_active_level() ? LOW : HIGH;
}

void write_pump_output(bool enabled)
{
    if (pump_gpio_in_use == 255) {
        return;
    }

    digitalWrite(pump_gpio_in_use, enabled ? pump_active_level_gpio() : pump_inactive_level_gpio());
    pump_output_state = enabled;
}

void force_motion_stop_internal(const char *reason)
{
    const bool was_active = motion_targets_active();
    pid_controller[0].update_target(0.0f);
    pid_controller[1].update_target(0.0f);
    motion_command_source = MOTION_SOURCE_NONE;
    motion_last_command_ms = millis();

    if (was_active) {
        log_debug("safety", "%s", reason);
    }
}
} // namespace

void safety_init()
{
    const uint8_t configured_gpio = static_cast<uint8_t>(config.pump_gpio());
    if (pump_gpio_in_use != 255 && pump_gpio_in_use != configured_gpio) {
        pinMode(pump_gpio_in_use, INPUT);
    }

    pump_gpio_in_use = configured_gpio;
    agent_state = state;
    pinMode(pump_gpio_in_use, OUTPUT);
    pump_last_command_ms = millis();
    pump_command_source = PUMP_SOURCE_NONE;
    motion_last_command_ms = millis();
    motion_command_source = MOTION_SOURCE_NONE;
    write_pump_output(false);

    log_debug(
        "safety",
        "pump init gpio=%u active_level=%u timeout=%lums",
        pump_gpio_in_use,
        config.pump_active_level() ? 1 : 0,
        config.pump_timeout_ms());
}

void safety_loop()
{
    if (motion_command_source != MOTION_SOURCE_NONE) {
        if (motion_command_source == MOTION_SOURCE_AGENT && agent_state != AGENT_CONNECTED) {
            force_motion_stop_internal("agent disconnected, force stop motors");
        } else if (CMD_VEL_TIMEOUT_MS > 0 && (millis() - motion_last_command_ms) > CMD_VEL_TIMEOUT_MS) {
            if (motion_command_source == MOTION_SOURCE_WEB) {
                force_motion_stop_internal("web motion timeout, force stop motors");
            } else {
                force_motion_stop_internal("cmd_vel timeout, force stop motors");
            }
        }
    }

    if (pump_output_state && pump_command_source == PUMP_SOURCE_AGENT && agent_state != AGENT_CONNECTED) {
        safety_force_pump_off();
        return;
    }

    const uint32_t timeout_ms = config.pump_timeout_ms();
    if (pump_output_state && timeout_ms > 0 && (millis() - pump_last_command_ms) > timeout_ms) {
        log_debug("safety", "pump timeout, force off");
        safety_force_pump_off();
    }
}

void safety_force_pump_off()
{
    pump_last_command_ms = millis();
    pump_command_source = PUMP_SOURCE_NONE;
    write_pump_output(false);
}

void safety_set_pump_command(bool enabled)
{
    pump_last_command_ms = millis();
    if (enabled && agent_state != AGENT_CONNECTED) {
        log_debug("safety", "reject pump on while agent disconnected");
        safety_force_pump_off();
        return;
    }

    pump_command_source = enabled ? PUMP_SOURCE_AGENT : PUMP_SOURCE_NONE;
    write_pump_output(enabled);
}

void safety_set_web_pump_command(bool enabled)
{
    pump_last_command_ms = millis();
    pump_command_source = enabled ? PUMP_SOURCE_WEB : PUMP_SOURCE_NONE;
    write_pump_output(enabled);
}

bool safety_pump_enabled()
{
    return pump_output_state;
}

void safety_force_motion_stop()
{
    force_motion_stop_internal("force stop motors");
}

void safety_on_cmd_vel_received()
{
    motion_last_command_ms = millis();
    motion_command_source = MOTION_SOURCE_AGENT;
}

void safety_on_web_motion_command_received()
{
    motion_last_command_ms = millis();
    motion_command_source = MOTION_SOURCE_WEB;
}

void safety_on_agent_state_changed(states new_state)
{
    agent_state = new_state;
    if (agent_state != AGENT_CONNECTED && motion_command_source == MOTION_SOURCE_AGENT) {
        force_motion_stop_internal("agent state changed, stop motors");
    }
    if (agent_state != AGENT_CONNECTED && pump_command_source == PUMP_SOURCE_AGENT) {
        safety_force_pump_off();
    }
}
