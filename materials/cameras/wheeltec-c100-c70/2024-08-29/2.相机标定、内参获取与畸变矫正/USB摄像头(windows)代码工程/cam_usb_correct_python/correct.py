import cv2
import numpy as np

# 初始化摄像头
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # 设置分辨率
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("无法打开摄像头")
    exit()

# 标定板参数设置
pattern_size = (9, 6)          # 棋盘格内部角点数量
square_size = 25.0             # 棋盘格物理尺寸（毫米）
image_points = []              # 存储图像中的角点
object_points = []             # 存储三维世界坐标

# 标定参数
camera_matrix = None
dist_coeffs = None
rvecs = None
tvecs = None
is_calibrated = False
show_undistorted = False

while True:
    ret, frame = cap.read()
    if not ret:
        print("获取帧失败")
        break

    # 转换为灰度图
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 寻找棋盘格角点
    found, corners = cv2.findChessboardCorners(gray, pattern_size, 
        cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
    
    if found:
        # 亚像素精确化
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
        cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        
        # 绘制角点
        cv2.drawChessboardCorners(frame, pattern_size, corners, found)
    
    # 处理键盘输入
    key = cv2.waitKey(30)
    if key == 27:  # ESC退出
        break
    elif key == ord(' ') and found:  # 空格键保存数据
        # 生成物体坐标系点
        objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * square_size
        
        image_points.append(corners)
        object_points.append(objp)
        print(f"已捕获标定图像：{len(image_points)}")
    elif key == ord('c'):  # 执行标定
        if len(object_points) >= 5:
            frame_size = (frame.shape[1], frame.shape[0])
            ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                object_points, image_points, frame_size, None, None)
            print(f"标定完成！重投影误差：{ret}")
            print("相机矩阵：\n", camera_matrix)
            print("畸变系数：", dist_coeffs.flatten())
            is_calibrated = True
        else:
            print(f"需要至少5张标定图像，当前只有：{len(object_points)}")
    elif key == ord('a'):  # 切换显示模式
        show_undistorted = not show_undistorted

    # 显示结果
    if show_undistorted and is_calibrated:
        undistorted = cv2.undistort(frame, camera_matrix, dist_coeffs)
        cv2.imshow("USB Camera", undistorted)
    else:
        cv2.imshow("USB Camera", frame)

cap.release()
cv2.destroyAllWindows()
