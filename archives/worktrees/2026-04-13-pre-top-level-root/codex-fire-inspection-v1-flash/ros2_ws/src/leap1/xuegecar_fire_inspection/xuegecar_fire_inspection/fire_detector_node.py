import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool


class FireDetectorNode(Node):
    def __init__(self):
        super().__init__('fire_detector_node')
        self.bridge = CvBridge()

        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('fire_detected_topic', '/fire_detected')
        self.declare_parameter('debug_image_topic', '/camera/debug_image')
        self.declare_parameter('hsv_lower', [0, 120, 180])
        self.declare_parameter('hsv_upper', [35, 255, 255])
        self.declare_parameter('min_fire_area', 700.0)
        self.declare_parameter('required_consecutive_detections', 4)
        self.declare_parameter('clear_frames', 6)
        self.declare_parameter('center_weight', 0.25)
        self.declare_parameter('center_region_ratio', 0.5)
        self.declare_parameter('blur_kernel_size', 5)
        self.declare_parameter('morphological_kernel_size', 5)

        image_topic = self.get_parameter('image_topic').value
        self.fire_publisher = self.create_publisher(Bool, self.get_parameter('fire_detected_topic').value, 10)
        self.debug_publisher = self.create_publisher(Image, self.get_parameter('debug_image_topic').value, 10)
        self.create_subscription(Image, image_topic, self._image_callback, 10)

        self._positive_frames = 0
        self._clear_frame_count = 0
        self._fire_state = False

    def _image_callback(self, msg: Image):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        detected, bbox, score = self._detect_fire(frame)

        if detected:
            self._positive_frames += 1
            self._clear_frame_count = 0
        else:
            self._positive_frames = 0
            self._clear_frame_count += 1

        required = int(self.get_parameter('required_consecutive_detections').value)
        clear_frames = int(self.get_parameter('clear_frames').value)

        if self._positive_frames >= required:
            self._fire_state = True
        elif self._clear_frame_count >= clear_frames:
            self._fire_state = False

        self.fire_publisher.publish(Bool(data=self._fire_state))

        debug = frame.copy()
        color = (0, 0, 255) if self._fire_state else (0, 255, 0)
        cv2.putText(debug, f'fire={self._fire_state} score={score:.1f}', (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        if bbox is not None:
            x, y, w, h = bbox
            cv2.rectangle(debug, (x, y), (x + w, y + h), color, 2)
        debug_msg = self.bridge.cv2_to_imgmsg(debug, encoding='bgr8')
        debug_msg.header = msg.header
        self.debug_publisher.publish(debug_msg)

    def _detect_fire(self, frame):
        blur_kernel = int(self.get_parameter('blur_kernel_size').value)
        if blur_kernel % 2 == 0:
            blur_kernel += 1
        morph_kernel = int(self.get_parameter('morphological_kernel_size').value)
        min_fire_area = float(self.get_parameter('min_fire_area').value)
        center_weight = float(self.get_parameter('center_weight').value)
        center_ratio = float(self.get_parameter('center_region_ratio').value)

        blurred = cv2.GaussianBlur(frame, (blur_kernel, blur_kernel), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        lower = np.array(self.get_parameter('hsv_lower').value, dtype=np.uint8)
        upper = np.array(self.get_parameter('hsv_upper').value, dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((morph_kernel, morph_kernel), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return False, None, 0.0

        height, width = frame.shape[:2]
        center_x = width / 2.0
        center_y = height / 2.0
        half_center_w = width * center_ratio / 2.0
        half_center_h = height * center_ratio / 2.0

        best_score = 0.0
        best_bbox = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_fire_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            contour_center_x = x + w / 2.0
            contour_center_y = y + h / 2.0
            in_center = (
                abs(contour_center_x - center_x) <= half_center_w
                and abs(contour_center_y - center_y) <= half_center_h
            )
            score = area * (1.0 + center_weight if in_center else 1.0)
            if score > best_score:
                best_score = score
                best_bbox = (x, y, w, h)

        return best_bbox is not None, best_bbox, best_score


def main(args=None):
    rclpy.init(args=args)
    node = FireDetectorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
