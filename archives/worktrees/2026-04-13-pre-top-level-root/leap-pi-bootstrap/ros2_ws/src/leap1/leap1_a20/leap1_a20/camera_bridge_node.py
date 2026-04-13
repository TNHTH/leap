from __future__ import annotations

import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

from .common import CAMERA_STATUS_TOPIC, json_dumps, utc_now_text


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class CameraBridgeNode(Node):
    """将 UVC 摄像头桥接成 ROS 图像话题和 MJPEG 预览流。"""

    def __init__(
        self,
        node_name: str,
        default_camera_name: str,
        default_device: str,
        default_frame_id: str,
        default_mjpeg_port: int,
    ) -> None:
        super().__init__(node_name)
        self.declare_parameter("camera_name", default_camera_name)
        self.declare_parameter("device", default_device)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", 15.0)
        self.declare_parameter("frame_id", default_frame_id)
        self.declare_parameter("mjpeg_port", default_mjpeg_port)
        self.declare_parameter("mjpeg_host", "0.0.0.0")

        self.camera_name = self.get_parameter("camera_name").value
        self.device = str(self.get_parameter("device").value)
        self.width = int(self.get_parameter("width").value)
        self.height = int(self.get_parameter("height").value)
        self.fps = float(self.get_parameter("fps").value)
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.mjpeg_port = int(self.get_parameter("mjpeg_port").value)
        self.mjpeg_host = str(self.get_parameter("mjpeg_host").value)

        self.image_pub = self.create_publisher(Image, f"/a20/{self.camera_name}/image_raw", 10)
        self.status_pub = self.create_publisher(String, CAMERA_STATUS_TOPIC, 10)

        self._lock = threading.Lock()
        self._latest_jpeg: bytes = b""
        self._latest_frame: Optional[tuple[int, int, bytes]] = None
        self._latest_stamp = 0.0
        self._online = False
        self._stop_event = threading.Event()
        self._http_server: Optional[_ReusableThreadingHTTPServer] = None

        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        self._start_http_server()
        self.create_timer(1.0, self._publish_status)

    def destroy_node(self) -> bool:
        self._stop_event.set()
        if self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
        return super().destroy_node()

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if not self.device:
            self.get_logger().warning(f"{self.camera_name} 未配置设备路径，将保持离线占位。")
            return None
        capture = cv2.VideoCapture(self.device)
        if not capture.isOpened():
            self.get_logger().error(f"{self.camera_name} 无法打开摄像头设备: {self.device}")
            capture.release()
            return None
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_FPS, self.fps)
        return capture

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            capture = self._open_capture()
            if capture is None:
                self._set_offline()
                time.sleep(2.0)
                continue

            self.get_logger().info(f"{self.camera_name} 已打开设备 {self.device}，开始采集。")
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    self.get_logger().warning(f"{self.camera_name} 读取帧失败，准备重连。")
                    self._set_offline()
                    break

                frame = cv2.resize(frame, (self.width, self.height))
                success, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not success:
                    continue

                stamp = self.get_clock().now().to_msg()
                image_msg = Image()
                image_msg.header.stamp = stamp
                image_msg.header.frame_id = self.frame_id
                image_msg.height = frame.shape[0]
                image_msg.width = frame.shape[1]
                image_msg.encoding = "bgr8"
                image_msg.is_bigendian = False
                image_msg.step = frame.shape[1] * 3
                image_msg.data = frame.tobytes()
                if self._stop_event.is_set() or not rclpy.ok():
                    break
                try:
                    self.image_pub.publish(image_msg)
                except Exception as exc:  # noqa: BLE001
                    self.get_logger().warning(f"{self.camera_name} 发布图像失败，准备退出采集循环: {exc}")
                    self._set_offline()
                    break

                with self._lock:
                    self._latest_jpeg = encoded.tobytes()
                    self._latest_frame = (frame.shape[1], frame.shape[0], image_msg.data)
                    self._latest_stamp = time.time()
                    self._online = True

                time.sleep(max(0.0, 1.0 / max(self.fps, 1.0)))

            capture.release()
            time.sleep(1.0)

    def _set_offline(self) -> None:
        with self._lock:
            self._online = False
            self._latest_jpeg = b""
            self._latest_frame = None

    def _publish_status(self) -> None:
        status = String()
        with self._lock:
            status.data = json_dumps(
                {
                    "camera_name": self.camera_name,
                    "device": self.device,
                    "online": self._online,
                    "frame_id": self.frame_id,
                    "mjpeg_port": self.mjpeg_port,
                    "stream_url": f"http://127.0.0.1:{self.mjpeg_port}/stream",
                    "snapshot_url": f"http://127.0.0.1:{self.mjpeg_port}/snapshot.jpg",
                    "updated_at": utc_now_text(),
                }
            )
        self.status_pub.publish(status)

    def _start_http_server(self) -> None:
        node = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/status":
                    self._send_json()
                    return
                if parsed.path == "/snapshot.jpg":
                    self._send_snapshot()
                    return
                if parsed.path == "/stream":
                    self._send_stream()
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "unknown path")

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                node.get_logger().debug(f"{self.address_string()} - {format % args}")

            def _send_json(self) -> None:
                with node._lock:
                    payload = json_dumps(
                        {
                            "camera_name": node.camera_name,
                            "online": node._online,
                            "device": node.device,
                            "mjpeg_port": node.mjpeg_port,
                            "updated_at": utc_now_text(),
                        }
                    ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _send_snapshot(self) -> None:
                with node._lock:
                    frame = node._latest_jpeg
                if not frame:
                    self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "camera offline")
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)

            def _send_stream(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                while not node._stop_event.is_set():
                    with node._lock:
                        frame = node._latest_jpeg
                    if not frame:
                        time.sleep(0.2)
                        continue
                    try:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        time.sleep(max(0.0, 1.0 / max(node.fps, 1.0)))
                    except BrokenPipeError:
                        break
                    except ConnectionResetError:
                        break

        self._http_server = _ReusableThreadingHTTPServer((self.mjpeg_host, self.mjpeg_port), Handler)
        thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
        thread.start()
        self.get_logger().info(
            f"{self.camera_name} MJPEG 服务已启动: http://127.0.0.1:{self.mjpeg_port}/stream"
        )


def run_camera_bridge(
    node_name: str,
    default_camera_name: str,
    default_device: str,
    default_frame_id: str,
    default_mjpeg_port: int,
) -> None:
    rclpy.init()
    node = CameraBridgeNode(
        node_name=node_name,
        default_camera_name=default_camera_name,
        default_device=default_device,
        default_frame_id=default_frame_id,
        default_mjpeg_port=default_mjpeg_port,
    )
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main() -> None:
    run_camera_bridge(
        node_name="camera_bridge_node",
        default_camera_name="vehicle_camera",
        default_device="/dev/video0",
        default_frame_id="camera_link",
        default_mjpeg_port=8091,
    )
