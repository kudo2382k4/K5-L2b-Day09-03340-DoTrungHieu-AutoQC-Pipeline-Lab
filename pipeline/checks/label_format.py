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

import math
from collections import defaultdict

def run(ds, cfg):
    c = cfg["label_format"]
    tol, min_px = c["overflow_tol"], c["min_box_px"]
    max_frac, dup_iou = c["max_box_frac"], c["dup_box_iou"]
    n_cls = len(ds.classes)
    issues = []

    def add(sev, code, stem, msg, line, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, line=line, extra=extra))

    for lp in ds.label_files():
        stem = lp.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue
        size = ds.image_size(stem)              # 1 lần / file
        seen = defaultdict(list)                # cls -> [box] của các dòng trước

        for ln, text in lines:
            # 1. định dạng
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", stem, f"dòng sai định dạng: {e}", ln)
                continue
            if not all(map(math.isfinite, (x, y, w, h))):
                add(ERROR, "BAD_FORMAT", stem, "giá trị NaN/inf", ln)
                continue
            # 2. id lớp
            if not 0 <= cls < n_cls:
                add(ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_cls - 1}", ln)
                continue
            # 3. box rỗng
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, f"box rỗng w={w} h={h}", ln)
                continue
            box = (x, y, w, h)
            # 4. tràn ảnh
            x1, x2, y1, y2 = x - w / 2, x + w / 2, y - h / 2, y + h / 2
            over = max(-x1, x2 - 1, -y1, y2 - 1)
            if over > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {over:.4f}", ln,
                    overflow=round(over, 6))
            # 5. trùng (chỉ so trong cùng lớp)
            same = seen[cls]
            if any(iou_xywh(pb, box) > dup_iou for pb in same):
                add(ERROR, "DUP_BOX", stem, "box trùng với một dòng trước (cùng lớp)", ln)
            # 6. nhỏ (px)
            if size:
                short = min(w * size[0], h * size[1])
                if short < min_px:
                    add(WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {min_px}px", ln)
            # 7. quá to
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.2f} ảnh", ln)
            same.append(box)
    return issues