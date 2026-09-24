"""Generate anonymous, consistently scaled outputs for the Study 4 audit.

The source-to-anonymous-ID map is deliberately written as ``*.private.json``
inside the generated output directory.  Do not publish that file with the
audit results.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiments.acm_paper.rq1_model_selection.evaluate_smp import load_checkpoint
from src.seg.model import build_model_by_arch


IMAGENET_MEAN = np.asarray([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.asarray([0.229, 0.224, 0.225], dtype=np.float32)


def _test_samples(manifest_path: Path) -> tuple[Path, list[dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_dir = Path(manifest["dataset_dir"])
    samples = [s for s in manifest["samples"] if s["assigned_split"] == "test"]
    if not samples:
        raise ValueError("manifest contains no samples assigned to the test split")
    return dataset_dir, samples


def _predict_mask(
    model: torch.nn.Module,
    image_bgr: np.ndarray,
    image_size: int,
    threshold: float,
    device: torch.device,
) -> np.ndarray:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (image_size, image_size), interpolation=cv2.INTER_LINEAR)
    normalized = (resized.astype(np.float32) / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = torch.from_numpy(normalized.transpose(2, 0, 1)).unsqueeze(0).to(device)
    with torch.no_grad():
        probability = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
    mask_small = (probability >= threshold).astype(np.uint8) * 255
    height, width = image_bgr.shape[:2]
    return cv2.resize(mask_small, (width, height), interpolation=cv2.INTER_NEAREST)


def _make_contact_sheet(
    images: list[tuple[str, np.ndarray]],
    output_path: Path,
    tile_size: int = 320,
    columns: int = 5,
) -> None:
    label_height = 36
    rows = (len(images) + columns - 1) // columns
    sheet = np.full((rows * (tile_size + label_height), columns * tile_size, 3), 32, np.uint8)
    for index, (image_id, image) in enumerate(images):
        row, column = divmod(index, columns)
        height, width = image.shape[:2]
        scale = min(tile_size / width, tile_size / height)
        display = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
        )
        y0 = row * (tile_size + label_height)
        x0 = column * tile_size
        offset_y = y0 + (tile_size - display.shape[0]) // 2
        offset_x = x0 + (tile_size - display.shape[1]) // 2
        sheet[offset_y : offset_y + display.shape[0], offset_x : offset_x + display.shape[1]] = display
        cv2.putText(
            sheet,
            image_id,
            (x0 + 8, y0 + tile_size + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise OSError(f"failed to write contact sheet: {output_path}")


def generate_outputs(
    manifest_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    architecture: str = "unet_mobilenet",
    image_size: int = 256,
    threshold: float = 0.5,
    device_name: str = "cpu",
) -> int:
    dataset_dir, samples = _test_samples(manifest_path)
    device = torch.device(device_name)
    model = build_model_by_arch(architecture, encoder_weights=None).to(device)
    load_checkpoint(checkpoint_path, model, device)
    model.eval()

    deidentified_dir = output_dir / "deidentified"
    deidentified_dir.mkdir(parents=True, exist_ok=True)
    source_map: dict[str, str] = {}
    contact_images: list[tuple[str, np.ndarray]] = []

    for index, sample in enumerate(samples, start=1):
        image_id = f"E{index:02d}"
        source_path = dataset_dir / sample["image_path"]
        image = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"cannot read source image for {image_id}: {source_path}")
        mask = _predict_mask(model, image, image_size, threshold, device)
        deidentified = np.zeros_like(image)
        deidentified[mask > 0] = image[mask > 0]
        destination = deidentified_dir / f"{image_id}.png"
        if not cv2.imwrite(str(destination), deidentified):
            raise OSError(f"failed to write {destination}")
        source_map[image_id] = str(source_path.resolve())
        contact_images.append((image_id, deidentified))

    provenance = {
        "split_manifest": str(manifest_path.resolve()),
        "checkpoint": str(checkpoint_path.resolve()),
        "architecture": architecture,
        "image_size": image_size,
        "threshold": threshold,
        "number_of_images": len(samples),
        "source_map": source_map,
    }
    (output_dir / "source_map.private.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    _make_contact_sheet(contact_images, output_dir / "contact_sheet.private.png")
    return len(samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("outputs/acm_paper/rq1/split_manifest.json"))
    parser.add_argument("--checkpoint", type=Path, default=Path("models/acm_paper/rq1/unet_mobilenet/best.pth"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/acm_paper/rq4/audit_images"))
    parser.add_argument("--architecture", default="unet_mobilenet")
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    count = generate_outputs(
        args.manifest,
        args.checkpoint,
        args.output_dir,
        args.architecture,
        args.image_size,
        args.threshold,
        args.device,
    )
    print(f"Generated {count} anonymous audit outputs in {args.output_dir}")


if __name__ == "__main__":
    main()
