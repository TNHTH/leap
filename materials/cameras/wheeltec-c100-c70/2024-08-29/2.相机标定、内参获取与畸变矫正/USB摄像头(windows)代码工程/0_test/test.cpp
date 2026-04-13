#include <opencv2/opencv.hpp>
#include <iostream>

int main() {
    cv::Mat img = cv::imread("C:/code/OpenCV/0_test/test.png"); // 替换为你的图片路径
    if (img.empty()) {
        std::cerr << "Unable to load image" << std::endl;
        return -1;
    }
    cv::imshow("Test Image", img);
    cv::waitKey(0);
    return 0;
}