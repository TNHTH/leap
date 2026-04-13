# Leap 相机资料索引

## 当前角色划分

- 车载相机链路：
  - 当前 ROS 2 启动参数入口：`ros2_ws/src/leap1/leap1_a20/launch/a20_vehicle.launch.py`
  - 默认参数名：`vehicle_camera_device`
- 固定摄像头链路：
  - 同一 launch 内参数：`with_ground_camera`、`ground_camera_device`、`ground_camera_port`

## 当前主机观察到的设备

- `HJ USB 2.0 Camera`
  - 当前映射：`/dev/video0`、`/dev/video1`
  - 可作为外置相机候选
- `Integrated Camera`
  - 当前映射：`/dev/video2`、`/dev/video3`

说明：实际 `/dev/video*` 编号可能在重插后变化，后续使用前优先重新检查设备名。

## 外部资料入口

- WHEELTEC C100/C70 资料包：
  - `/home/gwh/leap/materials/cameras/wheeltec-c100-c70/2024-08-29`

## 推荐使用顺序

1. 先看资料包中的技术规格书与标定说明
2. 再确认当前主机上的设备号
3. 最后把目标设备填进 `vehicle_camera_device` 或 `ground_camera_device`

