"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    settings = cfg["label_format"]
    issues = []

    def report(severity, code, stem, line_number, message, **extra):
        issues.append(
            Issue(
                check="label_format",
                severity=severity,
                code=code,
                image=stem,
                message=message,
                line=line_number,
                extra=extra,
            )
        )

    for label_file in ds.label_files():
        stem = label_file.stem
        image_size = ds.image_size(stem)
        previous_boxes = {}

        for line_number, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except (ValueError, OverflowError) as error:
                report(ERROR, "BAD_FORMAT", stem, line_number, str(error))
                continue

            if not 0 <= class_id < len(ds.classes):
                report(
                    ERROR, "BAD_CLASS_ID", stem, line_number,
                    f"ID lớp {class_id} nằm ngoài phạm vi hợp lệ",
                )
                continue

            if width <= 0 or height <= 0:
                report(
                    ERROR, "BOX_ZERO", stem, line_number,
                    f"Kích thước khung không hợp lệ: w={width}, h={height}",
                )
                continue

            left = cx - width / 2
            top = cy - height / 2
            right = cx + width / 2
            bottom = cy + height / 2
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)

            if overflow > settings["overflow_tol"]:
                report(
                    ERROR, "BOX_OUT_OF_IMAGE", stem, line_number,
                    f"Khung tràn ra ngoài ảnh {overflow:.4f}",
                    overflow=overflow,
                )

            box = (cx, cy, width, height)
            same_class_boxes = previous_boxes.setdefault(class_id, [])

            if any(
                iou_xywh(box, previous) > settings["dup_box_iou"]
                for previous in same_class_boxes
            ):
                report(
                    ERROR, "DUP_BOX", stem, line_number,
                    "Khung trùng với một khung cùng lớp ở dòng trước",
                )

            same_class_boxes.append(box)

            if image_size is not None:
                image_width, image_height = image_size
                short_side_px = min(width * image_width, height * image_height)

                if short_side_px < settings["min_box_px"]:
                    report(
                        WARN, "BOX_TINY", stem, line_number,
                        f"Cạnh ngắn của khung chỉ có {short_side_px:.1f} px",
                    )

            area_fraction = width * height
            if area_fraction > settings["max_box_frac"]:
                report(
                    WARN, "BOX_HUGE", stem, line_number,
                    f"Diện tích khung chiếm {area_fraction:.1%} diện tích ảnh",
                )

    return issues