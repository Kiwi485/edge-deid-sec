"""Build cis-controls CSV from a judgment TSV and the per-control evidence files.

Usage: python3 build_controls_csv.py <judgments.tsv> <checks-dir-relative-to-cis-dir> <out.csv>
The TSV has columns: control_id, status, exception_reason, remediation (tab separated, '#' comments).
Titles come from controls.tsv (control_id, profile, mode, title) next to this script.
"""

import csv
import re
import sys
from pathlib import Path

CIS_DIR = Path(__file__).resolve().parents[1]
STATUSES = {"PASS", "FAIL", "NOT_CHECKED", "N/A"}


def read_tsv(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            rows.append(line.split("\t"))
    return rows


def main():
    judgments_path, checks_rel, out_path = sys.argv[1:4]
    controls = {r[0]: r for r in read_tsv(Path(__file__).with_name("controls.tsv"))}
    judgments = {r[0]: r for r in read_tsv(judgments_path)}
    missing = sorted(set(controls) - set(judgments), key=lambda c: [int(x) for x in c.split(".")])
    extra = sorted(set(judgments) - set(controls))
    if missing or extra:
        raise SystemExit(f"judgments mismatch: missing={missing} extra={extra}")

    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["control_id", "title", "profile", "mode", "applicable", "status",
                         "evidence", "exception_reason", "remediation", "verified_at"])
        for control_id, profile, mode, title in controls.values():
            _, status, reason, remediation = (judgments[control_id] + ["", "", ""])[:4]
            if status not in STATUSES:
                raise SystemExit(f"{control_id}: bad status {status}")
            if status == "N/A" and not reason:
                raise SystemExit(f"{control_id}: N/A needs a reason")
            evidence = f"{checks_rel}/{control_id}.txt"
            text = (CIS_DIR / evidence).read_text(encoding="utf-8", errors="replace")
            verified_at = re.search(r"collected: (\S+)", text).group(1)
            writer.writerow([control_id, title, profile, mode, str(status != "N/A").lower(), status,
                             evidence, reason, remediation, verified_at])
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
