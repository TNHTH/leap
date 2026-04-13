#ifndef AP_ROS_TRANSPORT_H
#define AP_ROS_TRANSPORT_H
#include "ap_global.h"

bool setup_transport(); // 传输模式初始化
bool create_transport(); // ROS节点/发布者/订阅者创建
bool destory_transport(); // ROS资源销毁
bool microros_setup_transport_udp_client_(); // UDP客户端传输初始化
bool microros_setup_transport_serial_(HardwareSerial& serial); // 串口传输初始化

#endif // AP_ROS_TRANSPORT_H