import numpy as np
import pytest

from src.seg import tflite_inference


class FakeInterpreter:
    def __init__(self, shape, logits, quantized=False):
        self.shape = shape
        self.logits = logits
        self.quantized = quantized
        self.input = None

    def get_input_details(self):
        return [{
            "index": 0,
            "shape": np.array(self.shape),
            "dtype": np.int8 if self.quantized else np.float32,
            "quantization": (0.1, 0),
        }]

    def get_output_details(self):
        return [{
            "index": 1,
            "dtype": np.int8 if self.quantized else np.float32,
            "quantization": (0.1, 0),
        }]

    def set_tensor(self, index, data):
        self.input = data

    def invoke(self):
        pass

    def get_tensor(self, index):
        return self.logits


@pytest.mark.parametrize("layout", ["nchw", "nhwc"])
def test_tflite_mask_and_normalization(monkeypatch, layout):
    size = 4
    shape = (1, 3, size, size) if layout == "nchw" else (1, size, size, 3)
    logits = np.full((1, 1, size, size), -2.0, dtype=np.float32)
    logits[:, :, :2, :] = 2.0
    interpreter = FakeInterpreter(shape, logits)
    monkeypatch.setattr(tflite_inference, "_load_interpreter", lambda _: (interpreter, 1.0))
    image = np.full((8, 6, 3), 255, dtype=np.uint8)

    mask, tongue, timings = tflite_inference.run_inference(
        "", "model.tflite", img_size=size, image_array=image, return_timings=True
    )

    assert interpreter.input.dtype == np.float32
    assert interpreter.input.shape == shape
    expected_red = (1.0 - 0.485) / 0.229
    assert interpreter.input.flat[0] == pytest.approx(expected_red)
    assert mask.shape == (8, 6)
    assert np.all(mask[:4] == 255) and np.all(mask[4:] == 0)
    assert np.all(tongue[4:] == 0) and np.all(tongue[:4] == 255)
    assert timings["model_load_ms"] == 1.0


def test_tflite_quantized_output(monkeypatch):
    logits = np.full((1, 4, 4, 1), -10, dtype=np.int8)
    logits[:, :2] = 10
    interpreter = FakeInterpreter((1, 4, 4, 3), logits, quantized=True)
    monkeypatch.setattr(tflite_inference, "_load_interpreter", lambda _: (interpreter, 0.0))

    mask, _ = tflite_inference.run_inference(
        "", "model.tflite", img_size=4, image_array=np.zeros((4, 4, 3), dtype=np.uint8)
    )

    assert interpreter.input.dtype == np.int8
    assert np.all(mask[:2] == 255) and np.all(mask[2:] == 0)