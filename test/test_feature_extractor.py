import cv2
import numpy as np
import pytest

from src.seg.feature_extractor import FEATURE_VERSION, _glcm_features, extract_features


def test_feature_contract_and_reproducibility():
    image = np.random.default_rng(42).integers(0, 256, (16, 20, 3), dtype=np.uint8)
    mask = np.full((16, 20), 255, dtype=np.uint8)
    features = extract_features(image, mask)
    assert FEATURE_VERSION == "v2_glcm"
    assert features.shape == (256,)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    np.testing.assert_array_equal(features, extract_features(image, mask))
    for start in (0, 16, 32):
        assert features[start:start + 16].sum() == pytest.approx(1.0)
    assert features[144:240].sum() == pytest.approx(1.0)
    assert np.all((features[240:] >= 0) & (features[240:] <= 1))


@pytest.mark.parametrize("shape", [(1, 1), (1, 5), (5, 1), (6, 6)])
def test_empty_and_small_masks(shape):
    image = np.full((*shape, 3), 128, dtype=np.uint8)
    mask = np.zeros(shape, dtype=np.uint8)
    np.testing.assert_array_equal(extract_features(image, mask), np.zeros(256, np.float32))
    mask[0, 0] = 255
    features = extract_features(image, mask)
    assert features.shape == (256,)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
    np.testing.assert_array_equal(features[240:], np.zeros(16))


def test_constant_region_glcm():
    image = np.full((5, 5, 3), 128, dtype=np.uint8)
    features = extract_features(image, np.ones((5, 5), np.uint8))
    np.testing.assert_allclose(features[240:].reshape(4, 4), np.tile([0, 0, 1, 1], (4, 1)))


def test_checkerboard_glcm_direction_order():
    gray = (np.indices((6, 6)).sum(axis=0) % 2 * 255).astype(np.uint8)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    features = _glcm_features(image, np.ones(gray.shape, bool)).reshape(4, 4)
    np.testing.assert_allclose(features[[0, 2]], np.tile([1, 1, 1 / 962, np.sqrt(0.5)], (2, 1)), rtol=1e-6)
    np.testing.assert_allclose(features[[1, 3], :3], np.tile([0, 0, 1], (2, 1)))


def test_masked_glcm_matches_manual_pair_counts_and_ignores_background():
    image = np.random.default_rng(7).integers(0, 256, (5, 6, 3), dtype=np.uint8)
    mask = np.array([
        [1, 1, 0, 0, 0, 1],
        [1, 0, 1, 1, 0, 1],
        [1, 1, 1, 0, 1, 1],
        [0, 0, 1, 1, 1, 0],
        [1, 0, 0, 0, 0, 1],
    ], dtype=bool)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.int32) // 8
    expected = []
    for row_offset, col_offset in ((0, 1), (1, 1), (1, 0), (1, -1)):
        counts = np.zeros((32, 32), dtype=np.float64)
        for row, col in np.argwhere(mask):
            next_row, next_col = row + row_offset, col + col_offset
            if 0 <= next_row < 5 and 0 <= next_col < 6 and mask[next_row, next_col]:
                source, target = gray[row, col], gray[next_row, next_col]
                counts[source, target] += 1
                counts[target, source] += 1
        probabilities = counts / counts.sum()
        difference = np.arange(32)[:, None] - np.arange(32)[None, :]
        expected.extend([
            (probabilities * difference ** 2).sum() / 31 ** 2,
            (probabilities * abs(difference)).sum() / 31,
            (probabilities / (1 + difference ** 2)).sum(),
            np.sqrt((probabilities ** 2).sum()),
        ])
    actual = _glcm_features(image, mask)
    np.testing.assert_allclose(actual, expected, rtol=1e-6)
    changed = image.copy()
    changed[~mask] = 255
    np.testing.assert_array_equal(actual, _glcm_features(changed, mask))
    np.testing.assert_array_equal(extract_features(image, mask.astype(np.uint8))[240:], actual)


def test_missing_inputs_and_mask_resize():
    image = np.zeros((8, 8, 3), np.uint8)
    np.testing.assert_array_equal(extract_features(None, None), np.zeros(256, np.float32))
    np.testing.assert_array_equal(extract_features(image, None), np.zeros(256, np.float32))
    mask = np.array([[0, 1], [1, 1]], np.uint8)
    resized = cv2.resize(mask, (8, 8), interpolation=cv2.INTER_NEAREST)
    np.testing.assert_array_equal(extract_features(image, mask), extract_features(image, resized))