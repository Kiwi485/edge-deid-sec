import cv2
import numpy as np


def check_quality(
    image,
    min_width=320,
    min_height=240,
    blur_var_threshold=10.0,
    brightness_low=45.0,
    brightness_high=210.0,
):
    """Run quality gate checks and return pass/fail with reason.

    Checks:
    1. Minimum resolution
    2. Blur (Laplacian variance)
    3. Brightness range
    """
    result = {
        "pass": False,
        "reason": "invalid_image",
        "metrics": {},
    }

    if image is None or not isinstance(image, np.ndarray):
        return result
    if image.ndim != 3 or image.shape[2] != 3:
        result["reason"] = "invalid_image_shape"
        return result

    h, w = image.shape[:2]
    if h < min_height or w < min_width:
        result["reason"] = "low_resolution"
        result["metrics"] = {
            "width": int(w),
            "height": int(h),
            "min_width": int(min_width),
            "min_height": int(min_height),
        }
        return result

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())

    result["metrics"] = {
        "width": int(w),
        "height": int(h),
        "laplacian_variance": lap_var,
        "brightness_mean": brightness,
        "blur_var_threshold": float(blur_var_threshold),
        "brightness_low": float(brightness_low),
        "brightness_high": float(brightness_high),
    }

    reasons = []
    if lap_var < blur_var_threshold:
        reasons.append("blur")
    if brightness < brightness_low:
        reasons.append("too_dark")
    elif brightness > brightness_high:
        reasons.append("too_bright")

    if reasons:
        result["reason"] = ",".join(reasons)
        return result

    result["pass"] = True
    result["reason"] = "ok"
    return result
