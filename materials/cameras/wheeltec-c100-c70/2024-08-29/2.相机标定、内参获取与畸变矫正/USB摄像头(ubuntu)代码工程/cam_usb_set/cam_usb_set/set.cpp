/*//////////////////////////
通过libv4l2开发库调整相机参数
数字1-5切换不同的参数，↑↓键调参
//////////////////////////*/
#include <opencv2/opencv.hpp>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <iostream>
#include <string>
#include <map>
#include <algorithm>  // 添加algorithm头文件

struct CameraControl {
    int id;
    std::string name;
    int min;
    int max;
    int current;
};

std::map<int, CameraControl> controls = {
    {V4L2_CID_BRIGHTNESS,     {V4L2_CID_BRIGHTNESS,     "Brightness",    -64, 64, 0}},
    {V4L2_CID_CONTRAST,       {V4L2_CID_CONTRAST,       "Contrast",      0, 100, 90}},
    {V4L2_CID_SATURATION,     {V4L2_CID_SATURATION,     "Saturation",    0, 100, 80}},
    {V4L2_CID_SHARPNESS,      {V4L2_CID_SHARPNESS,      "Sharpness",     0, 100, 0}},
    {V4L2_CID_GAMMA,          {V4L2_CID_GAMMA,          "Gamma",       100, 500, 40}}
};

bool set_v4l2_control(const char* device, int ctrl_id, int value) {
    int fd = open(device, O_RDWR);
    if (fd < 0) {
        std::cerr << "打开设备失败: " << strerror(errno) << std::endl;
        return false;
    }

    v4l2_queryctrl query_ctrl{};
    query_ctrl.id = ctrl_id;
    if (ioctl(fd, VIDIOC_QUERYCTRL, &query_ctrl) < 0) {
        std::cerr << "控制项 " << ctrl_id << " 不支持: " << strerror(errno) << std::endl;
        close(fd);
        return false;
    }

    // 兼容性修改：使用std::min和std::max替代std::clamp
    value = std::max((int)query_ctrl.minimum, std::min(value, (int)query_ctrl.maximum));

    v4l2_control ctrl{};
    ctrl.id = ctrl_id;
    ctrl.value = value;
    if (ioctl(fd, VIDIOC_S_CTRL, &ctrl) < 0) {
        std::cerr << "设置失败: " << strerror(errno) << std::endl;
        close(fd);
        return false;
    }

    close(fd);
    controls[ctrl_id].current = value;
    std::cout << controls[ctrl_id].name << " 设置为: " << value << std::endl;
    return true;
}

int main() {
    const char* device = "/dev/video0";
    
    // 兼容性修改：使用普通迭代器替代结构化绑定
    for (auto& control_pair : controls) {
        int id = control_pair.first;
        CameraControl& ctrl = control_pair.second;
        if (!set_v4l2_control(device, id, ctrl.current)) {
            std::cerr << "初始化 " << ctrl.name << " 失败" << std::endl;
        }
    }

    cv::VideoCapture cap(0);
    if (!cap.isOpened()) {
        std::cerr << "无法打开摄像头" << std::endl;
        return -1;
    }

    cv::namedWindow("USB Camera", cv::WINDOW_AUTOSIZE);
    int current_control = V4L2_CID_CONTRAST;
    cv::Mat frame;

    while (true) {
        cap >> frame;
        if (frame.empty()) break;

        std::string info = controls[current_control].name + ": " + 
                          std::to_string(controls[current_control].current);
        cv::putText(frame, info, cv::Point(20, 40), 
                    cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar(0, 255, 0), 2);

        cv::imshow("USB Camera", frame);

        int key = cv::waitKey(30);
        if (key == 27) break;

        switch (key) {
            case '1': current_control = V4L2_CID_BRIGHTNESS; break;
            case '2': current_control = V4L2_CID_CONTRAST; break;
            case '3': current_control = V4L2_CID_SATURATION; break;
            case '4': current_control = V4L2_CID_SHARPNESS; break;
            case '5': current_control = V4L2_CID_GAMMA; break;
        }

        if (key == 82) {  // 上箭头
            int new_val = controls[current_control].current + 5;
            set_v4l2_control(device, current_control, new_val);
        } else if (key == 84) {  // 下箭头
            int new_val = controls[current_control].current - 5;
            set_v4l2_control(device, current_control, new_val);
        }
    }

    cap.release();
    cv::destroyAllWindows();
    return 0;
}