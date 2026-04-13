# Leap1 Dual Fix Build 2026-03-13 13:41 CST

## 产物
- `leap1_dual_fix_merged_2026-03-13_13-41.bin`

## 烧录方式
- 这是可直接整包烧录的 merged bin。
- 布局：
  - `0x1000` `bootloader.bin`
  - `0x8000` `partitions.bin`
  - `0x10000` `firmware.bin`

## 本次修复点
- 修复 `micro-ROS` 建链失败被错误当成成功继续的问题。
- 修复消息字符串和 transport 实体在重复建链/销毁时的状态复位。
- 修复左右独立运动学参数未真正接入的问题。
- 下调低速死区阈值并提供保守的通用低速起步补偿默认值。

## SHA256
- `b86936c4b63cd4db486abe58a0458d311d6c36a8df9e490f517f11d5b21d322d`
