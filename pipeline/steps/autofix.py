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


REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}


def _clip_line(text):
    """Cắt box về trong [0,1], giữ nguyên lớp. Trả dòng mới, hoặc None nếu box không còn diện tích."""
    cid, cx, cy, w, h = parse_yolo_line(text)
    x1, y1 = max(0.0, cx - w / 2), max(0.0, cy - h / 2)
    x2, y2 = min(1.0, cx + w / 2), min(1.0, cy + h / 2)
    if x2 - x1 <= 0 or y2 - y1 <= 0:                 # box nằm hẳn ngoài ảnh: xoá chứ không ghi box rỗng
        return None
    return f"{cid} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def fix(ds, issues, cfg):
    """Sửa các lỗi bắt buộc máy sửa được AN TOÀN, ngay trong ds, và trả về mọi thay đổi (03_fixes.csv)."""
    errs = [i for i in issues if i.severity == ERROR]      # cảnh báo là việc của người, không sửa
    fixes = []

    # 1) Xoá ảnh (trùng / rò rỉ test / hỏng / quá nhỏ). Làm TRƯỚC để lỗi dòng của ảnh đó bỏ qua êm.
    removed = set()
    for stem in sorted({i.image for i in errs if i.code in REMOVE_CODES}):
        ip, lp = ds.image_path(stem), ds.label_path(stem)
        before = ip.name if ip else "(không còn ảnh)"
        if lp.exists():
            before += " + nhãn"
            lp.unlink()
        if ip:
            ip.unlink()
        removed.add(stem)
        fixes.append(dict(image=stem, line="", action="remove_image", before=before, after="(đã loại khỏi lô)"))

    # 2) data.yaml: ghi lại names đúng danh sách lớp của dự án (một lần, dù có nhiều dòng lỗi)
    if any(i.code == "BAD_CLASS_NAME" for i in errs):
        old = ", ".join(f"{i}:{n}" for i, n in sorted(ds.yaml_names().items())) or "(không đọc được)"
        d = (yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else None) or {}
        d["names"] = dict(enumerate(cfg["classes"]))
        ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(dict(image="data.yaml", line="", action="rename_classes", before=old,
                          after=", ".join(f"{i}:{n}" for i, n in enumerate(cfg["classes"]))))

    # 3) Ảnh chưa có file nhãn: máy KHÔNG bịa nhãn, cũng không tạo file rỗng (rỗng = "ảnh nền").
    #    Chỉ ghi một dòng fix để review_queue đẩy ảnh lên đầu hàng đợi người gán.
    for stem in sorted({i.image for i in errs if i.code == "MISSING_LABEL_FILE"} - removed):
        fixes.append(dict(image=stem, line="", action="needs_label",
                          before="(không có file)", after="chuyển người gán"))

    # 4) Lỗi theo dòng: GOM THEO FILE rồi ghi lại MỘT lần, vì issue.line là số dòng GỐC.
    by_file = defaultdict(lambda: (set(), set()))
    for i in errs:
        if i.line is None or i.image in removed:
            continue
        drop, clip = by_file[i.image]
        if i.code in DROP_CODES:
            drop.add(i.line)
        elif i.code == "BOX_OUT_OF_IMAGE":
            clip.add(i.line)

    for stem in sorted(by_file):
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        drop, clip = by_file[stem]
        clip = clip - drop                               # một dòng vừa tràn vừa lặp: xoá thắng cắt
        out, rows, changed = [], [], False
        for n, text in enumerate(lp.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if n in drop:
                rows.append(dict(image=stem, line=n, action="drop_line", before=text.strip(), after=""))
                changed = True
                continue
            if n in clip:
                try:
                    new = _clip_line(text)
                except ValueError:                       # dòng không parse được: để yên, không ghi fix
                    out.append(text)
                    continue
                if new is None:
                    rows.append(dict(image=stem, line=n, action="drop_line", before=text.strip(),
                                     after="(cắt xong không còn diện tích)"))
                else:
                    out.append(new)
                    rows.append(dict(image=stem, line=n, action="clip_box", before=text.strip(), after=new))
                changed = True
                continue
            out.append(text)                             # dòng không bị cờ (kể cả dòng trống) giữ nguyên
        if changed:
            lp.write_text("".join(l + "\n" for l in out), encoding="utf-8")
            fixes.extend(rows)
    return fixes
