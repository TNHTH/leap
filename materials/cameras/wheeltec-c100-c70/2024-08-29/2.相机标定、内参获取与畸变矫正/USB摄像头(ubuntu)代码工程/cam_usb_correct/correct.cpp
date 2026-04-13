#include <opencv2/opencv.hpp>
#include <vector>
#include <iostream>

int main() {
    cv::VideoCapture cap(0);
    cap.set(cv::CAP_PROP_FRAME_WIDTH, 640);   // 设置分辨率##############################################################
    cap.set(cv::CAP_PROP_FRAME_HEIGHT, 480);
    
    if (!cap.isOpened()) {
        std::cerr << "无法打开摄像头" << std::endl;
        return -1;
    }

    // 标定板参数设置
    const cv::Size patternSize(9, 6);       // 棋盘格内部角点数量##########################################################
    const float squareSize = 25.0f;         // 棋盘格方格物理尺寸（毫米）##################################################
    std::vector<std::vector<cv::Point2f>> imagePoints;
    std::vector<std::vector<cv::Point3f>> objectPoints;

    // 标定参数存储
    cv::Mat cameraMatrix, distCoeffs;
    std::vector<cv::Mat> rvecs, tvecs;
    bool isCalibrated = false;
    bool showUndistorted = false;

    cv::namedWindow("USB Camera", cv::WINDOW_AUTOSIZE);

    while (true) {
        cv::Mat frame;
        cap >> frame;
        if (frame.empty()) {
            std::cerr << "获取帧失败" << std::endl;
            break;
        }

        // 棋盘格检测
        cv::Mat gray;
        cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
        std::vector<cv::Point2f> corners;
        bool found = cv::findChessboardCorners(gray, patternSize, corners,
            cv::CALIB_CB_ADAPTIVE_THRESH + cv::CALIB_CB_NORMALIZE_IMAGE);

        // 如果检测到棋盘格
        if (found) {
            // 亚像素精确化
            cv::cornerSubPix(gray, corners, cv::Size(11, 11), cv::Size(-1, -1),
                cv::TermCriteria(cv::TermCriteria::EPS + cv::TermCriteria::MAX_ITER, 30, 0.1));
            
            // 绘制角点
            cv::drawChessboardCorners(frame, patternSize, corners, found);
        }

        // 处理键盘输入
        int key = cv::waitKey(30);
        if (key == 27) { // ESC 退出
            break;
        }
        else if (key == ' ' && found) { // 空格键保存标定数据
            // 生成物体坐标系点
            std::vector<cv::Point3f> obj;
            for (int i = 0; i < patternSize.height; ++i) {
                for (int j = 0; j < patternSize.width; ++j) {
                    obj.emplace_back(j * squareSize, i * squareSize, 0);
                }
            }

            imagePoints.push_back(corners);
            objectPoints.push_back(obj);
            std::cout << "已捕获标定图像：" << imagePoints.size() << std::endl;
        }
        else if (key == 'c') { // C键执行标定
            if (objectPoints.size() >= 5) {
                double rms = cv::calibrateCamera(objectPoints, imagePoints, frame.size(),
                    cameraMatrix, distCoeffs, rvecs, tvecs);
                std::cout << "标定完成！重投影误差：" << rms << "\n";
                std::cout << "相机矩阵：\n" << cameraMatrix << "\n";
                std::cout << "畸变系数：" << distCoeffs.t() << std::endl;
                isCalibrated = true;

                cv::FileStorage fs("camera_params.yaml", cv::FileStorage::WRITE);
                if (fs.isOpened()) {
                    fs << "camera_matrix" << cameraMatrix;
                    fs << "dist_coeffs" << distCoeffs;
                    fs.release();
                    std::cout << "参数已保存到 camera_params.yaml" << std::endl;
                } else {
                    std::cerr << "无法保存参数文件！" << std::endl;
                }
            }
            else {
                std::cerr << "需要至少5张标定图像，当前只有：" << objectPoints.size() << std::endl;
            }
        }
        else if (key == 'a') { // A键切换显示模式
            showUndistorted = !showUndistorted;
        }

        // 显示结果
        if (showUndistorted && isCalibrated) {
            cv::Mat undistorted;
            cv::undistort(frame, undistorted, cameraMatrix, distCoeffs);
            cv::imshow("USB Camera", undistorted);
        }
        else {
            cv::imshow("USB Camera", frame);
        }
    }

    cap.release();
    cv::destroyAllWindows();
    return 0;
}