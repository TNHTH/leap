#ifndef BSP_BATTERY_H
#define BSP_BATTERY_H

#include <Arduino.h>

class Battery {
public:
    Battery(uint8_t pin = 34, float scale = 5.02f);

    void init();        // 初始化（一次性）
    void update();      // 更新数据（周期性）
    float voltage() const { return _voltage; }

private:
    uint8_t _pin;
    float _scale;
    float _voltage;
};

#endif // BSP_BATTERY_H
