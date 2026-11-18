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
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}

    fixes = []
    images_to_remove = set()
    images_needing_labels = set()
    line_actions = defaultdict(dict)
    rename_classes = False

    def log(image, line, action, before, after):
        fixes.append({
            "image": image,
            "line": line,
            "action": action,
            "before": before,
            "after": after,
        })

    # Gom lỗi theo ảnh và số dòng gốc.
    for issue in issues:
        if issue.severity != ERROR:
            continue

        code = issue.code
        if code in remove_codes or code.startswith("DUP_IMAGE_"):
            images_to_remove.add(issue.image)
        elif code == "MISSING_LABEL_FILE":
            images_needing_labels.add(issue.image)
        elif code == "BAD_CLASS_NAME":
            rename_classes = True
        elif issue.line is not None:
            if code in drop_codes:
                line_actions[issue.image][issue.line] = "drop_line"
            elif code == "BOX_OUT_OF_IMAGE":
                line_actions[issue.image].setdefault(issue.line, "clip_box")

    # Xử lý ảnh bị loại trước khi sửa các dòng nhãn.
    for stem in sorted(images_to_remove):
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        removed_files = []

        for path in (image_path, label_path):
            if path is not None and path.is_file():
                path.unlink()
                removed_files.append(path.name)

        if removed_files:
            log(stem, None, "remove_image", ", ".join(removed_files), "")

    # Ghi log để chuyển người gán nhãn.
    for stem in sorted(images_needing_labels - images_to_remove):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            log(stem, None, "needs_label", "(không có file)", "chuyển người gán")

    # Ghi lại danh sách tên lớp và giữ các mục khác trong YAML.
    if rename_classes:
        path = ds.yaml_path
        data = (
            yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if path.exists()
            else {}
        )
        old_names = data.get("names")
        new_names = list(cfg["classes"])

        if old_names != new_names:
            data["names"] = new_names
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            log("data.yaml", None, "rename_classes", str(old_names), str(new_names))

    # Duyệt từng file một lần để số dòng luôn khớp với issues.
    for stem, actions in sorted(line_actions.items()):
        if stem in images_to_remove:
            continue

        path = ds.label_path(stem)
        if not path.is_file():
            continue

        original = path.read_text(encoding="utf-8", errors="replace")
        updated = []

        for line_number, raw_line in enumerate(original.splitlines(keepends=True), 1):
            action = actions.get(line_number)
            before = raw_line.rstrip("\r\n")

            if action == "drop_line":
                log(stem, line_number, "drop_line", before, "")
                continue

            if action != "clip_box":
                updated.append(raw_line)
                continue

            try:
                class_id, cx, cy, width, height = parse_yolo_line(before)
            except (ValueError, OverflowError):
                updated.append(raw_line)
                continue

            left = cx - width / 2
            top = cy - height / 2
            right = cx + width / 2
            bottom = cy + height / 2

            clipped = (
                max(0.0, left),
                max(0.0, top),
                min(1.0, right),
                min(1.0, bottom),
            )
            if clipped == (left, top, right, bottom):
                updated.append(raw_line)
                continue

            left, top, right, bottom = clipped
            if right <= left or bottom <= top:
                log(stem, line_number, "drop_line", before, "")
                continue

            new_cx = (left + right) / 2
            new_cy = (top + bottom) / 2
            new_width = right - left
            new_height = bottom - top
            after = (
                f"{class_id} {new_cx:.16g} {new_cy:.16g} "
                f"{new_width:.16g} {new_height:.16g}"
            )
            updated.append(after + raw_line[len(before):])
            log(stem, line_number, "clip_box", before, after)

        new_text = "".join(updated)
        if new_text != original:
            path.write_text(new_text, encoding="utf-8")

    return fixes