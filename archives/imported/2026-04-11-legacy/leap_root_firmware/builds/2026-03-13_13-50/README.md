# Leap1 Dual Fix Preconfigured Build 2026-03-13 13:50 CST

## 产物
- `leap1_dual_fix_preconfigured_merged_2026-03-13_13-50.bin`

## 用途
- 这是“刷完即用”的整包镜像。
- 已包含：
  - 新版 dual-fix 固件
  - 预置 NVS 用户配置

## 已预置的配置
- `microros_mode=udp_client`
- `wifi_ssid=TNHTH`
- `wifi_pswd=<预置，本文不回写明文>`
- `udpserver_ip=192.168.5.17`
- `udpserver_port=8888`
- `first_startup=0`

## 烧录方式
- 直接作为 `0x0` 整包镜像烧录即可。
- 镜像布局：
  - `0x1000` bootloader
  - `0x8000` partitions
  - `0x9000` nvs
  - `0x10000` firmware

## SHA256
- `47de9791fd698105609909cd6258ddde57aa7fa6c7fd739d8bfb43dedd004e75`
