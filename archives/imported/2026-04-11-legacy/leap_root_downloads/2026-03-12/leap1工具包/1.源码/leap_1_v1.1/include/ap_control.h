#ifndef AP_CONTROL_H
#define AP_CONTROL_H

void loop_control(); // 核心控制循环（电机、显示、按键、IMU更新）
void loop_transport(); // ROS传输状态管理循环
void deal_command(char key[32], char value[32]); // 串口命令处理

#endif // AP_CONTROL_H