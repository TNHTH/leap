#include "ap_ros_transport.h"
#include <rosidl_runtime_c/string_functions.h>

// 所有全局变量在此初始化（仅一次）
// MicroROS消息初始化
geometry_msgs__msg__Twist twist_msg = {};
nav_msgs__msg__Odometry odom_msg = {};
sensor_msgs__msg__Imu imu_msg = {};
sensor_msgs__msg__BatteryState battery_msg= {};
micro_ros_utilities_memory_conf_t conf = {0};

// MicroROS订阅发布者服务初始化
rcl_publisher_t odom_publisher = {};
rcl_publisher_t imu_publisher = {};
rcl_subscription_t twist_subscriber = {};
rcl_service_t config_service = {};
rcl_wait_set_t wait_set = {};
rcl_publisher_t battery_publisher = {};

// MicroROS执行器&节点初始化
// rclc_executor_t executor = {};
rcl_init_options_t init_options = {};
rclc_support_t support = {};
rcl_allocator_t allocator = {};
rcl_node_t node = {};
rcl_timer_t timer = {};

namespace
{
bool transport_entities_created = false;

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
}

void reset_transport_entities()
{
    odom_publisher = rcl_get_zero_initialized_publisher();
    imu_publisher = rcl_get_zero_initialized_publisher();
    battery_publisher = rcl_get_zero_initialized_publisher();
    twist_subscriber = rcl_get_zero_initialized_subscription();
    config_service = rcl_get_zero_initialized_service();
    wait_set = rcl_get_zero_initialized_wait_set();
    init_options = rcl_get_zero_initialized_init_options();
    memset(&support, 0, sizeof(support));
    allocator = rcl_get_default_allocator();
    node = rcl_get_zero_initialized_node();
    timer = rcl_get_zero_initialized_timer();
    memset(&executor, 0, sizeof(executor));
    transport_entities_created = false;
}

bool prepare_transport_messages(const String &odom_frameid_str, const String &odom_child_frameid_str)
{
    reset_transport_messages();
    odom_msg.header.frame_id = micro_ros_string_utilities_set(odom_msg.header.frame_id, odom_frameid_str.c_str());
    odom_msg.child_frame_id = micro_ros_string_utilities_set(odom_msg.child_frame_id, odom_child_frameid_str.c_str());
    imu_msg.header.frame_id = micro_ros_string_utilities_set(imu_msg.header.frame_id, "imu");
    if (odom_msg.header.frame_id.data == nullptr || odom_msg.child_frame_id.data == nullptr || imu_msg.header.frame_id.data == nullptr) {
        log_debug("ros2", "failed to allocate frame id strings");
        reset_transport_messages();
        return false;
    }
    return true;
}

bool transport_requires_wifi()
{
    return config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT;
}
} // namespace

void callback_sensor_publisher_timer_(rcl_timer_t *timer, int64_t last_call_time) {
    RCLC_UNUSED(last_call_time);
    if (timer != NULL) {
        int64_t stamp = rmw_uros_epoch_millis();
        odom_t odom = kinematics.odom();

        // 填充里程计消息
        odom_msg.header.stamp.sec = static_cast<int32_t>(stamp / 1000);
        odom_msg.header.stamp.nanosec = static_cast<uint32_t>((stamp % 1000) * 1e6);
        odom_msg.pose.pose.position.x = odom.x;
        odom_msg.pose.pose.position.y = odom.y;
        odom_msg.pose.pose.orientation.w = odom.quaternion.w;
        odom_msg.pose.pose.orientation.x = odom.quaternion.x;
        odom_msg.pose.pose.orientation.y = odom.quaternion.y;
        odom_msg.pose.pose.orientation.z = odom.quaternion.z;
        odom_msg.twist.twist.angular.z = odom.angular_speed;
        odom_msg.twist.twist.linear.x = odom.linear_speed;

        // 更新显示
        display.updateBotAngular(odom.angular_speed);
        display.updateBotLinear(odom.linear_speed);

        // 发布里程计消息
        RCSOFTCHECK(rcl_publish(&odom_publisher, &odom_msg, NULL));

        // 发布IMU消息
        if (imu.isEnable()) {
            imu.getImuDriverData(imu_data);
            imu_msg.header.stamp.sec = static_cast<int32_t>(stamp / 1000);
            imu_msg.header.stamp.nanosec = static_cast<uint32_t>((stamp % 1000) * 1e6);
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

            RCSOFTCHECK(rcl_publish(&imu_publisher, &imu_msg, NULL));
        }

        battery.update();
        battery_msg.voltage = battery.voltage();  // 单位: V
        battery_msg.current = NAN;                // 可选，不测可填 NAN
        battery_msg.percentage = NAN;             // 若无 SOC 算法可暂时空
        battery_msg.power_supply_status = sensor_msgs__msg__BatteryState__POWER_SUPPLY_STATUS_DISCHARGING;
        battery_msg.present = true;

        RCSOFTCHECK(rcl_publish(&battery_publisher, &battery_msg, NULL));
    }
}

void callback_twist_subscription_(const void *msgin) {
    const geometry_msgs__msg__Twist *msg = (const geometry_msgs__msg__Twist *)msgin;
    static float target_motor_speed1, target_motor_speed2;
    // 运动学逆解计算电机目标速度
    kinematics.kinematic_inverse(msg->linear.x * 1000, msg->angular.z, target_motor_speed1, target_motor_speed2);
    pid_controller[0].update_target(target_motor_speed1);
    pid_controller[1].update_target(target_motor_speed2);
}

bool setup_transport() {
    bool setup_success = true;
    if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_WIFI_UDP_CLIENT) {
        log_set_target(Serial);
        WiFi.onEvent(WiFiEventCB);
        setup_success = microros_setup_transport_udp_client_();
        display.updateTransMode("udp_client");
    }
    if (config.microros_transport_mode() == CONFIG_TRANSPORT_MODE_SERIAL) {
        SerialBT.begin(config.board_name());
        log_set_target(SerialBT);
        if (config.microros_serial_id() == 2) {
            microros_setup_transport_serial_(Serial2);
            display.updateTransMode("serial2");
        } else {
            microros_setup_transport_serial_(Serial);
            display.updateTransMode("serial");
        }
    }
    return setup_success;
}

bool create_transport() {
    String nodename = config.ros2_nodename();
    String ros2namespace = config.ros2_namespace();
    String twist_topic = config.ros2_twist_topic_name();
    String odom_topic = config.ros2_odom_topic_name();
    String odom_frameid_str = config.ros2_odom_frameid();
    String odom_child_frameid_str = config.ros2_odom_child_frameid();
    const unsigned int timer_timeout = config.odom_publish_period();

    reset_transport_entities();
    if (!prepare_transport_messages(odom_frameid_str, odom_child_frameid_str)) {
        return false;
    }
    delay(500);

    if (!check_rcl_ok("rcl_init_options_init", rcl_init_options_init(&init_options, allocator))) goto fail;
    if (!check_rcl_ok("rcl_init_options_set_domain_id", rcl_init_options_set_domain_id(&init_options, config.ros2_domain_id()))) goto fail;
    if (!check_rcl_ok("rclc_support_init_with_options", rclc_support_init_with_options(&support, 0, NULL, &init_options, &allocator))) goto fail;
    if (!check_rcl_ok("rclc_node_init_default", rclc_node_init_default(&node, nodename.c_str(), ros2namespace.c_str(), &support))) goto fail;

    if (!check_rcl_ok("rclc_publisher_init_default(odom)", rclc_publisher_init_default(
        &odom_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), 
        odom_topic.c_str()))) goto fail;

    if (!check_rcl_ok("rclc_publisher_init_default(imu)", rclc_publisher_init_default(
        &imu_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu), 
        "imu"))) goto fail;

    if (!check_rcl_ok("rclc_publisher_init_default(battery)", rclc_publisher_init_default(
        &battery_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState), 
        "battery_state"))) goto fail;

    if (!check_rcl_ok("rclc_subscription_init_best_effort", rclc_subscription_init_best_effort(&twist_subscriber, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist), twist_topic.c_str()))) goto fail;

    if (!check_rcl_ok("rclc_timer_init_default", rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(timer_timeout), callback_sensor_publisher_timer_))) goto fail;

    if (!check_rcl_ok("rclc_executor_init", rclc_executor_init(&executor, &support.context, 2, &allocator))) goto fail;
    if (!check_rcl_ok("rclc_executor_add_subscription", rclc_executor_add_subscription(&executor, &twist_subscriber, &twist_msg, &callback_twist_subscription_, ON_NEW_DATA))) goto fail;
    if (!check_rcl_ok("rclc_executor_add_timer", rclc_executor_add_timer(&executor, &timer))) goto fail;

    transport_entities_created = true;
    return true;

fail:
    destory_transport();
    return false;
}

bool destory_transport() {
    if (support.context.impl != NULL) {
        rmw_context_t *rmw_context = rcl_context_get_rmw_context(&support.context);
        (void)rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);
    }
    if (odom_publisher.impl != NULL) {
        RCSOFTCHECK(rcl_publisher_fini(&odom_publisher, &node));
    }
    if (imu_publisher.impl != NULL) {
        RCSOFTCHECK(rcl_publisher_fini(&imu_publisher, &node));
    }
    if (battery_publisher.impl != NULL) {
        RCSOFTCHECK(rcl_publisher_fini(&battery_publisher, &node));
    }
    if (twist_subscriber.impl != NULL) {
        RCSOFTCHECK(rcl_subscription_fini(&twist_subscriber, &node));
    }
    if (config_service.impl != NULL) {
        RCSOFTCHECK(rcl_service_fini(&config_service, &node));
    }
    if (timer.impl != NULL) {
        RCSOFTCHECK(rcl_timer_fini(&timer));
    }
    if (node.impl != NULL) {
        RCSOFTCHECK(rcl_node_fini(&node));
    }
    if (support.context.impl != NULL) {
        rclc_support_fini(&support);
    }
    reset_transport_entities();
    reset_transport_messages();
    return true;
}

bool microros_setup_transport_udp_client_() {
    String ssid = config.wifi_sta_ssid();
    String ip = config.microros_uclient_server_ip();
    String password = config.wifi_sta_pswd();
    uint32_t agent_port = config.microros_uclient_server_port();

    display.updateWIFISSID(ssid);
    display.updateWIFIPSWD(password);
    display.updateWIFIServerIp(ip + ":" + String(agent_port));

    IPAddress agent_ip;
    agent_ip.fromString(ip);
    if (!set_microros_wifi_transports((char *)ssid.c_str(), (char *)password.c_str(), agent_ip, agent_port, config.board_name())) {
        return false;
    }
    return true;
}

bool microros_setup_transport_serial_(HardwareSerial& serial) {
    String nodename = config.ros2_nodename();
    String ros2namespace = config.ros2_namespace();
    String twist_topic = config.ros2_twist_topic_name();
    String odom_topic = config.ros2_odom_topic_name();
    String odom_frameid_str = config.ros2_odom_frameid();
    String odom_child_frameid_str = config.ros2_odom_child_frameid();

    odom_msg.header.frame_id = micro_ros_string_utilities_set(odom_msg.header.frame_id, odom_frameid_str.c_str());
    odom_msg.child_frame_id = micro_ros_string_utilities_set(odom_msg.child_frame_id, odom_child_frameid_str.c_str());
    imu_msg.header.frame_id = micro_ros_string_utilities_set(imu_msg.header.frame_id, "imu");
    const unsigned int timer_timeout = config.odom_publish_period();

    uint32_t serial_baudraate = config.serial_baudrate();
    serial.updateBaudRate(serial_baudraate);
    if (!set_microros_serial_transports(serial)) {
        return false;
    }
    return true;
}
