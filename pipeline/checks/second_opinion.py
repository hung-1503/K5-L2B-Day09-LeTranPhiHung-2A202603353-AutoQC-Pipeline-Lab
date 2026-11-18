"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _numbered_boxes(lines, class_count):
    for line, text in lines:
        try:
            cls, *box = parse_yolo_line(text)
        except (ValueError, OverflowError):
            continue
        if 0 <= cls < class_count and box[2] > 0 and box[3] > 0:
            yield line, cls, box


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    limits = cfg["second_opinion"]
    iou_missing = limits["iou_missing"]
    issues = []
    for path in ds.image_files():
        stem = path.stem
        if stem not in preds:
            continue
        lines = ds.read_label_lines(stem)
        if lines is None:
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        width, height = size
        labels = list(_numbered_boxes(lines, len(ds.classes)))
        model_boxes = preds[stem]

        for cls, conf, *box in model_boxes:
            if conf < limits["conf"] or box[2] * width * box[3] * height < limits["min_area_px"]:
                continue
            overlaps = [(label_cls, iou_xywh(box, label_box)) for _, label_cls, label_box in labels]
            candidates = [(label_cls, iou) for label_cls, iou in overlaps if iou >= iou_missing]
            if not candidates:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy lớp {cls} nhưng thiếu box khớp", extra={"conf": conf}))
                continue

            same_class = max((iou for label_cls, iou in candidates if label_cls == cls), default=None)
            if same_class is not None:
                if same_class < limits["iou_loose"]:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"box lớp {cls} có IoU {same_class:.2f}",
                                        extra={"conf": conf, "iou": same_class}))
                continue

            label_cls, best_iou = max(candidates, key=lambda candidate: candidate[1])
            if best_iou >= limits["iou_match"]:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    f"nhãn lớp {label_cls}, model dự đoán lớp {cls}",
                                    extra={"conf": conf, "iou": best_iou}))

        reference_boxes = [box for _, conf, *box in model_boxes if conf >= limits["fp_conf"]]
        for line, cls, box in labels:
            if not any(iou_xywh(box, ref) >= iou_missing for ref in reference_boxes):
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    f"model không thấy box khớp với nhãn lớp {cls}", line))
    return issues
