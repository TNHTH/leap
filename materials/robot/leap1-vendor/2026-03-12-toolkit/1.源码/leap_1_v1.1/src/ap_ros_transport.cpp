#include "ap_ros_transport.h"

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
    return true;
}

bool create_transport() {
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
    delay(500);

    allocator = rcl_get_default_allocator();
    init_options = rcl_get_zero_initialized_init_options();
    RCSOFTCHECK(rcl_init_options_init(&init_options, allocator));
    RCSOFTCHECK(rcl_init_options_set_domain_id(&init_options, config.ros2_domain_id()));
    RCSOFTCHECK(rclc_support_init_with_options(&support, 0, NULL, &init_options, &allocator));
    RCSOFTCHECK(rclc_node_init_default(&node, nodename.c_str(), ros2namespace.c_str(), &support));

    // 初始化发布者
    // 初始化发布者
    RCSOFTCHECK(rclc_publisher_init_default(
        &odom_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(nav_msgs, msg, Odometry), 
        odom_topic.c_str()));

    RCSOFTCHECK(rclc_publisher_init_default(
        &imu_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, Imu), 
        "imu"));

    RCSOFTCHECK(rclc_publisher_init_default(
        &battery_publisher, 
        &node, 
        ROSIDL_GET_MSG_TYPE_SUPPORT(sensor_msgs, msg, BatteryState), 
        "battery_state"));

    // 初始化订阅者
    RCSOFTCHECK(rclc_subscription_init_best_effort(&twist_subscriber, &node, ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist), twist_topic.c_str()));

    // 初始化定时器
    RCSOFTCHECK(rclc_timer_init_default(&timer, &support, RCL_MS_TO_NS(timer_timeout), callback_sensor_publisher_timer_));

    // 初始化执行器
    RCSOFTCHECK(rclc_executor_init(&executor, &support.context, 3, &allocator));
    RCSOFTCHECK(rclc_executor_add_subscription(&executor, &twist_subscriber, &twist_msg, &callback_twist_subscription_, ON_NEW_DATA));
    RCSOFTCHECK(rclc_executor_add_timer(&executor, &timer));

    return true;
}

bool destory_transport() {
    rmw_context_t *rmw_context = rcl_context_get_rmw_context(&support.context);
    (void)rmw_uros_set_context_entity_destroy_session_timeout(rmw_context, 0);
    RCSOFTCHECK(rcl_publisher_fini(&odom_publisher, &node));
    RCSOFTCHECK(rcl_publisher_fini(&battery_publisher, &node));
    RCSOFTCHECK(rcl_subscription_fini(&twist_subscriber, &node));
    RCSOFTCHECK(rcl_service_fini(&config_service, &node));
    RCSOFTCHECK(rcl_timer_fini(&timer));
    RCSOFTCHECK(rclc_executor_fini(&executor));
    RCSOFTCHECK(rcl_node_fini(&node));
    rclc_support_fini(&support);
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