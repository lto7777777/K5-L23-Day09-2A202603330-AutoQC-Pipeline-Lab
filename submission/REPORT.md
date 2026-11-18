# Báo cáo Day 09 — Phạm Hữu Minh, 2A202603330

## 1. Kết luận trước

Pipeline kết luận **Hold** (mã thoát 10). Lô vào 224 ảnh, cửa vào loại 22 ảnh, còn **202 ảnh** được xuất ra `submission/export/clean_v1/` dưới dạng **bản nháp**, chưa phải bản phát hành.

Lý do: sau sửa tự động và một vòng người duyệt thì **không còn lỗi bắt buộc nào** (`07_error_list_v3` có 0 dòng `error`), nhưng **38/202 ảnh (18,8%)** vẫn còn cảnh báo chưa ai xem, cao hơn ngưỡng `gate.warn_ratio_hold = 10%`. Hàng đợi duyệt có 125 ảnh trong khi ngân sách chỉ 80, nên 45 ảnh không có người nhìn tới. Lô không hỏng. Nó chỉ chưa đủ mắt người nhìn qua.

## 2. Lỗi và phân việc

Số liệu lấy từ `02_error_list_v1` (211 dòng: 58 lỗi bắt buộc + 153 cảnh báo).

| Mã lỗi | Số dòng / số ảnh | Ai sửa | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 / 8 | máy (cửa vào) | md5 trùng từng byte, không cần phán đoán |
| `LEAK_TEST` | 5 / 5 | máy (cửa vào) | trùng ảnh kho test/val: để lại là rò rỉ, không thương lượng |
| `DUP_IMAGE_NEAR` | 4 / 4 | máy (cửa vào) | phash lệch ≤ 12; đã mở xem tận mắt cả 4 cặp |
| `BAD_SIZE` | 3 / 3 | máy (cửa vào) | cạnh ngắn < 250px, quy tắc số học |
| `CORRUPT_IMAGE` | 2 / 2 | máy (cửa vào) | `Image.load()` ném lỗi, chắc chắn |
| `BAD_CLASS_ID` | 6 / 6 | máy | id 93/4/−1 không có nghĩa, xoá dòng là an toàn |
| `DUP_BOX` | 7 / 7 | máy | cùng lớp, IoU > 0,9 với một dòng trước: dòng sau thừa |
| `BOX_OUT_OF_IMAGE` | 8 / 8 | máy | cắt về trong `[0,1]`, giữ nguyên lớp, không đổi ngữ nghĩa |
| `BOX_ZERO` | 4 / 4 | máy | w hoặc h ≤ 0, box không tồn tại |
| `BAD_FORMAT` | 3 / 3 | máy | thiếu cột hoặc `nan`, không đọc được thì không giữ |
| `BAD_CLASS_NAME` | 2 / 1 file | máy | ghi lại `names` trong `data.yaml` theo danh sách dự án |
| `MISSING_LABEL_FILE` | 6 / 6 | **người** | máy không được bịa nhãn; ảnh vào đầu hàng đợi |
| `POSSIBLE_MISSING` | 53 / 52 | **người** | model thấy vật mà nhãn không có: phải nhìn mới biết ai đúng |
| `POSSIBLE_LOOSE_BOX` | 28 / 24 | **người** | box lệch bao nhiêu là chấp nhận được là việc của guideline |
| `POSSIBLE_FALSE_POS` | 29 / 27 | **người** | hai phần ba số cờ này là báo động giả (precision 0,31 trên calib) |
| `POSSIBLE_WRONG_CLASS` | 18 / 18 | **người** | car/truck/bus là ranh giới ngữ nghĩa, không phải cú pháp |
| `EMPTY_LABEL` | 12 / 12 | **người** | máy không phân biệt được ảnh nền với ảnh chưa ai gán |
| `BOX_TINY` · `BOX_HUGE` · `CLASS_RARE` | 6/4 · 3/3 · 4 | **người** | ngưỡng quy ước, chỉ là dấu hiệu đáng ngó |

Máy đã thực hiện 35 thay đổi (`03_fixes.csv`): 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`. Con số khớp đúng với nhóm lỗi máy được phép sửa: 6 + 7 + 4 + 3 = 20 dòng phải xoá, và cả 8 box tràn đều cắt lại được, không box nào nằm hẳn ngoài ảnh. Sau vòng này chỉ còn 6 lỗi bắt buộc `MISSING_LABEL_FILE`, đúng loại mà máy cố tình không đụng vào.

**Hàng đợi.** `05_review_queue.csv` xếp 125 ảnh theo điểm bằng tổng trọng số cảnh báo, nhân thêm `1 + conf` của model. Vì vậy 6 ảnh `NEEDS_LABEL` (trọng số 10) nằm ngay đầu, chỉ sau `img_0020` (11,524 điểm: ảnh này vừa bị máy xoá dòng, vừa có `POSSIBLE_MISSING` lẫn `POSSIBLE_WRONG_CLASS`). Đó là thứ tự đúng: 6 ảnh kia nếu không ai gán thì cả lô phải Rework, nên chúng đáng tiền công nhất.

Với ngân sách 80 ảnh, người xem được 98/128 dòng lỗi ngữ nghĩa (`POSSIBLE_*`), trên 74/104 ảnh dính loại lỗi đó, khoảng 77%. Ranh giới ngân sách rất mong manh: ảnh thứ 80 có điểm 3,343 còn ảnh thứ 81 có điểm 3,333. Hai ảnh gần như giống nhau về mức đáng ngờ mà chỉ một ảnh được xem. 80 không phải con số vừa đủ, nó là chỗ hết giờ.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | `DUP_IMAGE_NEAR` 1,00 / 0,50 → **1,00 / 0,67**; `DUP_IMAGE_EXACT` giữ 1,00 / 1,00 | Đây là ngưỡng xoá ảnh: sai một lần là mất ảnh tốt không lấy lại được, nên ưu tiên precision tuyệt đối. Trên calib mọi giá trị 4–14 cho cùng P/R, nên tôi chọn 12 bằng bằng chứng từ lô raw chứ không bằng F1 (xem dưới). |
| `second_opinion.conf` | 0.25 | **0.6** | `POSSIBLE_MISSING` 0,50 / 1,00 → **0,57 / 1,00**; `WRONG_CLASS` 0,56 / 0,83 → **0,62 / 0,83**; `LOOSE_BOX` 0,29 / 0,40 → 0,20 / 0,20 | 0,6 là giá trị lớn nhất còn giữ recall 1,00 cho `POSSIBLE_MISSING` (8/8 lỗi chèn), và là mức precision tốt nhất tại recall đó. Lên 0,7 recall tụt còn 0,88, lên 0,8 còn 0,75: đổi 2 lỗi lọt lấy vài phần trăm precision là lỗ. Xuống dưới 0,6 không thêm recall nào cho `MISSING` (đã 1,00), chỉ thêm báo động giả. |

Giá phải trả của 0,6 là `POSSIBLE_LOOSE_BOX`: recall rơi từ 0,40 xuống 0,20, tức 1/5 lỗi chèn. Tôi chấp nhận, vì box lỏng là lỗi nhẹ nhất trong bốn loại (vật vẫn có box, chỉ lệch) và mang trọng số duyệt thấp nhất (1,5 so với 3 và 2), trong khi mỗi báo động giả thêm vào lại ăn mất một suất trong ngân sách 80 ảnh.

**Chỗ calibration đánh lừa tôi, kèm bằng chứng.** Bảng sweep nói `phash_dist = 16` là tốt nhất: `DUP_IMAGE_NEAR` recall 0,83 mà precision vẫn **1,00**; thậm chí `phash_dist = 20` cũng precision 1,00. Cả hai con số đều vô nghĩa, vì hai lý do bảng không thể hiện.

1. Bảng mù với `LEAK_TEST`: `MANIFEST.csv` không có dòng `LEAK_TEST` nào (bộ calib dựng ra vốn không có ca rò rỉ), nên mọi cờ `LEAK_TEST` sai đều không rơi vào cột FP của bất kỳ mã nào. Tôi đếm thử trên chính 39 ảnh calib: dist 16 sinh 1 cờ `LEAK_TEST`, dist 20 sinh 22 cờ trên 39 ảnh. Vì `LEAK_TEST` được ưu tiên hơn `DUP_IMAGE_EXACT`, chính nó kéo recall `EXACT` từ 1,00 xuống 0,33 ở dist 20. Bảng hiện ra như bỏ sót, thực chất là công cụ đang quăng hơn nửa bộ calib đi mà không bị trừ một điểm precision nào.
2. Mở ảnh ra xem thì dist 16 xoá nhầm. Trên lô raw, tăng từ 14 lên 16 làm xuất hiện 3 cặp trùng mới và 6 ảnh bị coi là rò rỉ test. Tôi dựng ảnh ghép và xem từng cặp: 6/6 khớp `LEAK_TEST` là ảnh hoàn toàn khác nhau (`img_0013` là bàn làm việc đầy máy tính, bị ghép với một ảnh sân bóng chày trong kho test), và 2/3 cặp trùng gần đúng cũng khác hẳn: `img_0011` (tay vợt tennis) bị ghép với `img_0008` (hai người trượt tuyết), `img_0177` (người lướt sóng) bị ghép với `img_0113` (người đàn ông ngồi bàn ăn). Nếu tin bảng, pipeline sẽ xoá vĩnh viễn 8 ảnh tốt.

Bốn cặp mà dist 12 bắt được thì ngược lại, đều là trùng thật: `img_0076`~`img_0042` và `img_0143`~`img_0037` lệch phash 0 (cùng một ảnh, lưu lại nên md5 khác), `img_0223`~`img_0077` lệch 6 (cùng cảnh nhà thờ, đổi độ sáng), `img_0186`~`img_0061` lệch 10 (cùng cái ghế đá, cắt nhẹ). Khoảng trống giữa cặp thật xa nhất (10) và cặp sai đầu tiên (16) là vùng an toàn, nên tôi đặt ngưỡng vào giữa: **12**. Số ảnh bị loại ở cửa vào là 22/224, khoảng 10%, hợp lý với một lô cố tình chèn ảnh trùng.

Hạn chế phải nhớ: calib chỉ có 39 ảnh, mỗi mã chỉ 2–8 lỗi chèn nên precision và recall nhảy từng bước 12–50%. `docs/CALIBRATION.md` cũng nói rõ lỗi `WRONG_CLASS` trong calib chủ yếu là person→car, còn raw nghiêng về car/truck/bus. Recall 0,83 đo trên calib không được đọc thành recall 0,83 trên raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

**(a) Cửa chặn chặn thật.** Chạy lại đúng lô đó nhưng bỏ bước người duyệt:

```
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```

Kết quả: `kết luận: REWORK — còn 6 lỗi bắt buộc -> trả lại bước sửa, KHÔNG xuất dataset`, **mã thoát 20**, và thư mục `work/exp_nb/clean_v1` không hề được tạo ra. Sáu lỗi còn lại là `MISSING_LABEL_FILE` ở `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`, đúng sáu ảnh mà máy từ chối bịa nhãn. Trong lần chạy chính thức, chính sáu ảnh này nằm đầu hàng đợi và được người gán, nhờ vậy lô mới thoát khỏi Rework. Cùng lúc đó `data/raw/` không bị đụng tới: tôi băm sha1 toàn bộ thư mục trước và sau khi chạy, hai giá trị trùng nhau (`ea1a237a…`).

Mã thoát 0/10/20 là để CI tự quyết mà không cần người đọc log: 0 thì cho merge và đẩy dataset đi, 10 thì dừng lại chờ duyệt nốt hàng đợi, 20 thì fail build vì có lỗi phải sửa chứ không phải chờ.

**(b) Ba chỗ pipeline không bắt được, đều có bằng chứng.**

1. Ảnh trùng bị biến đổi mạnh thì lọt, và tôi để vậy có chủ ý. Cặp `img_0084`~`img_0074` đúng là trùng thật (cùng cảnh đám đông và cái ô, một bản bị cắt) nhưng phash lệch 16, nằm ngoài ngưỡng 12 của tôi. Tôi cố tình để nó lọt: muốn bắt nó thì phải nâng lên 16, mà cái giá là 8 ảnh tốt bị xoá nhầm như đã đo ở mục 3. Một ảnh trùng lọt vào train chỉ làm lệch nhẹ phân bố, còn xoá nhầm 8 ảnh là mất dữ liệu thật.
2. Box lỏng vừa phải thì không ai báo. Ở `conf = 0,6`, `POSSIBLE_LOOSE_BOX` chỉ bắt 1/5 lỗi chèn trên calib (recall 0,20). Ngưỡng `iou_loose = 0,5` là cố định, nên một box bị phình khoảng 1,2–1,5 lần vẫn có IoU trên 0,5 với dự đoán của model và đi thẳng vào dataset.
3. Gán nhầm lớp mà model lớn cũng nhầm thì vô hình. `POSSIBLE_WRONG_CLASS` đã bỏ sót 1/6 lỗi chèn ngay trên calib, và cơ chế của nó là so với yolo26l: nếu model cũng gọi chiếc xe tải đó là bus thì không cờ nào bật. Lô raw lệch hẳn về nhóm xe (`class_stats.csv`: car 101, person 574, truck 41, bus 32), đúng vùng mà cả người lẫn model hay nhầm, nên con số thật nhiều khả năng xấu hơn 0,83.

Một điều nữa đáng ghi: máy sửa xong lại đẻ ra việc cho người. Sau bước `clip_box`, `BOX_TINY` tăng từ 6 lên 7 dòng và `EMPTY_LABEL` tăng từ 12 lên 15 ảnh. Cắt một box tràn có thể làm nó nhỏ hơn ngưỡng, còn xoá hết dòng hỏng của một file thì để lại file nhãn rỗng, mà rỗng thì máy không phân biệt được ảnh nền với ảnh chưa gán.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

**Chưa chạy.** Phần train cần GPU và chạy trên Colab; trong buổi làm bài này tôi không chạy notebook nên không có `submission/results/`. Tôi không điền số nào cho mục này thay vì đoán: một bảng mAP không có file JSON do `scripts/train_compare.py` sinh ra thì không ai kiểm chứng được. Phần lõi được kiểm bằng `make check-core`.

Nếu chạy sau, có một điều cần cẩn thận đã thấy trước từ số liệu hiện có. Bản `clean` hơn `raw` ở chỗ đã loại 22 ảnh, trong đó **5 ảnh rò rỉ từ chính tập test**, và sửa 35 chỗ; nhưng 45 ảnh trong hàng đợi vẫn mang nhãn máy chưa ai duyệt. Vì vậy chênh lệch mAP nếu có nhiều khả năng đến từ việc bỏ 5 ảnh rò rỉ (chính 5 ảnh đó làm `raw` trông tốt hơn một cách giả tạo khi đo trên test) chứ không phải từ chất lượng nhãn. Với tập test chỉ 100 ảnh, chênh lệch nhỏ hơn độ lệch giữa các seed là chuyện bình thường, và khi đó kết luận đúng là chưa kết luận được.

## 6. Quyết định và ghi chú AI

**Quyết định cuối: Hold.** Tôi giữ nguyên kết luận của pipeline thay vì chỉnh ngưỡng cho ra Release. Thử nghiệm cho thấy chỉ cần nâng `second_opinion.conf` lên 0,8 là lô này thành Release ngay, tỉ lệ cảnh báo rơi từ 18,8% xuống 7,9%. Nhưng đó là Release giả: đổi lại, recall của `POSSIBLE_MISSING` trên calib tụt từ 1,00 xuống 0,75, tức công cụ mù bớt đi chứ lô không sạch hơn chút nào.

Để thành Release cần đúng một việc: duyệt nốt 45 ảnh còn lại trong hàng đợi rồi chạy lại. Khi đó mọi ảnh có cảnh báo đều đã qua mắt người và tỉ lệ cảnh báo chưa duyệt về 0. Điều kiện đổi quyết định theo chiều ngược lại cũng rõ: nếu vòng duyệt tiếp theo làm lộ ra lỗi bắt buộc mới, chẳng hạn người gán thiếu cột hoặc sai id lớp, gate sẽ tự chuyển sang Rework. Tôi đã kiểm điều đó bằng lần chạy `--budget 0` ở mục 4.

**Ghi chú dùng AI** (có dùng, theo `RULES.md` và `docs/PROMPTING.md`):

- *Prompt chính:* dán nguyên docstring của từng module kèm file test tương ứng, cộng 4 ý bắt buộc. (1) Đầu vào là `Dataset` kiểu YOLO gồm `images/`, `labels/`, `data.yaml`; (2) quy tắc kiểm là đúng bảng mã lỗi trong docstring, mọi ngưỡng đọc từ `cfg`, không viết cứng số; (3) đầu ra là `list[Issue]` với `Issue.line` là số dòng gốc của file nhãn; (4) giới hạn an toàn: chỉ `autofix` được ghi file và chỉ ghi trong `ds`, không đụng `data/raw/`, không đọc `MANIFEST.csv`, `review_reference/` hay `data/test/`.
- *Cách tôi kiểm:* đọc lại từng dòng và soát riêng hai chỗ dễ sai nhất là nơi ghi/xoá file và nơi lấy ngưỡng (tất cả đều từ `cfg`); chạy `pytest` với 79 test xanh; tự viết thêm 10 ca ngoài bộ test như `GUIDE.md` dặn (một dòng mang 2 lỗi cùng lúc, dòng trống và dòng chỉ có khoảng trắng ở giữa file, một ảnh có 6 dự đoán, một ảnh không có dự đoán nào); cuối cùng đối chiếu trên bộ `calib` có đáp án.
- *Một lần AI sai:* khi hỏi kết quả cắt box `1 0.97 0.5 0.2 0.3`, AI trả lời tâm mới là 0,95. Chạy thật ra **0,935** (mép trái 0,87, mép phải cắt về 1,0). Nó sai vì nhẩm theo một ví dụ khác trong bộ test chứ không tính lại. Tôi bắt được là nhờ tự viết ca kiểm rồi so với kết quả chạy thay vì tin con số AI đọc ra. Đó cũng là lý do mục 3 chọn ngưỡng bằng cách mở ảnh ra xem chứ không bằng bảng F1.

Phần thưởng CVAT (+2) tôi không làm trong buổi này.
