#pragma once
#include <Arduino.h>

// 启动所有任务
void start_all_tasks();

// 单独任务声明（如需单独控制，可暴露出来）
void loop_transport_task(void *param);
void loop_control_task(void *param);
void loop_wifi_task(void *param);
void loop_lidar_task(void *param);
