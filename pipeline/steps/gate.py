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
    """Quyết định Release / Hold / Rework. Lỗi bắt buộc luôn thắng, kể cả ở ảnh người đã duyệt."""
    thr = cfg["gate"]["warn_ratio_hold"]
    stems, reviewed = set(image_stems), set(reviewed)
    n_images = len(stems)
    n_errors = sum(1 for i in issues if i.severity == ERROR)        # không bao giờ bỏ qua, không lọc theo ảnh
    warn_images = {i.image for i in issues                         # đếm ẢNH, không đếm dòng issue
                   if i.severity == WARN and i.image in stems and i.image not in reviewed}
    n_warn = len(warn_images)
    warn_ratio = round(n_warn / n_images, 4) if n_images else 0     # dataset rỗng: không chia cho 0
    reasons = []
    if n_errors:
        decision = "Rework"
        reasons.append(f"còn {n_errors} lỗi bắt buộc -> trả lại bước sửa, KHÔNG xuất dataset")
    elif warn_ratio >= thr:
        decision = "Hold"
        reasons.append(f"{n_warn}/{n_images} ảnh ({warn_ratio:.1%}) còn cảnh báo chưa qua mắt người "
                       f">= ngưỡng {thr:.0%}")
    else:
        decision = "Release"
        reasons.append(f"hết lỗi bắt buộc; {n_warn}/{n_images} ảnh ({warn_ratio:.1%}) còn cảnh báo "
                       f"< ngưỡng {thr:.0%}")
    reasons.append(f"người đã duyệt {len(reviewed & stems)} ảnh; mẫu số là {n_images} ảnh trong dataset")
    return dict(decision=decision, n_errors=n_errors, n_warn_images=n_warn,
                n_images=n_images, warn_ratio=warn_ratio, reasons=reasons)
