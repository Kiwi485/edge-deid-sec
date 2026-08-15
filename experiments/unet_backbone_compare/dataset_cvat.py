from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.utils.data import Dataset


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
MASK_EXTENSIONS = {".png", ".bmp", ".tif", ".tiff"}
IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def find_image_dir(data_root: Path) -> Path:
    image_dir = data_root / "images"
    if image_dir.exists():
        return image_dir
    return data_root


def find_annotations_dir(data_root: Path) -> Path:
    annotations_dir = data_root / "annotations"
    if not annotations_dir.exists():
        raise FileNotFoundError(f"Annotation directory not found: {annotations_dir}")
    return annotations_dir


def detect_annotation_format(annotations_dir: Path) -> str:
    json_files = sorted(annotations_dir.glob("*.json"))
    xml_files = sorted(annotations_dir.glob("*.xml"))
    mask_files = [p for p in annotations_dir.rglob("*") if p.suffix.lower() in MASK_EXTENSIONS]
    if json_files:
        with json_files[0].open("r", encoding="utf-8") as f:
            data = json.load(f)
        if {"images", "annotations", "categories"}.issubset(data.keys()):
            return "coco_json"
        return "json"
    if xml_files:
        return "cvat_xml"
    if mask_files:
        return "mask_png"
    raise FileNotFoundError(f"No supported annotation files found in {annotations_dir}")


def collect_images(image_dir: Path) -> dict[str, Path]:
    images: dict[str, Path] = {}
    for path in image_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images[path.name] = path
            images[path.stem] = path
    return images


def _polygon_to_mask(size: tuple[int, int], segmentation: list[Any]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    polygons = segmentation if segmentation and isinstance(segmentation[0], list) else [segmentation]
    for polygon in polygons:
        if len(polygon) >= 6:
            points = [(float(polygon[i]), float(polygon[i + 1])) for i in range(0, len(polygon), 2)]
            draw.polygon(points, outline=1, fill=1)
    return mask


def _decode_uncompressed_rle(size_hw: tuple[int, int], counts: list[int]) -> np.ndarray:
    height, width = size_hw
    values = []
    value = 0
    for count in counts:
        values.extend([value] * int(count))
        value = 1 - value
    flat = np.array(values[: height * width], dtype=np.uint8)
    if flat.size < height * width:
        flat = np.pad(flat, (0, height * width - flat.size))
    return flat.reshape((width, height)).T


def _coco_segmentation_to_mask(size: tuple[int, int], segmentation: Any) -> Image.Image:
    if isinstance(segmentation, list):
        return _polygon_to_mask(size, segmentation)
    if isinstance(segmentation, dict) and isinstance(segmentation.get("counts"), list):
        arr = _decode_uncompressed_rle(tuple(segmentation["size"]), segmentation["counts"])
        return Image.fromarray((arr > 0).astype(np.uint8), mode="L")
    if isinstance(segmentation, dict):
        try:
            from pycocotools import mask as mask_utils
        except ImportError as exc:
            raise ImportError("Compressed COCO RLE masks require pycocotools.") from exc
        arr = mask_utils.decode(segmentation)
        return Image.fromarray((arr > 0).astype(np.uint8), mode="L")
    return Image.new("L", size, 0)


def _parse_points(points_text: str) -> list[tuple[float, float]]:
    points = []
    for pair in points_text.split(";"):
        if not pair.strip():
            continue
        x, y = pair.split(",")
        points.append((float(x), float(y)))
    return points


def _decode_cvat_mask_rle(rle: str, width: int, height: int) -> np.ndarray:
    counts = [int(v) for v in rle.replace(",", " ").split() if v.strip()]
    values = []
    value = 0
    for count in counts:
        values.extend([value] * count)
        value = 1 - value
    flat = np.array(values[: width * height], dtype=np.uint8)
    if flat.size < width * height:
        flat = np.pad(flat, (0, width * height - flat.size))
    return flat.reshape((height, width))


class CvatSegmentationDataset(Dataset):
    def __init__(
        self,
        data_root: str | Path = "cvat/train",
        img_size: int = 256,
        normalize: bool = True,
        annotation_format: str | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.image_dir = find_image_dir(self.data_root)
        self.annotations_dir = find_annotations_dir(self.data_root)
        self.img_size = img_size
        self.normalize = normalize
        self.annotation_format = annotation_format or detect_annotation_format(self.annotations_dir)
        self.image_lookup = collect_images(self.image_dir)

        if self.annotation_format == "coco_json":
            self.samples = self._load_coco_samples()
        elif self.annotation_format == "cvat_xml":
            self.samples = self._load_cvat_xml_samples()
        elif self.annotation_format == "mask_png":
            self.samples = self._load_mask_png_samples()
        else:
            raise ValueError(f"Unsupported annotation format: {self.annotation_format}")

        if not self.samples:
            raise RuntimeError(f"No image/mask samples found under {self.data_root}")

    def _resolve_image(self, file_name: str) -> Path | None:
        return self.image_lookup.get(file_name) or self.image_lookup.get(Path(file_name).name) or self.image_lookup.get(Path(file_name).stem)

    def _load_coco_samples(self) -> list[dict[str, Any]]:
        json_files = sorted(self.annotations_dir.glob("*.json"))
        with json_files[0].open("r", encoding="utf-8") as f:
            data = json.load(f)

        anns_by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
        category_names = {cat["id"]: cat.get("name", "").lower() for cat in data.get("categories", [])}
        for ann in data.get("annotations", []):
            name = category_names.get(ann.get("category_id"), "")
            if name and name != "tongue":
                continue
            anns_by_image[int(ann["image_id"])].append(ann)

        samples = []
        for image_info in data.get("images", []):
            image_path = self._resolve_image(image_info["file_name"])
            if image_path is None:
                continue
            samples.append(
                {
                    "image_path": image_path,
                    "width": int(image_info["width"]),
                    "height": int(image_info["height"]),
                    "annotations": anns_by_image.get(int(image_info["id"]), []),
                    "source": "coco_json",
                }
            )
        return samples

    def _load_cvat_xml_samples(self) -> list[dict[str, Any]]:
        xml_file = sorted(self.annotations_dir.glob("*.xml"))[0]
        root = ET.parse(xml_file).getroot()
        samples = []
        for image_node in root.findall(".//image"):
            image_path = self._resolve_image(image_node.attrib["name"])
            if image_path is None:
                continue
            shapes = []
            for polygon in image_node.findall("polygon"):
                if polygon.attrib.get("label", "").lower() == "tongue":
                    shapes.append({"type": "polygon", "points": _parse_points(polygon.attrib["points"])})
            for mask in image_node.findall("mask"):
                if mask.attrib.get("label", "").lower() == "tongue":
                    shapes.append({"type": "mask", "attributes": dict(mask.attrib)})
            samples.append(
                {
                    "image_path": image_path,
                    "width": int(float(image_node.attrib["width"])),
                    "height": int(float(image_node.attrib["height"])),
                    "annotations": shapes,
                    "source": "cvat_xml",
                }
            )
        return samples

    def _load_mask_png_samples(self) -> list[dict[str, Any]]:
        masks = [p for p in self.annotations_dir.rglob("*") if p.suffix.lower() in MASK_EXTENSIONS]
        samples = []
        for mask_path in sorted(masks):
            image_path = self._resolve_image(mask_path.stem)
            if image_path is None:
                continue
            with Image.open(image_path) as img:
                width, height = img.size
            samples.append({"image_path": image_path, "mask_path": mask_path, "width": width, "height": height, "source": "mask_png"})
        return samples

    def __len__(self) -> int:
        return len(self.samples)

    def _build_mask(self, sample: dict[str, Any]) -> Image.Image:
        size = (sample["width"], sample["height"])
        mask = Image.new("L", size, 0)
        if sample["source"] == "mask_png":
            with Image.open(sample["mask_path"]) as mask_img:
                return mask_img.convert("L").point(lambda p: 1 if p > 0 else 0)
        if sample["source"] == "coco_json":
            for ann in sample["annotations"]:
                ann_mask = _coco_segmentation_to_mask(size, ann.get("segmentation", []))
                mask = Image.fromarray(np.maximum(np.array(mask, dtype=np.uint8), np.array(ann_mask, dtype=np.uint8)), mode="L")
            return mask
        for shape in sample["annotations"]:
            if shape["type"] == "polygon":
                shape_mask = Image.new("L", size, 0)
                ImageDraw.Draw(shape_mask).polygon(shape["points"], outline=1, fill=1)
                mask = Image.fromarray(np.maximum(np.array(mask, dtype=np.uint8), np.array(shape_mask, dtype=np.uint8)), mode="L")
            elif shape["type"] == "mask":
                attrs = shape["attributes"]
                left = int(float(attrs.get("left", 0)))
                top = int(float(attrs.get("top", 0)))
                width = int(float(attrs["width"]))
                height = int(float(attrs["height"]))
                rle = attrs.get("rle", "")
                decoded = _decode_cvat_mask_rle(rle, width, height)
                canvas = np.array(mask, dtype=np.uint8)
                canvas[top : top + height, left : left + width] = np.maximum(canvas[top : top + height, left : left + width], decoded)
                mask = Image.fromarray(canvas, mode="L")
        return mask

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]
        with Image.open(sample["image_path"]) as img:
            image = img.convert("RGB")
        mask = self._build_mask(sample)

        image = image.resize((self.img_size, self.img_size), resample=Image.Resampling.BILINEAR)
        mask = mask.resize((self.img_size, self.img_size), resample=Image.Resampling.NEAREST)

        image_tensor = torch.from_numpy(np.asarray(image, dtype=np.float32)).permute(2, 0, 1) / 255.0
        if self.normalize:
            image_tensor = (image_tensor - IMAGENET_MEAN) / IMAGENET_STD
        mask_tensor = torch.from_numpy((np.asarray(mask, dtype=np.uint8) > 0).astype(np.float32)).unsqueeze(0)
        return image_tensor, mask_tensor
