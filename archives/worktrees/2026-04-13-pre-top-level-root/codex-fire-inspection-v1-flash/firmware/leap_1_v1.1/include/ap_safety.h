#ifndef AP_SAFETY_H
#define AP_SAFETY_H

#include <Arduino.h>
#include "ap_global.h"

void safety_init();
void safety_loop();
void safety_stop_motion();
void safety_force_pump_off();
void safety_set_pump_command(bool enabled);
bool safety_pump_enabled();
void safety_on_cmd_vel_received();
void safety_on_agent_state_changed(states new_state);
bool safety_serial_config_enabled();

#endif // AP_SAFETY_H
