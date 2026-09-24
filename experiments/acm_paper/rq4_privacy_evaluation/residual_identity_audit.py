"""Create and summarize a manual residual identity-cue audit."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


CUES = {
    "teeth": "Natural or artificial tooth structure, including a visible tooth edge.",
    "dental_hardware": "Braces, wires, brackets, retainers, fillings, or other dental hardware.",
    "lips": "Lip tissue or a recognizable lip boundary/contour.",
    "facial_skin": "Non-lip facial skin, including visible skin texture or pigmentation.",
    "facial_jaw_contour": "A recognizable facial, cheek, chin, or jaw outline.",
    "distinctive_marker": "A scar, mole, tattoo, lesion, or other potentially distinctive marker.",
    "other": "Any other visible non-tongue content that could plausibly carry identity information.",
}
FIELDNAMES = ["image_id", *CUES, "notes"]
VALID_SCORES = {0, 1, 2}


def write_template(path: Path, image_count: int = 15) -> None:
    if image_count < 1:
        raise ValueError("image_count must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for index in range(1, image_count + 1):
            writer.writerow({"image_id": f"E{index:02d}", **{cue: "" for cue in CUES}, "notes": ""})


def read_annotations(path: Path, expected_count: int | None = 15) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in FIELDNAMES if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing columns in {path}: {', '.join(missing)}")
        rows = list(reader)
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f"expected {expected_count} annotation rows, found {len(rows)}")
    identifiers = [row["image_id"].strip() for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("image_id values must be unique")
    for row in rows:
        row["image_id"] = row["image_id"].strip()
        for cue in CUES:
            raw = row[cue].strip()
            try:
                score = int(raw)
            except ValueError as exc:
                raise ValueError(f"{row['image_id']} {cue}: score must be 0, 1, or 2") from exc
            if score not in VALID_SCORES:
                raise ValueError(f"{row['image_id']} {cue}: score must be 0, 1, or 2")
            row[cue] = score
    return rows


def aggregate(rows: Iterable[dict]) -> dict:
    records = list(rows)
    if not records:
        raise ValueError("at least one annotation row is required")
    result: dict[str, dict[str, int | float]] = {}
    for cue in CUES:
        any_count = sum(int(row[cue] >= 1) for row in records)
        clear_count = sum(int(row[cue] == 2) for row in records)
        result[cue] = {
            "any_residual_cases": any_count,
            "clearly_visible_cases": clear_count,
            "rate_any_percent": round(100.0 * any_count / len(records), 1),
        }
    any_per_image = [max(row[cue] for cue in CUES) for row in records]
    any_count = sum(score >= 1 for score in any_per_image)
    clear_count = sum(score == 2 for score in any_per_image)
    result["any_identity_relevant_cue"] = {
        "any_residual_cases": any_count,
        "clearly_visible_cases": clear_count,
        "rate_any_percent": round(100.0 * any_count / len(records), 1),
    }
    return {"number_of_images": len(records), "cues": result}


def agreement(first: list[dict], second: list[dict]) -> dict:
    first_by_id = {row["image_id"]: row for row in first}
    second_by_id = {row["image_id"]: row for row in second}
    if set(first_by_id) != set(second_by_id):
        raise ValueError("reviewer files must contain the same image_id values")
    result = {}
    for cue in CUES:
        pairs = [(first_by_id[key][cue], second_by_id[key][cue]) for key in sorted(first_by_id)]
        observed = sum(a == b for a, b in pairs) / len(pairs)
        counts_a, counts_b = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
        expected = sum((counts_a[s] / len(pairs)) * (counts_b[s] / len(pairs)) for s in VALID_SCORES)
        kappa = 1.0 if expected == 1.0 and observed == 1.0 else (observed - expected) / (1.0 - expected)
        result[cue] = {"exact_agreement_percent": round(observed * 100, 1), "cohen_kappa": round(kappa, 3)}
    return result


def _label(cue: str) -> str:
    return {
        "dental_hardware": "Braces or dental hardware",
        "lips": "Lip tissue or contour",
        "facial_skin": "Facial skin",
        "facial_jaw_contour": "Facial or jaw contour",
        "distinctive_marker": "Distinctive marker",
        "any_identity_relevant_cue": "Any identity-relevant cue",
    }.get(cue, cue.replace("_", " ").title())


def write_summary(summary: dict, markdown_path: Path, json_path: Path | None = None) -> None:
    total = summary["number_of_images"]
    lines = [
        "# Residual Identity-Cue Audit Results",
        "",
        "Scores 1 (possibly visible) and 2 (clearly visible) are counted as residual cues.",
        "",
        "| Residual identity cue | Any residual cases | Clearly visible cases | Rate of any residual cue |",
        "|---|---:|---:|---:|",
    ]
    for cue, values in summary["cues"].items():
        lines.append(
            f"| {_label(cue)} | {values['any_residual_cases']} / {total} | "
            f"{values['clearly_visible_cases']} / {total} | {values['rate_any_percent']:.1f}% |"
        )
    lines.extend([
        "",
        "This visible-cue audit supplements pixel-level removal metrics. It does not establish formal anonymity or resistance to re-identification attacks.",
        "",
    ])
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="Create a blank annotation sheet")
    init_parser.add_argument("--output", type=Path, required=True)
    init_parser.add_argument("--image-count", type=int, default=15)
    summarize_parser = subparsers.add_parser("summarize", help="Validate and aggregate one completed sheet")
    summarize_parser.add_argument("--annotations", type=Path, required=True)
    summarize_parser.add_argument("--markdown", type=Path, required=True)
    summarize_parser.add_argument("--json", type=Path)
    summarize_parser.add_argument("--expected-count", type=int, default=15)
    agreement_parser = subparsers.add_parser("agreement", help="Compare two independent reviewer sheets")
    agreement_parser.add_argument("--reviewer-a", type=Path, required=True)
    agreement_parser.add_argument("--reviewer-b", type=Path, required=True)
    agreement_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "init":
        write_template(args.output, args.image_count)
    elif args.command == "summarize":
        rows = read_annotations(args.annotations, args.expected_count)
        write_summary(aggregate(rows), args.markdown, args.json)
    else:
        first = read_annotations(args.reviewer_a)
        second = read_annotations(args.reviewer_b)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(agreement(first, second), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
