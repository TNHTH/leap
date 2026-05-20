#include "oled_display.h"

void OledDisplay::init()
{
    Wire.begin(18, 19, 400000UL);
    _display = Adafruit_SSD1306(128, 64, &Wire);
    _display.begin(SSD1306_SWITCHCAPVCC, 0x3C); // 设置OLED的I2C地址
    _display.clearDisplay();                    // 清空屏幕
    _display.setTextSize(1);                    // 设置字体大小
    _display.setTextColor(SSD1306_WHITE);       // 设置字体颜色
    _display.setCursor(0, 0);                   // 设置开始显示文字的坐标
    _display.print("    ");
    _display.println(version_code_); // 输出的字符
    _display.println("");
    _display.println("syetem starting...");
    _display.display();
}

OledDisplay::OledDisplay()
{
}

void OledDisplay::updateDisplay()
{
    if (millis() - last_update_time > update_interval)
    {
        String timenow = String(hour()) + ":" + twoDigits(minute()) + ":" + twoDigits(second());
        last_update_time = millis();
        _display.clearDisplay();
        _display.setCursor(0, 0);
        _display.print("    ");
        _display.println(version_code_);
        _display.print("mode:");
        _display.println(mode_);
        if (mode_ == "udp_client")
        {
            // 连接成功显示当前ip，电压，线速度和角速度
            if (wifi_status_ == WIFI_STATUS_OK)
            {
                _display.print("time :");
                _display.println(timenow);
                _display.print("ip:");
                _display.println(wifi_ip_);
                _display.print("voltage :");
                _display.println(battery_info_);
                _display.print("linear  :");
                _display.println(bot_linear_);
                _display.print("angular :");
                _display.println(bot_angular_);
            }
            // ping 失败，则显示当前ip，服务ip和wifi名称
            else if (wifi_status_ == WIFI_STATUS_PING_FAILED || wifi_status_ == WIFI_STATUS_GOT_IP)
            {
                _display.print("wifi:");
                _display.println(wifi_info_);
                _display.print("ip:");
                _display.println(wifi_ip_);
                _display.print("ssid:");
                _display.println(wifi_ssid_);
                _display.print("sip:");
                _display.println(wifi_server_ip_);
            }
            // 找不到wifi，密码错误，则显示wifi名称，密码
            else
            {
                _display.print("wifi:");
                _display.println(wifi_info_);
                _display.print("ssid:");
                _display.println(wifi_ssid_);
                _display.print("pswd:");
                _display.println(wifi_pswd_);
            }
        }
        else
        {
            _display.print("time :");
            _display.println(timenow);
            _display.print("baud :");
            _display.println(baudrate_);
            _display.print("voltage :");
            _display.println(battery_info_);
            _display.print("linear  :");
            _display.println(bot_linear_);
            _display.print("angular :");
            _display.println(bot_angular_);
        }
        _display.display();
    }
}

void OledDisplay::updateVersionCode(String version_code)
{
    version_code_ = version_code;
}

void OledDisplay::updateBatteryInfo(float &battery_info)
{
    battery_info_ = battery_info;
}
void OledDisplay::updateUltrasoundDist(float &ultrasound_distance)
{
    ultrasound_distance_ = ultrasound_distance;
}
void OledDisplay::updateBotAngular(float &bot_angular)
{
    bot_angular_ = bot_angular;
}
void OledDisplay::updateBotLinear(float &bot_linear)
{
    bot_linear_ = bot_linear;
}
void OledDisplay::updateTransMode(String mode)
{
    mode_ = mode;
}
void OledDisplay::updateWIFIServerIp(String server_ip)
{
    wifi_server_ip_ = server_ip;
}
void OledDisplay::updateWIFIIp(String ip)
{
    if (wifi_ip_ != ip)
    {
        wifi_ip_ = ip;
    }
    // 判断LocalIP 和 Server IP 是否在同一个子网，不在则 WARN
}
void OledDisplay::updateWIFIInfo(String info, wifi_status_t status)
{
    if (wifi_info_ != info)
    {
        wifi_info_ = info;
    }
    wifi_status_ = status;
}
void OledDisplay::updateCurrentTime(int64_t current_time_)
{
    current_time = current_time_;
}
String OledDisplay::twoDigits(int digits)
{
    if (digits < 10)
    {
        String i = '0' + String(digits);
        return i;
    }
    else
    {
        return String(digits);
    }
}

void OledDisplay::updateBaudRate(uint32_t baudrate)
{
    baudrate_ = baudrate;
}

void OledDisplay::updateStartupInfo()
{
    String timenow = String(hour()) + ":" + twoDigits(minute()) + ":" + twoDigits(second());
    last_update_time = millis();
    _display.clearDisplay();
    _display.setCursor(0, 0);
    _display.print("    ");
    _display.println(version_code_); // 输出的字符
    _display.print("mode:");
    _display.println(mode_);
    _display.print("voltage:");
    _display.println(battery_info_);
    _display.println("");
    _display.println("syetem starting...");
    _display.display();
}

void OledDisplay::updateDisplayMode(uint8_t display_mode)
{
    display_mode_ = display_mode;
}

void OledDisplay::updateWIFISSID(String ssid)
{
    wifi_ssid_ = ssid;
}
void OledDisplay::updateWIFIPSWD(String pswd)
{
    wifi_pswd_ = pswd.length() == 0 ? "" : "******";
}
