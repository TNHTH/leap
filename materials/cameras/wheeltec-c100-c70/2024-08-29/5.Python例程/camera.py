# -*- coding: utf-8 -*-

import cv2
import argparse

def catch_video(name='my_video', video_index=0):
    # cv2.namedWindow(name)
    cap = cv2.VideoCapture(video_index) # 创建摄像头识别类
    if not cap.isOpened():

        raise Exception('Check if the camera is on.')
    else:
         print("Press \"q\" to quit\n")
    while cap.isOpened():
        catch, frame = cap.read() # 读取每一帧图片
        cv2.imshow(name, frame) # 在window上显示图片
        key = cv2.waitKey(10)
        if key & 0xFF == ord('q'):
    # 按q退出
            break
    # 释放摄像头
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
        parser = argparse.ArgumentParser()
        parser.add_argument('-i','--id' ,type = int ,default = 0)
        args = parser.parse_args()
        sensor_id = args.id
        catch_video(video_index = sensor_id)
        # catch_video()
        
