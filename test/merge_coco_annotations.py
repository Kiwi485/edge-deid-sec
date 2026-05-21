"""
合併兩個 COCO JSON 標注檔案（instances_default.json）。
用法：
    python test/merge_coco_annotations.py \
        --a data/cvat/train/annotations/instances_default.json \
        --b <新的 500 張標注 JSON 路徑> \
        --out data/cvat/train/annotations/instances_default_merged.json
"""

import argparse
import json
import copy


def merge_coco(path_a: str, path_b: str, output: str) -> None:
    with open(path_a, "r", encoding="utf-8") as f:
        data_a = json.load(f)
    with open(path_b, "r", encoding="utf-8") as f:
        data_b = json.load(f)

    # 確保 categories 一致（直接沿用 A 的）
    merged = copy.deepcopy(data_a)

    # 計算 A 的最大 image_id 和 annotation id
    max_img_id = max((img["id"] for img in data_a["images"]), default=0)
    max_ann_id = max((ann["id"] for ann in data_a["annotations"]), default=0)

    # 收集 A 已有的檔名，避免重複加入相同圖片
    existing_filenames = {img["file_name"] for img in data_a["images"]}

    # 建立 B 的 image_id 對應表
    img_id_map: dict[int, int] = {}
    for img in data_b["images"]:
        if img["file_name"] in existing_filenames:
            # 找到 A 中對應的 id
            for a_img in data_a["images"]:
                if a_img["file_name"] == img["file_name"]:
                    img_id_map[img["id"]] = a_img["id"]
                    break
        else:
            max_img_id += 1
            new_img = copy.deepcopy(img)
            new_img["id"] = max_img_id
            img_id_map[img["id"]] = max_img_id
            merged["images"].append(new_img)

    # 合併 annotations（只加入有對應圖片的標注）
    for ann in data_b["annotations"]:
        if ann["image_id"] not in img_id_map:
            continue
        max_ann_id += 1
        new_ann = copy.deepcopy(ann)
        new_ann["id"] = max_ann_id
        new_ann["image_id"] = img_id_map[ann["image_id"]]
        merged["annotations"].append(new_ann)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)

    print(f"完成！圖片數: {len(merged['images'])}，標注數: {len(merged['annotations'])}")
    print(f"輸出路徑: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="合併兩個 COCO JSON 標注檔案")
    parser.add_argument("--a", required=True, help="原始標注 JSON（150 張）")
    parser.add_argument("--b", required=True, help="新增標注 JSON（500 張）")
    parser.add_argument("--out", required=True, help="合併後輸出路徑")
    args = parser.parse_args()

    merge_coco(args.a, args.b, args.out)
