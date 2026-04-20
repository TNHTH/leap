from __future__ import annotations

from leap1_a20_interfaces.msg import PerceptionDetection


def bbox_area_ratio(msg: PerceptionDetection) -> float:
    return max(0.0, float(msg.bbox_w)) * max(0.0, float(msg.bbox_h))


def is_positive_detection(
    msg: PerceptionDetection,
    hazard_type: str,
    confidence_threshold: float,
    minimum_bbox_area: float,
) -> bool:
    if msg.hazard_type != hazard_type:
        return False
    if not msg.detected:
        return False
    if float(msg.confidence) < confidence_threshold:
        return False
    if bbox_area_ratio(msg) < minimum_bbox_area:
        return False
    return True
