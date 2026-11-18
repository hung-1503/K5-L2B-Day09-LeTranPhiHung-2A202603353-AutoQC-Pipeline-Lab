"""Optional QC check for unusually elongated YOLO bounding boxes."""

import argparse
from pathlib import Path

from ..common import WARN, Dataset, Issue, load_config, parse_yolo_line, write_issues_csv

DEFAULT_MAX_RATIO = 12.0


def run(ds, cfg):
    max_ratio = cfg.get("aspect_ratio", {}).get("max_ratio", DEFAULT_MAX_RATIO)
    issues = []
    for path in ds.image_files():
        stem = path.stem
        size = ds.image_size(stem)
        if size is None:
            continue
        for line, text in ds.read_label_lines(stem) or []:
            try:
                cls, _, _, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue
            if not 0 <= cls < len(ds.classes) or width <= 0 or height <= 0:
                continue
            width_px, height_px = width * size[0], height * size[1]
            if min(width_px, height_px) <= 0:
                continue
            ratio = max(width_px, height_px) / min(width_px, height_px)
            if ratio > max_ratio:
                issues.append(Issue(
                    "aspect_ratio", WARN, "BOX_EXTREME_ASPECT", stem,
                    f"Tỷ lệ cạnh box {ratio:.2f}:1 vượt ngưỡng {max_ratio:g}:1",
                    line, {"ratio": round(ratio, 3), "max_ratio": max_ratio},
                ))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("work/run/ds"))
    parser.add_argument("--out", type=Path, default=Path("work/aspect_ratio.csv"))
    parser.add_argument("--max-ratio", type=float, default=DEFAULT_MAX_RATIO)
    args = parser.parse_args()
    if not 1 <= args.max_ratio < float("inf"):
        parser.error("--max-ratio must be finite and at least 1")

    cfg = load_config()
    ds = Dataset(args.dataset, cfg["classes"])
    if not ds.images_dir.is_dir() or not ds.labels_dir.is_dir():
        parser.error("--dataset must contain images/ and labels/")
    cfg["aspect_ratio"] = {"max_ratio": args.max_ratio}
    issues = run(ds, cfg)
    write_issues_csv(issues, args.out)
    print(f"{len(issues)} warnings -> {args.out}")


if __name__ == "__main__":
    main()
