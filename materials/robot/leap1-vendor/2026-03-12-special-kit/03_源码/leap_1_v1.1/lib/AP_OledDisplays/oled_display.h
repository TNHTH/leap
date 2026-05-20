#ifndef __OLED_DISPLAY_H__
#define __OLED_DISPLAY_H__
#include <Wire.h>             // 加载Wire库
#include <Adafruit_GFX.h>     // 加载Adafruit_GFX库
#include <Adafruit_SSD1306.h> // 加载Adafruit_SSD1306库
#include <TimeLib.h>

enum wifi_status_t
{
    WIFI_STATUS_OK,
    WIFI_STATUS_NO_FOUND,
    WIFI_STATUS_PASD_ERROR,
    WIFI_STATUS_WAIT_CONNECT,
    WIFI_STATUS_PING_FAILED,
    WIFI_STATUS_GOT_IP,
    WIFI_STATUS_UNKNOW,
};

class OledDisplay
{
private:
    Adafruit_SSD1306 _display;

    float battery_info_;
    float ultrasound_distance_;
    float bot_angular_;
    float bot_linear_;
    uint32_t baudrate_;
    String mode_;
    String version_code_;
    uint8_t display_mode_;

    int64_t current_time;
    uint64_t last_update_time;
    uint64_t update_interval{1000};

    String wifi_ssid_;
    String wifi_pswd_;
    String wifi_ip_;
    String wifi_server_ip_;
    String wifi_info_ = "wait connect";
    wifi_status_t wifi_status_ = WIFI_STATUS_WAIT_CONNECT;

public:
    void init();
    void updateDisplayMode(uint8_t display_mode);
    void updateDisplay();
    void updateStartupInfo();
    void updateBatteryInfo(float &battery_info);
    void updateUltrasoundDist(float &ultrasound_distance);
    void updateBotAngular(float &bot_angular);
    void updateBotLinear(float &bot_linear);
    void updateTransMode(String mode);
    void updateCurrentTime(int64_t current_time_);
    void updateBaudRate(uint32_t baudrate);
    void updateWIFIIp(String ip);
    void updateWIFIServerIp(String server_ip);
    void updateWIFIInfo(String info, wifi_status_t status);
    void updateWIFISSID(String ssid);
    void updateWIFIPSWD(String pswd);
    void updateVersionCode(String version_code);
    String twoDigits(int digits);
    OledDisplay();
    ~OledDisplay() = default;
};

#endif // __OLED_DISPLAY_H__