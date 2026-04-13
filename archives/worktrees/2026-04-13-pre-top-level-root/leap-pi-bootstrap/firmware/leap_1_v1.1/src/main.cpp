#include <Arduino.h>
#include "leapbot.h"
#include "tasks.h"

void setup() {
    Serial.begin(115200);
    Board esp32s3;

    if (!esp32s3.board_init()) while (1);

    // 启动所有任务
    start_all_tasks();
}

void loop() {}
