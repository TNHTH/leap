import threading
from http import server
from socketserver import ThreadingMixIn
from typing import Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


class _StreamHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        node = self.server.node  # type: ignore[attr-defined]
        if self.path not in ('/', node.stream_path):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Age', '0')
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()
        try:
            while rclpy.ok():
                frame = node.wait_for_frame()
                if frame is None:
                    continue
                self.wfile.write(b'--frame\r\n')
                self.wfile.write(b'Content-Type: image/jpeg\r\n')
                self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format, *args):
        return


class _ThreadedHTTPServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.bridge = CvBridge()
        self.declare_parameter('camera_device', 0)
        self.declare_parameter('frame_width', 640)
        self.declare_parameter('frame_height', 480)
        self.declare_parameter('fps', 15.0)
        self.declare_parameter('frame_id', 'camera_link')
        self.declare_parameter('mjpeg_host', '0.0.0.0')
        self.declare_parameter('mjpeg_port', 8090)
        self.declare_parameter('jpeg_quality', 85)
        self.declare_parameter('stream_path', '/stream')
        self.declare_parameter('image_topic', '/camera/image_raw')

        self.stream_path = self.get_parameter('stream_path').value
        image_topic = self.get_parameter('image_topic').value
        self.publisher = self.create_publisher(Image, image_topic, 10)
        self._frame_id = self.get_parameter('frame_id').value
        self._jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(self.get_parameter('jpeg_quality').value)]
        self._latest_frame: Optional[bytes] = None
        self._frame_condition = threading.Condition()

        device = self.get_parameter('camera_device').value
        self.capture = cv2.VideoCapture(device)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.get_parameter('frame_width').value))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.get_parameter('frame_height').value))
        self.capture.set(cv2.CAP_PROP_FPS, float(self.get_parameter('fps').value))
        if not self.capture.isOpened():
            raise RuntimeError(f'Failed to open camera device: {device}')

        fps = max(float(self.get_parameter('fps').value), 1.0)
        self.timer = self.create_timer(1.0 / fps, self._capture_once)

        self.http_server = _ThreadedHTTPServer(
            (self.get_parameter('mjpeg_host').value, int(self.get_parameter('mjpeg_port').value)),
            _StreamHandler,
        )
        self.http_server.node = self  # type: ignore[attr-defined]
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()

    def _capture_once(self):
        ok, frame = self.capture.read()
        if not ok:
            self.get_logger().warning('Camera frame grab failed.')
            return
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        self.publisher.publish(msg)

        encoded, jpeg = cv2.imencode('.jpg', frame, self._jpeg_params)
        if encoded:
            with self._frame_condition:
                self._latest_frame = jpeg.tobytes()
                self._frame_condition.notify_all()

    def wait_for_frame(self) -> Optional[bytes]:
        with self._frame_condition:
            if self._latest_frame is None:
                self._frame_condition.wait(timeout=1.0)
            return self._latest_frame

    def destroy_node(self):
        if hasattr(self, 'http_server'):
            self.http_server.shutdown()
            self.http_server.server_close()
        if hasattr(self, 'capture'):
            self.capture.release()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
