#include "bsp_battery.h"

Battery::Battery(uint8_t pin, float scale)
    : _pin(pin), _scale(scale), _voltage(0.0f) {}

void Battery::init() {
    pinMode(_pin, INPUT);
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
}

void Battery::update() {
    int mv = analogReadMilliVolts(_pin);
    _voltage = _scale * (mv * 1e-3f);
}
