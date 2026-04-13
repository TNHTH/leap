#ifndef AP_HW_INIT_H
#define AP_HW_INIT_H

#include "leapbot.h"

class Board {
public:
    bool board_init();

private:
    bool serial_init();
    bool oled_init();
    bool motor_init();
    bool encoder_init();
    bool button_init();
    bool battery_init();
};

void WiFiEventCB(WiFiEvent_t event, WiFiEventInfo_t info);
void doubleClick();
void oneClick();

#endif // AP_HW_INIT_H
