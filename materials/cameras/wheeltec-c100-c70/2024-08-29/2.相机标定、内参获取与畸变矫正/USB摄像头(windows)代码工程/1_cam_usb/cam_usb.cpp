#include <opencv2/opencv.hpp>
#include <iostream>

int main() {
    // 打开默认的摄像头（通常是第一个摄像头，索引为0）
    cv::VideoCapture cap(0);

    // 检查摄像头是否成功打开
    if (!cap.isOpened()) {
        std::cerr << "Error: Unable to open the camera!" << std::endl;
        return -1;
    }

    // 创建一个窗口来显示摄像头的视频流
    cv::namedWindow("USB Camera", cv::WINDOW_NORMAL);

    cv::Mat frame;
    while (true) {
        // 从摄像头读取一帧
        cap >> frame;

        // 检查是否成功读取帧
        if (frame.empty()) {
            std::cerr << "Error: Unable to read frame from camera!" << std::endl;
            break;
        }

        // 显示帧
        cv::imshow("USB Camera", frame);

        // 按下 'q' 键退出循环
        if (cv::waitKey(1) == 'q') {
            break;
        }
    }

    // 释放摄像头资源并关闭窗口
    cap.release();
    cv::destroyAllWindows();

    return 0;
}