#ifndef AP_CONTROL_H
#define AP_CONTROL_H

#include <stdint.h>

void refresh_control_config();
void loop_control();
void loop_transport();
void deal_command(char key[32], char value[32]);
void stop_motion();
void pump_init();
void pump_set(bool enabled);
void pump_force_off();
bool pump_is_enabled();
void pump_watchdog_check();
uint32_t pump_timeout_ms();

#endif // AP_CONTROL_H
