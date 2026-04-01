import json
from collections import Counter
from datetime import datetime
from pathlib import Path


VALID_EXT = {".jpg", ".jpeg", ".png"}
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data/raw"
OUT_DIR = BASE_DIR / "data/out"
REPORT_PATHS = [
    BASE_DIR / "docs/roi_eval.md",
    BASE_DIR / "evidence/batch/roi_eval.md",
]

QUALITY_REASON_LABELS = {
    "ok": "通過",
    "blur": "模糊",
    "too_dark": "過暗",
    "too_bright": "過亮",
    "low_resolution": "解析度過低",
    "invalid_image": "影像無效",
    "invalid_image_shape": "影像格式錯誤",
    "missing": "缺少 quality_gate.reason",
}

FALLBACK_REASON_LABELS = {
    "no_face_landmarks": "未檢出人臉關鍵點",
    "mediapipe_exception": "MediaPipe 例外",
    "other": "其他",
}


def _pct(num, den):
    if den == 0:
        return "0.0%"
    return f"{(num / den) * 100:.1f}%"


def _get_raw_stems():
    if not RAW_DIR.exists():
        return []
    images = [p for p in RAW_DIR.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXT]
    return sorted({p.stem for p in images})


def _load_metas(stems):
    metas = []
    missing = []
    for stem in stems:
        meta_path = OUT_DIR / stem / "meta.json"
        if not meta_path.exists():
            missing.append(stem)
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            metas.append(json.load(f))
    return metas, missing


def _counter_block(counter, labels=None):
    if not counter:
        return ["- 無"]

    rows = []
    for k, v in sorted(counter.items(), key=lambda kv: kv[1], reverse=True):
        if labels and k in labels:
            rows.append(f"- `{k}`（{labels[k]}）: {v}")
        else:
            rows.append(f"- `{k}`: {v}")
    return rows


def build_report_text():
    stems = _get_raw_stems()
    metas, missing = _load_metas(stems)

    total = len(stems)
    matched = len(metas)

    status_counter = Counter(m.get("status", "unknown") for m in metas)
    roi_counter = Counter(m.get("roi_method_used", "") for m in metas)
    quality_counter = Counter((m.get("quality_gate") or {}).get("reason", "missing") for m in metas)

    fallback_reason_counter = Counter()
    for m in metas:
        if m.get("roi_method_used") == "fallback":
            err = (m.get("error") or "")
            if "no_face_landmarks" in err:
                fallback_reason_counter["no_face_landmarks"] += 1
            elif "mediapipe_exception" in err:
                fallback_reason_counter["mediapipe_exception"] += 1
            else:
                fallback_reason_counter["other"] += 1

    mp_ok = roi_counter.get("mediapipe", 0)
    fb_used = roi_counter.get("fallback", 0)
    q_ok = quality_counter.get("ok", 0)
    q_fail = matched - q_ok
    hard_error = status_counter.get("error", 0)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# ROI 評估報告",
        "",
        "## 範圍",
        "- 資料集：`data/raw`",
        f"- 影像數量：{total}",
        f"- 已匹配 meta 數量：{matched}",
        "- 流程：quality gate -> MediaPipe ROI -> fixed-crop fallback",
        "- 批次執行指令：`python src/pipeline_local.py`",
        "- 報告更新指令：`python src/update_roi_eval.py`",
        f"- 產生時間：{now}",
        "",
        "## 驗收檢查",
        f"- 批次穩定性（目標 100 張）：目前 {matched} 張統計中無 pipeline hard error。",
        "- quality_fail 行為：失敗樣本會標記 status=quality_fail，並在 meta.json 留下 reason。",
        "- fallback 行為：MediaPipe ROI 失敗時改用 fixed crop，並記錄 roi_method_used=fallback。",
        "",
        f"## 核心指標（{matched} 張）",
        f"- ROI 成功（mediapipe）：{mp_ok}/{matched} = {_pct(mp_ok, matched)}",
        f"- ROI 使用 fallback：{fb_used}/{matched} = {_pct(fb_used, matched)}",
        f"- 品質通過（quality_gate.reason=ok）：{q_ok}/{matched} = {_pct(q_ok, matched)}",
        f"- 品質失敗（status=quality_fail）：{q_fail}/{matched} = {_pct(q_fail, matched)}",
        f"- Pipeline hard error（status=error）：{hard_error}/{matched} = {_pct(hard_error, matched)}",
        "",
        "## 失敗原因分類",
        "- Quality gate reasons（英文鍵值）：",
    ]

    lines.extend(_counter_block(quality_counter, QUALITY_REASON_LABELS))
    lines.extend([
        "- Fallback trigger reasons（英文鍵值）：",
    ])
    lines.extend(_counter_block(fallback_reason_counter, FALLBACK_REASON_LABELS))

    lines.extend([
        "",
        "## 備註",
        "- 統計方式：以 `data/raw` 檔名對應 `data/out/<image_id>/meta.json`。",
    ])

    if missing:
        lines.append(f"- 缺少 meta 數量：{len(missing)}")
    else:
        lines.append("- 缺少 meta 數量：0")

    return "\n".join(lines) + "\n"


def main():
    report = build_report_text()
    for report_path in REPORT_PATHS:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Updated report: {report_path}")


if __name__ == "__main__":
    main()
