"""TFLite tongue segmentation with the same output contract as run_inference."""

import time

import cv2
import numpy as np


_INTERPRETERS = {}


def _load_interpreter(model_path):
    if model_path in _INTERPRETERS:
        return _INTERPRETERS[model_path], 0.0

    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from ai_edge_litert.interpreter import Interpreter
        except ImportError as exc:
            raise ImportError("Install tflite-runtime or ai-edge-litert to run a TFLite model") from exc

    started = time.perf_counter()
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    _INTERPRETERS[model_path] = interpreter
    return interpreter, (time.perf_counter() - started) * 1000.0


def _convert_input(data, details):
    dtype = details["dtype"]
    if np.issubdtype(dtype, np.integer):
        scale, zero_point = details["quantization"]
        if scale <= 0:
            raise ValueError("TFLite input quantization scale must be positive")
        limits = np.iinfo(dtype)
        data = np.clip(np.round(data / scale + zero_point), limits.min, limits.max)
    return data.astype(dtype)


def run_inference(
    image_path,
    model_path,
    img_size=256,
    threshold=0.5,
    image_array=None,
    return_timings=False,
):
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if image_array is not None:
        image_bgr = image_array
    else:
        image_bgr = cv2.imread(str(image_path))
        if image_bgr is None:
            raise FileNotFoundError(f"Cannot load image: {image_path}")

    height, width = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    interpreter, model_load_ms = _load_interpreter(str(model_path))
    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    started = time.perf_counter()
    resized = cv2.resize(image_rgb, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
    normalized = (resized.astype(np.float32) / 255.0 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    normalized = normalized.astype(np.float32)
    shape = tuple(input_details["shape"])
    if shape == (1, 3, img_size, img_size):
        normalized = normalized.transpose(2, 0, 1)
    elif shape != (1, img_size, img_size, 3):
        raise ValueError(f"Unexpected TFLite input shape: {shape}")
    interpreter.set_tensor(input_details["index"], _convert_input(normalized[None], input_details))
    preprocess_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    interpreter.invoke()
    logits = interpreter.get_tensor(output_details["index"])
    if np.issubdtype(output_details["dtype"], np.integer):
        scale, zero_point = output_details["quantization"]
        if scale <= 0:
            raise ValueError("TFLite output quantization scale must be positive")
        logits = scale * (logits.astype(np.float32) - zero_point)
    logits = np.squeeze(logits)
    if logits.shape != (img_size, img_size):
        raise ValueError(f"Unexpected TFLite output shape: {logits.shape}")
    mask_small = (logits > np.log(threshold / (1.0 - threshold))).astype(np.uint8) * 255
    forward_ms = (time.perf_counter() - started) * 1000.0

    mask = cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_NEAREST)
    tongue_only = image_rgb.copy()
    tongue_only[mask == 0] = 0
    if return_timings:
        return mask, tongue_only, {
            "model_load_ms": model_load_ms,
            "seg_preprocess_ms": preprocess_ms,
            "seg_forward_ms": forward_ms,
        }
    return mask, tongue_only