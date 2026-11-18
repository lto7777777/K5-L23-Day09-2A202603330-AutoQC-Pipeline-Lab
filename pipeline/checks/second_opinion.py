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
    """So nhãn với dự đoán của model lớn hơn. CHỈ cảnh báo: model cũng sai, ảnh bị cờ sẽ do người xem."""
    c = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    issues = []
    for p in ds.image_files():                      # thứ tự ảnh = thứ tự báo cáo, chạy lại cho cùng kết quả
        stem = p.stem
        rows = preds.get(stem)
        if rows is None:                            # chưa có dự đoán cho ảnh này: không kết luận gì
            continue
        lines = ds.read_label_lines(stem)
        if lines is None:                           # chưa có file nhãn: việc của missing_labels
            continue
        size = ds.image_size(stem)
        labels = []                                 # (số dòng GỐC, id lớp, box) của các dòng hợp lệ
        for n, text in lines:
            try:
                cid, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue                            # dòng hỏng: label_format báo, ở đây không được làm chết script
            if 0 <= cid < len(ds.classes):
                labels.append((n, cid, (cx, cy, w, h)))

        for r in rows:                              # mỗi dự đoán sinh TỐI ĐA một issue
            cid, conf, box = int(r[0]), float(r[1]), tuple(float(v) for v in r[2:6])
            if conf < c["conf"]:
                continue                            # không tin dự đoán yếu
            if size and (box[2] * size[0]) * (box[3] * size[1]) < c["min_area_px"]:
                continue                            # vật quá nhỏ: guideline không gán
            cands, same = [], []                    # nhãn MỌI lớp có IoU >= iou_missing
            for _, lcid, lb in labels:
                v = iou_xywh(box, lb)
                if v >= c["iou_missing"]:
                    cands.append(v)
                    if lcid == cid:
                        same.append(v)
            name = ds.classes[cid] if 0 <= cid < len(ds.classes) else str(cid)
            if not cands:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    f"model thấy {name} (conf {conf:.2f}) mà nhãn không có box nào ở đó",
                                    extra={"conf": round(conf, 4)}))
            elif same:
                best = max(same)
                if best < c["iou_loose"]:           # đúng vật, đúng lớp, nhưng box lệch/lỏng
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        f"box {name} lệch so với model (IoU {best:.2f} < {c['iou_loose']})",
                                        extra={"conf": round(conf, 4), "iou": round(best, 3)}))
                # IoU đủ cao: nhãn đúng lớp đã phủ vật này -> không cờ
            else:
                best_other = max(cands)             # chỉ có nhãn khác lớp chồng lên
                if best_other >= c["iou_match"]:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                        f"model nói {name} (conf {conf:.2f}) nhưng nhãn gán lớp khác "
                                        f"(IoU {best_other:.2f})",
                                        extra={"conf": round(conf, 4), "iou": round(best_other, 3)}))
                # IoU trong [iou_missing, iou_match): mơ hồ, để dành cho FALSE_POS / lần duyệt khác

        # box nhãn không khớp dự đoán nào (dùng fp_conf, KHÔNG lọc diện tích)
        fp_boxes = [tuple(float(v) for v in r[2:6]) for r in rows if float(r[1]) >= c["fp_conf"]]
        for n, lcid, lb in labels:
            best = max((iou_xywh(lb, pb) for pb in fp_boxes), default=0.0)
            if best < c["iou_missing"]:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    f"box {ds.classes[lcid]} không khớp vật nào model thấy (IoU {best:.2f})",
                                    n, {"iou": round(best, 3)}))
    return issues
