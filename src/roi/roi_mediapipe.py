import cv2
import mediapipe as mp
import numpy as np
from functools import lru_cache
from pathlib import Path
import tempfile
from urllib.request import urlretrieve

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# Face Mesh lip landmarks used to localize tongue/mouth ROI.
LIP_LANDMARKS = [
    61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
    78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308,
]

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


def _resolve_model_path():
    # Prefer ASCII-safe temp path first to avoid Unicode path issues on Windows.
    temp_model = Path(tempfile.gettempdir()) / "edge_deid_face_landmarker.task"

    if temp_model.exists():
        return temp_model

    # Fallback: check project locations.
    repo_root_model = Path(__file__).resolve().parents[2] / "face_landmarker.task"
    local_model = Path(__file__).resolve().parent / "face_landmarker.task"

    if repo_root_model.exists():
        try:
            temp_model.write_bytes(repo_root_model.read_bytes())
            return temp_model
        except Exception:
            return repo_root_model
    if local_model.exists():
        try:
            temp_model.write_bytes(local_model.read_bytes())
            return temp_model
        except Exception:
            return local_model

    # Auto-download once for first-time setup in VM.
    try:
        urlretrieve(MODEL_URL, temp_model)
        return temp_model
    except Exception as exc:
        raise RuntimeError(f"failed to download face_landmarker.task: {exc}") from exc


@lru_cache(maxsize=1)
def _get_face_landmarker():
    # Cache detector so batch processing avoids repeated initialization overhead.
    model_path = _resolve_model_path()
    base_options = python.BaseOptions(model_asset_path=str(model_path))
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        running_mode=vision.RunningMode.IMAGE,
    )
    return vision.FaceLandmarker.create_from_options(options)


def extract_roi_mediapipe(image):
    """Extract mouth ROI from a BGR image using MediaPipe Face Landmarker.

    Returns:
        tuple: (roi_img, roi_bbox, status, error)
            roi_img: np.ndarray ROI image (BGR) or None on failure
            roi_bbox: [x1, y1, x2, y2] or [] on failure
            status: "ok" or "error"
            error: empty string on success, reason string on failure
    """
    try:
        if image is None or not isinstance(image, np.ndarray):
            return None, [], "error", "invalid image input"
        if image.ndim != 3 or image.shape[2] != 3:
            return None, [], "error", "image must be HxWx3 BGR"

        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return None, [], "error", "empty image shape"

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = _get_face_landmarker().detect(mp_image)

        if not result.face_landmarks:
            return None, [], "error", "no_face_landmarks"

        landmarks = result.face_landmarks[0]

        xs = []
        ys = []
        for idx in LIP_LANDMARKS:
            lm = landmarks[idx]
            xs.append(lm.x * w)
            ys.append(lm.y * h)

        x_min = max(0, int(min(xs)))
        y_min = max(0, int(min(ys)))
        x_max = min(w, int(max(xs)))
        y_max = min(h, int(max(ys)))

        # Add margin to make ROI less sensitive to landmark jitter.
        # Top: small padding above lips.
        # Bottom: extend 3× the lip-landmark height below y_max so a
        # protruding tongue is captured without including chin / neck / clothing.
        lip_h = y_max - y_min
        pad_x = int((x_max - x_min) * 0.15)
        pad_y_top = int(lip_h * 0.20)
        pad_y_bot = int(lip_h * 3.0)

        x1 = max(0, x_min - pad_x)
        y1 = max(0, y_min - pad_y_top)
        x2 = min(w, x_max + pad_x)
        y2 = min(h, y_max + pad_y_bot)

        if x2 <= x1 or y2 <= y1:
            return None, [], "error", "invalid roi bbox"

        roi_img = image[y1:y2, x1:x2].copy()
        if roi_img.size == 0:
            return None, [], "error", "empty roi image"

        return roi_img, [x1, y1, x2, y2], "ok", ""

    except Exception as exc:
        return None, [], "error", f"mediapipe_exception: {exc}"
