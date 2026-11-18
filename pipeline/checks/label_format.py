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
    """Duyệt từng file nhãn, từng dòng. Trả list[Issue] theo thứ tự file rồi số dòng."""
    c = cfg["label_format"]
    tol, min_px, max_frac, dup_iou = c["overflow_tol"], c["min_box_px"], c["max_box_frac"], c["dup_box_iou"]
    issues = []
    for lf in ds.label_files():                       # label_files() đã sắp xếp -> chạy lại cho cùng thứ tự
        stem = lf.stem
        size = ds.image_size(stem)                    # None nếu ảnh hỏng/không có: bỏ qua check tính theo px
        seen = []                                     # (id lớp, box) của các dòng HỢP LỆ trước đó, để tìm box lặp
        for n, text in ds.read_label_lines(stem) or []:
            try:
                cid, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:                   # dòng thiếu cột / nan / id không nguyên
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"không đúng 5 cột số ({e})", n))
                continue                              # dòng đã hỏng: không kiểm hình học của nó nữa
            if not 0 <= cid < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"id lớp {cid} ngoài 0..{len(ds.classes) - 1}", n, {"class_id": cid}))
                continue
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"box rỗng: w={w}, h={h}", n))
                continue
            # mép box: trái/trên âm là tràn ra ngoài, phải/dưới lớn hơn 1 là tràn ra ngoài
            over = max(-(cx - w / 2), -(cy - h / 2), (cx + w / 2) - 1.0, (cy + h / 2) - 1.0)
            if over > tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn ảnh {over:.4f} (cho phép {tol})", n, {"overflow": round(over, 6)}))
            box = (cx, cy, w, h)
            if any(pc == cid and iou_xywh(box, pb) > dup_iou for pc, pb in seen):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                    f"lặp box của một dòng trước (cùng lớp {cid}, IoU > {dup_iou})", n))
            if size:                                  # cạnh ngắn tính bằng px, cần kích thước ảnh thật
                short = min(w * size[0], h * size[1])
                if short < min_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        f"cạnh ngắn {short:.1f}px < {min_px}px", n, {"short_px": round(short, 1)}))
            if w * h > max_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    f"box chiếm {w * h:.1%} diện tích ảnh (> {max_frac:.0%})", n, {"frac": round(w * h, 4)}))
            seen.append((cid, box))
    return issues
