# Leap1 低速补偿整包固件

生成日期：`2026-03-13`

## 正确烧录文件

- `leap1_low_speed_compensation_merged_2026-03-13.bin`

这是可直接按原厂 `leap1.bin` 方式烧录的 **merged bin**，已经包含：

- bootloader
- partition table
- app firmware

## 不要直接整包烧录的文件

- `../leap_1_v1.1/.pio/build/leap_1/firmware.bin`
- `../builds/2026-03-12/leap1_low_speed_compensation_2026-03-12.bin`

这两个文件本质上都是 **app-only 镜像**，只能刷到 `0x10000`，不能直接替代原厂整包镜像。

## 结构校验

本整包镜像的关键偏移为：

- `0x1000`：bootloader
- `0x8000`：partition table
- `0x10000`：app

## 校验值

见同目录下的 `SHA256SUMS.txt`。
