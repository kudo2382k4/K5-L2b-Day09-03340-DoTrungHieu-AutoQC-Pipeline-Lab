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
    thr = cfg["gate"]["warn_ratio_hold"]
    stems = set(image_stems)
    reviewed = set(reviewed)
    n_images = len(stems)

    # 1. Lỗi bắt buộc: đếm TẤT CẢ, không lọc theo reviewed hay image_stems
    n_errors = sum(1 for i in issues if i.severity == ERROR)

    # 2. Ảnh còn cảnh báo: thuộc dataset, chưa được duyệt; đếm theo ẢNH
    warn_images = {
        i.image for i in issues
        if i.severity == WARN and i.image in stems and i.image not in reviewed
    }
    n_warn_images = len(warn_images)

    # 3. Tỉ lệ: so sánh bằng giá trị thô, chỉ làm tròn khi trả về
    raw_ratio = n_warn_images / n_images if n_images else 0.0
    warn_ratio = round(raw_ratio, 4)

    # 4. Cây quyết định
    reasons = []
    if n_errors > 0:
        decision = "Rework"
        reasons.append(f"còn {n_errors} lỗi bắt buộc (ERROR) — phải sửa trước khi phát hành")
    elif raw_ratio >= thr:
        decision = "Hold"
        reasons.append(
            f"{n_warn_images}/{n_images} ảnh ({raw_ratio:.1%}) còn cảnh báo chưa duyệt, "
            f">= ngưỡng Hold {thr:.1%}"
        )
    else:
        decision = "Release"
        reasons.append(
            f"không còn lỗi bắt buộc; {n_warn_images}/{n_images} ảnh ({raw_ratio:.1%}) "
            f"còn cảnh báo, dưới ngưỡng {thr:.1%}"
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }