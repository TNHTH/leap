1.该例程要求opencv版本要在3.2以上，使用python3运行，运行指令
python3 camera.py
2.例程默认打开设备号为0的摄像头，可以设置参数i指定打开摄像头的设备号
指定方法为：
python3 camera.py -i (设备号)
或者
python3 camera.py --id (设备号)
3.如何获取摄像头设备号：先在不插入摄像头的时候输入指令ls /dev/video*,再在接入摄像头时输入相同指令，对比两次指令结果，找到多出来的两个”/dev/video(设备号)“，选取这两个中设备号较小的设备。例如，多出来的两个设备是”/dev/video0“，”/dev/video0“则使用
python3 camera.py -i 0
打开摄像头。