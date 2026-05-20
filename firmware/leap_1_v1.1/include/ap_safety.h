#ifndef AP_SAFETY_H
#define AP_SAFETY_H

#include <Arduino.h>

#include "ap_global.h"

void safety_init();
void safety_loop();
void safety_force_pump_off();
void safety_set_pump_command(bool enabled);
void safety_set_web_pump_command(bool enabled);
bool safety_pump_enabled();
void safety_force_motion_stop();
void safety_on_cmd_vel_received();
void safety_on_web_motion_command_received();
void safety_on_agent_state_changed(states new_state);

#endif // AP_SAFETY_H
