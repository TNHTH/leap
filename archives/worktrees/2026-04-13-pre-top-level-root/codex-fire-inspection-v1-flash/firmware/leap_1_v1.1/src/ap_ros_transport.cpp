#include "ap_ros_transport.h"

#include <rosidl_runtime_c/string_functions.h>

geometry_msgs__msg__Twist twist_msg = {};
nav_msgs__msg__Odometry odom_msg = {};
sensor_msgs__msg__Imu imu_msg = {};
sensor_msgs__msg__BatteryState battery_msg = {};
std_msgs__msg__Bool pump_cmd_msg = {};
std_msgs__msg__Bool pump_state_msg = {};
std_msgs__msg__Int32 cmd_vel_count_msg = {};
std_msgs__msg__Float32 motor_target_left_msg = {};
std_msgs__msg__Float32 motor_target_right_msg = {};
std_msgs__msg__Float32 motor_output_left_msg = {};
std_msgs__msg__Float32 motor_output_right_msg = {};
std_msgs__msg__Float32 motor_speed_left_msg = {};
std_msgs__msg__Float32 motor_speed_right_msg = {};
micro_ros_utilities_memory_conf_t conf = {0};

rcl_publisher_t odom_publisher = {};
rcl_publisher_t imu_publisher = {};
rcl_publisher_t battery_publisher = {};
rcl_publisher_t pump_state_publisher = {};
rcl_publisher_t cmd_vel_count_publisher = {};
rcl_publisher_t motor_target_left_publisher = {};
rcl_publisher_t motor_target_right_publisher = {};
rcl_publisher_t motor_output_left_publisher = {};
rcl_publisher_t motor_output_right_publisher = {};
rcl_publisher_t motor_speed_left_publisher = {};
rcl_publisher_t motor_speed_right_publisher = {};
rcl_subscription_t twist_subscriber = {};
rcl_subscription_t pump_cmd_subscriber = {};
rcl_service_t config_service = {};
rcl_wait_set_t wait_set = {};

rcl_init_options_t init_options = {};
rclc_support_t support = {};
rcl_allocator_t allocator = {};
rcl_node_t node = {};
rcl_timer_t timer = {};

namespace
{
bool wifi_event_registered = false;

bool check_rcl_ok(const char *step, rcl_ret_t rc)
{
    if (rc != RCL_RET_OK) {
        log_debug("ros2", "%s failed: %d", step, (int)rc);
        return false;
    }
    return true;
}

void fini_string(rosidl_runtime_c__String *value)
{
    if (value != nullptr && value->data != nullptr) {
        rosidl_runtime_c__String__fini(value);
    }
}

void reset_transport_messages()
{
    fini_string(&odom_msg.header.frame_id);
    fini_string(&odom_msg.child_frame_id);
    fini_string(&imu_msg.header.frame_id);

    memset(&twist_msg, 0, sizeof(twist_msg));
    memset(&odom_msg, 0, sizeof(odom_msg));
    memset(&imu_msg, 0, sizeof(imu_msg));
    memset(&battery_msg, 0, sizeof(battery_msg));
    memset(&pump_cmd_msg, 0, sizeof(pump_cmd_msg));
    memset(&pump_state_msg, 0, sizeof(pump_state_msg));
    memset(&cmd_vel_count_msg, 0, sizeof(cmd_vel_count_msg));
    memset(&motor_target_left_msg, 0, sizeof(motor_target_left_msg));
    memset(&motor_target_right_msg, 0, sizeof(motor_target_right_msg));
    memset(&motor_output_left_msg, 0, sizeof(motor_output_left_msg));
    memset(&motor_output_right_msg, 0, sizeof(motor_output_right_msg));
    memset(&motor_speed_left_msg, 0, sizeof(motor_speed_left_msg));
    memset(&motor_speed_right_msg, 0, sizeof(motor_speed_right_msg));
}

void reset_transport_entities()
{
    odom_publisher = rcl_get_zero_initialized_publisher();
    imu_publisher = rcl_get_zero_initialized_publisher();
    battery_publisher = rcl_get_zero_initialized_publisher();
    pump_state_publisher = rcl_get_zero_initialized_publisher();
    cmd_vel_count_publisher = rcl_get_zero_initialized_publisher();
    motor_target_left_publisher = rcl_get_zero_initialized_publisher();
    motor_target_right_publisher = rcl_get_zero_initialized_publisher();
    motor_output_left_publisher = rcl_get_zero_initialized_publisher();
    motor_output_right_publisher = rcl_get_zero_initialized_publisher();
    motor_speed_left_publisher = rcl_get_zero_initialized_publisher();
    motor_speed_right_publisher = rcl_get_zero_initialized_publisher();
    twist_subscriber = rcl_get_zero_initialized_subscription();
    pump_cmd_subscriber = rcl_get_zero_initialized_subscription();
    config_service = rcl_get_zero_initialized_service();
    wait_set = rcl_get_zero_initialized_wait_set();
    init_options = rcl_get_zero_initialized_init_options();
    memset(&support, 0, sizeof(support));
    allocator = rcl_get_default_allocator();
    node = rcl_get_zero_initialized_node();
    timer = rcl_get_zero_initialized_timer();
    memset(&executor, 0, sizeof(executor));
}

bool prepare_transport_messages(const String &odom_frame_id, const String &odom_child_frame_id)
{
    reset_transport_messages();
    odom_msg.header.frame_id = micro_ros_string_utilities_set(odom_msg.header.frame_id, odom_frame_id.c_str());
    odom_msg.child_frame_id =
        micro_ros_string_utilities_set(odom_msg.child_frame_id, odom_child_frame_id.c_str());
    imu_msg.header.frame_id = micro_ros_string_utilities_set(imu_msg.header.frame_id, "imu");
    if (odom_msg.header.frame_id.data == nullptr || odom_msg.child_frame_id.data == nullptr ||
        imu_msg.header.frame_id.data == nullptr) {
        log_debug("ros2", "failed to allocate frame id strings");
        reset_transport_messages();
        return false;
    }
    return true;
}

bool wifi_services_required()
{
    return config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT ||
           config.lidar_wifi_bridge_enabled() || config.web_control_enabled();
}

void register_wifi_events_once()
{
    if (!wifi_event_registered) {
        WiFi.onEvent(WiFiEventCB);
        wifi_event_registered = true;
    }
}

void ensure_wifi_station_ready()
{
    if (!wifi_services_required()) {
        return;
    }

    const String ssid = config.wifi_sta_ssid();
    const String password = config.wifi_sta_pswd();
    display.updateWIFISSID(ssid);
    display.updateWIFIPSWD(password);
    ensure_wifi_station_connection(ssid.c_str(), password.c_str(), config.board_name());
}
} // namespace

void callback_sensor_publisher_timer_(rcl_timer_t *timer_handle, int64_t last_call_time)
{
    RCLC_UNUSED(last_call_time);
    if (timer_handle == nullptr) {
        return;
    }

    const int64_t stamp = rmw_uros_epoch_millis();
    const odom_t odom = kinematics.odom();

    odom_msg.header.stamp.sec = static_cast<int32_t>(stamp / 1000);
    odom_msg.header.stamp.nanosec = static_cast<uint32_t>((stamp % 1000) * 1000000);
    odom_msg.pose.pose.position.x = odom.x;
    odom_msg.pose.pose.position.y = odom.y;
    odom_msg.pose.pose.orientation.w = odom.quaternion.w;
    odom_msg.pose.pose.orientation.x = odom.quaternion.x;
    odom_msg.pose.pose.orientation.y = odom.quaternion.y;
    odom_msg.pose.pose.orientation.z = odom.quaternion.z;
    odom_msg.twist.twist.angular.z = odom.angular_speed;
    odom_msg.twist.twist.linear.x = odom.linear_speed;

    float odom_angular_speed = odom.angular_speed;
    float odom_linear_speed = odom.linear_speed;
    display.updateBotAngular(odom_angular_speed);
    display.updateBotLinear(odom_linear_speed);
    RCSOFTCHECK(rcl_publish(&odom_publisher, &odom_msg, nullptr));

    if (imu.isEnable()) {
        imu.getImuDriverData(imu_data);
        imu_msg.header.stamp.sec = static_cast<int32_t>(stamp / 1000);
        imu_msg.header.stamp.nanosec = static_cast<uint32_t>((stamp % 1000) * 1000000);
        imu_msg.angular_velocity.x = imu_data.angular_velocity.x;
        imu_msg.angular_velocity.y = imu_data.angular_velocity.y;
        imu_msg.angular_velocity.z = imu_data.angular_velocity.z;
        imu_msg.linear_acceleration.x = imu_data.linear_acceleration.x;
        imu_msg.linear_acceleration.y = imu_data.linear_acceleration.y;
        imu_msg.linear_acceleration.z = imu_data.linear_acceleration.z;
        imu_msg.orientation.x = imu_data.orientation.x;
        imu_msg.orientation.y = imu_data.orientation.y;
        imu_msg.orientation.z = imu_data.orientation.z;
        imu_msg.orientation.w = imu_data.orientation.w;
        RCSOFTCHECK(rcl_publish(&imu_publisher, &imu_msg, nullptr));
    }

    battery.update();
    battery_msg.voltage = battery.voltage();
    battery_msg.current = NAN;
    battery_msg.percentage = NAN;
    battery_msg.power_supply_status = sensor_msgs__msg__BatteryState__POWER_SUPPLY_STATUS_DISCHARGING;
    battery_msg.present = true;
    RCSOFTCHECK(rcl_publish(&battery_publisher, &battery_msg, nullptr));

    pump_state_msg.data = safety_pump_enabled();
    RCSOFTCHECK(rcl_publish(&pump_state_publisher, &pump_state_msg, nullptr));

    cmd_vel_count_msg.data = debug_cmd_vel_count;
    motor_target_left_msg.data = debug_target_motor_speed[0];
    motor_target_right_msg.data = debug_target_motor_speed[1];
    motor_output_left_msg.data = debug_motor_output[0];
    motor_output_right_msg.data = debug_motor_output[1];
    motor_speed_left_msg.data = debug_motor_speed[0];
    motor_speed_right_msg.data = debug_motor_speed[1];
    RCSOFTCHECK(rcl_publish(&cmd_vel_count_publisher, &cmd_vel_count_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_target_left_publisher, &motor_target_left_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_target_right_publisher, &motor_target_right_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_output_left_publisher, &motor_output_left_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_output_right_publisher, &motor_output_right_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_speed_left_publisher, &motor_speed_left_msg, nullptr));
    RCSOFTCHECK(rcl_publish(&motor_speed_right_publisher, &motor_speed_right_msg, nullptr));
}

void callback_twist_subscription_(const void *msgin)
{
    const auto *msg = static_cast<const geometry_msgs__msg__Twist *>(msgin);
    static float target_motor_speed1 = 0.0f;
    static float target_motor_speed2 = 0.0f;

    kinematics.kinematic_inverse(msg->linear.x * 1000.0f, msg->angular.z, target_motor_speed1, target_motor_speed2);
    debug_cmd_vel_count += 1;
    debug_target_motor_speed[0] = target_motor_speed1;
    debug_target_motor_speed[1] = target_motor_speed2;
    pid_controller[0].update_target(target_motor_speed1);
    pid_controller[1].update_target(target_motor_speed2);
    safety_on_cmd_vel_received();
}

void callback_pump_subscription_(const void *msgin)
{
    const auto *msg = static_cast<const std_msgs__msg__Bool *>(msgin);
    safety_set_pump_command(msg->data);
}

bool setup_transport()
{
    register_wifi_events_once();
    if (wifi_services_required()) {
        ensure_wifi_station_ready();
    }

    if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT) {
        log_set_target(Serial);
        const bool ok = microros_setup_transport_udp_client_();
        display.updateTransMode("udp_client");
        return ok;
    }

    if (config.microros_serial_id() == 2) {
        log_debug("ros2", "serial_id=2 disabled because GPIO16 is reserved for pump control");
    }
    log_set_target(Serial);
    const bool ok = microros_setup_transport_serial_(Serial);
    display.updateTransMode("serial");
    return ok;
}

bool create_transport()
{
    const String node_name = config.ros2_nodename();
    const String ros2_namespace = config.ros2_namespace();
    const String twist_topic = config.ros2_twist_topic_name();
    const String odom_topic = config.ros2_odom_topic_name();
    const String odom_frame_id = config.ros2_odom_frameid();
    const String odom_child_frame_id = config.ros2_odom_child_frameid();
    const unsigned int timer_timeout = config.odom_publish_period();

    reset_transport_entities();
    if (!prepare_transport_messages(odom_frame_id, odom_child_frame_id)) {
        return false;
    }
    delay(500);

    if (!check_rcl_ok("rcl_init_options_init", rcl_init_options_init(&init_options, allocator))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rcl_init_options_set_domain_id",
            rcl_init_options_set_domain_id(&init_options, config.ros2_domain_id()))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_support_init_with_options",
            rclc_support_init_with_options(&support, 0, nullptr, &init_options, &allocator))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_node_init_default",
            rclc_node_init_default(&node, node_name.c_str(), ros2_namespace.c_str(), &support))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(odom)",
            rclc_publisher_init_default(
                &odom_publisher, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), odom_topic.c_str()))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(imu)",
            rclc_publisher_init_default(
                &imu_publisher, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu), "imu"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(battery)",
            rclc_publisher_init_default(
                &battery_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState),
                "battery_state"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(pump_state)",
            rclc_publisher_init_default(
                &pump_state_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool),
                "/pump_state"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_cmd_vel_count)",
            rclc_publisher_init_default(
                &cmd_vel_count_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
                "/debug/cmd_vel_count"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_target_left)",
            rclc_publisher_init_default(
                &motor_target_left_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_target_left"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_target_right)",
            rclc_publisher_init_default(
                &motor_target_right_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_target_right"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_output_left)",
            rclc_publisher_init_default(
                &motor_output_left_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_output_left"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_output_right)",
            rclc_publisher_init_default(
                &motor_output_right_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_output_right"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_speed_left)",
            rclc_publisher_init_default(
                &motor_speed_left_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_speed_left"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_publisher_init_default(debug_motor_speed_right)",
            rclc_publisher_init_default(
                &motor_speed_right_publisher,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Float32),
                "/debug/motor_speed_right"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_subscription_init_best_effort(cmd_vel)",
            rclc_subscription_init_best_effort(
                &twist_subscriber,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
                twist_topic.c_str()))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_subscription_init_default(pump_cmd)",
            rclc_subscription_init_default(
                &pump_cmd_subscriber,
                &node,
                ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Bool),
                "/pump_cmd"))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_timer_init_default",
            rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(timer_timeout), callback_sensor_publisher_timer_))) {
        goto fail;
    }
    if (!check_rcl_ok("rclc_executor_init", rclc_executor_init(&executor, &support.context, 3, &allocator))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_executor_add_subscription(cmd_vel)",
            rclc_executor_add_subscription(
                &executor, &twist_subscriber, &twist_msg, &callback_twist_subscription_, ON_NEW_DATA))) {
        goto fail;
    }
    if (!check_rcl_ok(
            "rclc_executor_add_subscription(pump_cmd)",
            rclc_executor_add_subscription(
                &executor, &pump_cmd_subscriber, &pump_cmd_msg, &callback_pump_subscription_, ON_NEW_DATA))) {
        goto fail;
    }
    if (!check_rcl_ok("rclc_executor_add_timer", rclc_executor_add_timer(&executor, &timer))) {
        goto fail;
    }

    return true;

fail:
    destory_transport();
    return false;
}

bool destory_transport()
{
    if (support.context.impl != nullptr) {
        rmw_context_t *rmw_context = rcl_context_get_rmw_context(&support.context);
        (void)rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);
    }
    if (odom_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&odom_publisher, &node));
    }
    if (imu_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&imu_publisher, &node));
    }
    if (battery_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&battery_publisher, &node));
    }
    if (pump_state_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&pump_state_publisher, &node));
    }
    if (cmd_vel_count_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&cmd_vel_count_publisher, &node));
    }
    if (motor_target_left_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_target_left_publisher, &node));
    }
    if (motor_target_right_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_target_right_publisher, &node));
    }
    if (motor_output_left_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_output_left_publisher, &node));
    }
    if (motor_output_right_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_output_right_publisher, &node));
    }
    if (motor_speed_left_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_speed_left_publisher, &node));
    }
    if (motor_speed_right_publisher.impl != nullptr) {
        RCSOFTCHECK(rcl_publisher_fini(&motor_speed_right_publisher, &node));
    }
    if (twist_subscriber.impl != nullptr) {
        RCSOFTCHECK(rcl_subscription_fini(&twist_subscriber, &node));
    }
    if (pump_cmd_subscriber.impl != nullptr) {
        RCSOFTCHECK(rcl_subscription_fini(&pump_cmd_subscriber, &node));
    }
    if (config_service.impl != nullptr) {
        RCSOFTCHECK(rcl_service_fini(&config_service, &node));
    }
    if (timer.impl != nullptr) {
        RCSOFTCHECK(rcl_timer_fini(&timer));
    }
    if (node.impl != nullptr) {
        RCSOFTCHECK(rcl_node_fini(&node));
    }
    if (support.context.impl != nullptr) {
        rclc_support_fini(&support);
    }

    reset_transport_entities();
    reset_transport_messages();
    safety_stop_motion();
    safety_force_pump_off();
    return true;
}

bool microros_setup_transport_udp_client_()
{
    const String ssid = config.wifi_sta_ssid();
    const String ip = config.microros_uclient_server_ip();
    const String password = config.wifi_sta_pswd();
    const uint32_t agent_port = config.microros_uclient_server_port();

    display.updateWIFISSID(ssid);
    display.updateWIFIPSWD(password);
    display.updateWIFIServerIp(ip + ":" + String(agent_port));

    IPAddress agent_ip;
    agent_ip.fromString(ip);
    if (!set_microros_wifi_transports(
            const_cast<char *>(ssid.c_str()),
            const_cast<char *>(password.c_str()),
            agent_ip,
            agent_port,
            config.board_name())) {
        return false;
    }
    return true;
}

bool microros_setup_transport_serial_(HardwareSerial &serial)
{
    const uint32_t serial_baudrate = config.serial_baudrate();
    serial.updateBaudRate(serial_baudrate);
    return set_microros_serial_transports(serial);
}
