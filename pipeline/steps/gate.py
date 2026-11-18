"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    image_stems = set(image_stems)
    n_images = len(image_stems)
    hold_threshold = cfg["gate"]["warn_ratio_hold"]

    n_errors = 0
    warn_images = set()

    for issue in issues:
        if issue.severity == ERROR:
            n_errors += 1
        elif (
            issue.severity == WARN
            and issue.image in image_stems
            and issue.image not in reviewed
        ):
            warn_images.add(issue.image)

    n_warn_images = len(warn_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0

    warn_summary = (
        f"{n_warn_images}/{n_images} ảnh còn cảnh báo ({warn_ratio:.2%})"
    )

    if n_errors > 0:
        decision = "Rework"
        reasons = [f"Còn {n_errors} lỗi bắt buộc.", f"Có {warn_summary}."]
    elif warn_ratio >= hold_threshold:
        decision = "Hold"
        reasons = [
            f"Có {warn_summary}, đạt hoặc vượt ngưỡng {hold_threshold:.2%}."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Còn 0 lỗi bắt buộc và có {warn_summary}, "
            f"dưới ngưỡng {hold_threshold:.2%}."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": reasons,
    }
