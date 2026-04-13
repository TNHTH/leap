# xuegecar_fire_inspection

ROS 2 fire inspection package for Leap1. It provides:

- `camera_node`: USB camera capture, `/camera/image_raw`, and MJPEG streaming
- `fire_detector_node`: HSV and contour based fire detection with debounced output
- `mission_manager_node`: Nav2 waypoint patrol, fire response, pump control, and video recording
- `pump_guard_node`: startup/shutdown and heartbeat based pump shutdown guard

The default parameters are installed in `config/fire_inspection.yaml`.
