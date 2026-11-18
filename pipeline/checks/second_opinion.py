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
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    settings = cfg["second_opinion"]
    min_overlap = settings["iou_missing"]
    issues = []

    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    def warn(code, stem, message, line=None, **extra):
        issues.append(
            Issue(
                check="second_opinion",
                severity=WARN,
                code=code,
                image=stem,
                message=message,
                line=line,
                extra=extra,
            )
        )

    for image_path in ds.image_files():
        stem = image_path.stem
        if stem not in preds:
            continue

        label_lines = ds.read_label_lines(stem)
        if label_lines is None:
            continue

        labels = []
        for line_number, text in label_lines:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue

            if 0 <= class_id < len(ds.classes):
                labels.append((line_number, class_id, (cx, cy, width, height)))

        image_predictions = preds[stem]
        image_size = ds.image_size(stem)

        # So từng dự đoán đủ tin cậy và đủ lớn với các nhãn.
        if image_size is not None:
            image_width, image_height = image_size

            for class_id, confidence, cx, cy, width, height in image_predictions:
                area_px = (width * image_width) * (height * image_height)
                if (
                    confidence < settings["conf"]
                    or area_px < settings["min_area_px"]
                ):
                    continue

                prediction_box = (cx, cy, width, height)
                candidates = []
                for _, label_class, label_box in labels:
                    overlap = iou_xywh(prediction_box, label_box)
                    if overlap >= min_overlap:
                        candidates.append((label_class, overlap))

                if not candidates:
                    warn(
                        "POSSIBLE_MISSING", stem,
                        f"Có thể thiếu khung cho lớp {class_id}",
                        conf=confidence,
                    )
                    continue

                same_class = [
                    overlap
                    for label_class, overlap in candidates
                    if label_class == class_id
                ]

                if same_class:
                    best_overlap = max(same_class)
                    if best_overlap < settings["iou_loose"]:
                        warn(
                            "POSSIBLE_LOOSE_BOX", stem,
                            "Khung nhãn cùng lớp có thể bị lệch hoặc quá rộng",
                            conf=confidence, iou=best_overlap,
                        )
                    continue

                best_overlap = max(overlap for _, overlap in candidates)
                if best_overlap >= settings["iou_match"]:
                    warn(
                        "POSSIBLE_WRONG_CLASS", stem,
                        f"Khung có thể bị gán nhầm lớp; mô hình dự đoán lớp {class_id}",
                        conf=confidence, iou=best_overlap,
                    )

        # Kiểm tra chiều ngược lại: nhãn nào không khớp với dự đoán?
        reference_boxes = [
            (cx, cy, width, height)
            for _, confidence, cx, cy, width, height in image_predictions
            if confidence >= settings["fp_conf"]
        ]

        for line_number, _, label_box in labels:
            best_overlap = max(
                (iou_xywh(label_box, box) for box in reference_boxes),
                default=0.0,
            )
            if not reference_boxes or best_overlap < min_overlap:
                warn(
                    "POSSIBLE_FALSE_POS", stem,
                    "Khung nhãn có thể là khung thừa",
                    line=line_number, iou=best_overlap,
                )

    return issues