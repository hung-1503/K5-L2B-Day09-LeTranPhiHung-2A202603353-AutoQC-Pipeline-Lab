"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip_box(text):
    cls, x, y, w, h = parse_yolo_line(text)
    left, top = x - w / 2, y - h / 2
    right, bottom = x + w / 2, y + h / 2
    if 0 <= left < right <= 1 and 0 <= top < bottom <= 1:
        return text

    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, 1), min(bottom, 1)
    if left >= right or top >= bottom:
        return None
    box = ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)
    return f"{cls} " + " ".join(str(value) for value in box)


def fix(ds, issues, cfg):
    errors = [issue for issue in issues if issue.severity == ERROR]
    fixes = []

    def record(image, line, action, before, after):
        fixes.append(dict(image=image, line=line, action=action, before=before, after=after))

    removed = {issue.image for issue in errors if issue.code in REMOVE_CODES}
    for stem in sorted(removed):
        image = ds.image_path(stem)
        label = ds.label_path(stem)
        if image is not None:
            image.unlink(missing_ok=True)
        if image is not None or label.exists():
            label.unlink(missing_ok=True)
            record(stem, None, "remove_image", image.name if image else label.name, "")

    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else {}
        data = data or {}
        if ds.yaml_names() != dict(enumerate(cfg["classes"])):
            before = data.get("names")
            data["names"] = list(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            record("data.yaml", None, "rename_classes", str(before), str(data["names"]))

    line_errors = defaultdict(dict)
    missing = set()
    for issue in errors:
        if issue.image in removed:
            continue
        if issue.code == "MISSING_LABEL_FILE":
            missing.add(issue.image)
        elif issue.line is not None:
            if issue.code in DROP_CODES:
                line_errors[issue.image][issue.line] = "drop_line"
            elif issue.code == "BOX_OUT_OF_IMAGE":
                line_errors[issue.image].setdefault(issue.line, "clip_box")

    for stem in sorted(missing):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            record(stem, None, "needs_label", "(không có file)", "chuyển người gán")

    for stem, actions in sorted(line_errors.items()):
        path = ds.label_path(stem)
        if not path.exists():
            continue
        original = path.read_bytes().decode("utf-8", errors="replace")
        updated = []
        for number, raw in enumerate(original.splitlines(keepends=True), 1):
            action = actions.get(number)
            if action is None or not raw.strip():
                updated.append(raw)
                continue
            before = raw.rstrip("\r\n")
            after = _clip_box(before) if action == "clip_box" else None
            if after is None:
                record(stem, number, "drop_line", before, "")
            elif after != before:
                updated.append(after + raw[len(before):])
                record(stem, number, "clip_box", before, after)
            else:
                updated.append(raw)
        result = "".join(updated)
        if result != original:
            path.write_bytes(result.encode("utf-8"))

    return fixes
