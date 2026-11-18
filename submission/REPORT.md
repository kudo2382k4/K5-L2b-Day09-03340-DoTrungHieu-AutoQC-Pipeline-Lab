# Báo cáo Day 09 — Đỗ Trung Hiếu, 2A202603340

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát 10). Lô raw có **224 ảnh** vào; bước 1 loại **22** ảnh, còn **202 ảnh** đi qua QC và được xuất thành **bản nháp** `submission/export/clean_v1` (202 ảnh, CHƯA phát hành).
Lý do: sau sửa tự động và người duyệt **không còn lỗi bắt buộc nào** (0 ERROR), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa được người xem, vượt ngưỡng Hold 10%. Hàng đợi duyệt có **125 ảnh**, trong khi ngân sách chỉ **80 ảnh**.

## 2. Lỗi và phân việc
Số liệu lấy từ `02_error_list_v1` (gồm cả ảnh bị loại ở `01_intake`), 211 dòng.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | máy (loại ở bước 1) | trùng từng byte: chắc chắn, giữ 1 bản |
| `LEAK_TEST` | 5 ảnh | máy (loại ở bước 1) | trùng ảnh test/val: để lại sẽ thổi phồng điểm đánh giá |
| `DUP_IMAGE_NEAR` | 4 ảnh | máy (loại ở bước 1) | gần trùng (phash ≤ 12), đã mở xem cả 4 cặp đều trùng thật |
| `BAD_SIZE` / `CORRUPT_IMAGE` | 3 / 2 ảnh | máy (loại ở bước 1) | ảnh quá nhỏ / không mở được, không thể gán nhãn |
| `BOX_OUT_OF_IMAGE` | 8 dòng | máy (`clip_box` ×8) | cắt về [0,1] là an toàn, giữ nguyên lớp |
| `DUP_BOX` / `BAD_CLASS_ID` / `BOX_ZERO` / `BAD_FORMAT` | 7 / 6 / 4 / 3 dòng | máy (`drop_line` ×20) | dòng vô nghĩa hoặc lặp, không đoán được ý định nên xoá |
| `BAD_CLASS_NAME` | 1 file (2 dòng lỗi) | máy (`rename_classes`) | `names` trong data.yaml phải đúng danh sách dự án |
| `MISSING_LABEL_FILE` | 6 ảnh | **người** (`needs_label`) | máy không được bịa nhãn; nhãn rỗng nghĩa là "ảnh nền", khác "chưa gán" |
| `POSSIBLE_MISSING` | 53 lỗi / 52 ảnh | **người** | yolo26l thấy vật mà nhãn không có box; model cũng có thể sai |
| `POSSIBLE_FALSE_POS` | 29 dòng / 27 ảnh | **người** | box nhãn không khớp vật nào model thấy |
| `POSSIBLE_LOOSE_BOX` | 28 lỗi / 24 ảnh | **người** | đúng vật, đúng lớp nhưng box lệch/lỏng |
| `POSSIBLE_WRONG_CLASS` | 18 ảnh | **người** | model nói lớp khác với IoU ≥ 0,5 |
| `EMPTY_LABEL` | 12 ảnh (15 sau sửa) | **người** | file rỗng: ảnh nền hay thiếu nhãn? Sau `drop_line` thêm 3 file thành rỗng |
| `BOX_TINY` / `BOX_HUGE` | 6 dòng (4 ảnh) / 3 ảnh | **người** | quy tắc guideline, chỉ cảnh báo |
| `CLASS_RARE` | 4 lỗi (cấp dataset) | **người** | lớp ít box (truck 41, bus 32 so với person 574 box) |

Tổng: autofix làm **35 thay đổi** (`03_fixes.csv`): 20 `drop_line`, 8 `clip_box`, 6 `needs_label`, 1 `rename_classes`. Sau sửa (`04_error_list_v2`) chỉ còn 6 ERROR, đều là `MISSING_LABEL_FILE`.

**Thứ tự hàng đợi** (`05_review_queue.csv`): điểm ưu tiên = Σ trọng số mã lỗi × (1 + conf của model). Trọng số: `NEEDS_LABEL` 10, `WRONG_CLASS` 3, `MISSING`/`FALSE_POS`/`FIXED_DROP_LINE` 2, `LOOSE_BOX` 1,5… Vì vậy đứng đầu là `img_0020` (11,52: vừa bị xoá dòng, vừa có `POSSIBLE_MISSING` và `POSSIBLE_WRONG_CLASS`), tiếp theo là 6 ảnh chưa có nhãn (10,0). Ảnh càng nhiều loại lỗi nặng và model càng chắc thì càng lên trước.
**Với ngân sách 80 ảnh**: hàng đợi có 123 lỗi ngữ nghĩa (`POSSIBLE_*`) trên 103 ảnh; người duyệt xem 80 ảnh đầu, phủ **94/123 lỗi ngữ nghĩa (74 ảnh)** cộng 6 ảnh chưa có nhãn. Ảnh thứ 80 có điểm 3,343, ảnh 81 là 3,333: ranh giới rất sát, 45 ảnh còn lại không ai xem.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | `DUP_IMAGE_NEAR`: 1,00 / 0,50 → **1,00 / 0,67** (`EXACT` giữ 1,00 / 1,00) | Lỗi này **tự xoá ảnh**, nên ưu tiên precision. Trên raw, 10–14 bắt được cặp gần trùng ở dist 6 và 10 mà không xoá nhầm ảnh nào; chọn 12 ở giữa vùng an toàn |
| `second_opinion.conf` | 0.25 | **0.6** | `MISSING` 0,50 / 1,00 → **0,57 / 1,00**; `WRONG_CLASS` 0,56 / 0,83 → **0,62 / 0,83**; `LOOSE_BOX` 0,29 / 0,40 → 0,20 / 0,20 | Mức conf cao nhất mà recall `MISSING` vẫn 1,00. Hàng đợi raw giảm 145 → 125 ảnh. conf 0,8 cho Release (7,8%) nhưng recall `MISSING` tụt còn 0,75: đổi bỏ sót lấy hàng đợi gọn là "Release giả", nên không chọn |

**Chỗ calibration có thể đánh lừa:** nhìn bảng sweep, `phash_dist = 16` trông tốt nhất (P = **1,00**, R = **0,83**, cao hơn mọi giá trị khác). Nhưng chạy trên raw, số ảnh bị loại ở bước 1 tăng từ 22 lên **31**, và khi mở xem các cặp ở dist 16 thì có **2 cặp hoàn toàn khác nhau**: `img_0011` (tennis) bị coi là trùng `img_0008` (trượt tuyết), `img_0177` (lướt sóng) bị coi là trùng `img_0113` (người ngồi bàn). Calib chỉ có 6 ca gần trùng và không có cặp ảnh "khác nhưng phash gần" nào, nên precision 1,00 trên calib không nói gì về FP trên raw. Ngoài ra `phash_dist = 20` làm recall `EXACT` tụt còn 0,33 (ảnh bị gom sai nhóm), một dấu hiệu nữa cho thấy ngưỡng lớn không an toàn.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt): vòng 3 còn **6 lỗi `MISSING_LABEL_FILE`** (img_0031, img_0053, img_0126, img_0135, img_0170, img_0219), kết luận **REWORK — còn 6 lỗi bắt buộc**, **mã thoát 20**, log in "KHÔNG xuất: còn lỗi bắt buộc (Rework)" và thư mục `work/exp_nb/clean_v1` **không được tạo**. Autofix chạy lại sau duyệt cũng không "sửa" được các ảnh này, vì máy không được bịa nhãn.

**Đối chiếu với lỗi tự nhìn thấy ở Bước 1** (`viz_labels.py`):

| Ảnh | Tôi thấy | Pipeline báo |
|---|---|---|
| img_0010 | không mở được ảnh | `CORRUPT_IMAGE`, loại ở bước 1 ✅ |
| img_0050 | box người lướt sóng chỉ là một vạch dọc | `BOX_ZERO` (w = 0), autofix xoá; thêm `POSSIBLE_MISSING` (conf 0,93) đưa cho người ✅ |
| img_0001 | người lính bên phải không có box | `POSSIBLE_MISSING` (person, conf 0,95) ✅ |
| img_0020 | xe buýt gán là truck | `POSSIBLE_WRONG_CLASS` (model nói bus, IoU 0,94), đứng đầu hàng đợi ✅ |
| img_0015 | trọng tài không có box | chỉ báo `POSSIBLE_LOOSE_BOX` (IoU 0,34): box của trọng tài chồng lên box người đánh bóng nên bị hiểu là "box lỏng" chứ không phải "thiếu box" ⚠️ |

**(b) Điểm mù có bằng chứng:**
1. **Nhầm truck ↔ bus.** Trên calib, `POSSIBLE_WRONG_CLASS` bắt 5/6 lỗi chèn; ca **duy nhất bị sót là `calib_009` (truck→bus)**, còn cả 5 ca person→car đều bắt được. Hai lớp này giống nhau về hình dạng nên model lớn cũng nhầm, trong khi raw lại nghiêng về nhầm car/truck/bus (truck chỉ 41 box, bus 32 box). Recall 0,83 trên calib đánh giá cao hơn thực tế cho đúng loại lỗi hay gặp ở raw.
2. **Box lỏng vừa phải.** `POSSIBLE_LOOSE_BOX` chỉ bắt **1/5** lỗi chèn (recall 0,20); sót `calib_002`, `006`, `012`, `024` dù box đã phóng to 1,45–1,54 lần. Lý do: phóng 1,5 lần vẫn cho IoU khoảng 0,44, dễ rơi vào vùng mơ hồ. Ở v3 vẫn còn 20 ảnh `LOOSE_BOX` chưa ai xem.
3. **Ảnh trùng biến đổi mạnh.** Với `phash_dist = 12`, `DUP_IMAGE_NEAR` sót `calib_037` và `calib_038` (mức biến đổi 3 và 4). Trên raw, cặp `img_0084` / `img_0074` (cùng cô gái cầm ô, bị cắt và thu nhỏ, phash 16) **vẫn còn trong dataset**: nâng ngưỡng để bắt nó thì lại xoá nhầm 2 ảnh khác (mục 3).
4. **Ảnh đã duyệt vẫn còn cảnh báo.** 25 ảnh đã duyệt vẫn có cảnh báo ở v3 (nhãn người lệch với model, vd. `POSSIBLE_FALSE_POS`). Gate bỏ qua chúng, nên nếu người duyệt sai thì không còn lớp kiểm nào phía sau.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chạy trên Colab (T4) bằng `notebooks/day09_train_compare.ipynb`, không đổi cấu hình: **yolo26n.pt, 20 epoch, imgsz 640, batch 16, seed 0 và 1**, cùng val `data/gold_val` (40 ảnh) và cùng test `data/test` (100 ảnh, nhãn người). Chỉ khác dữ liệu train. `clean` là **bản nháp Hold** `clean_v1` (`manifest_sha1` 8966d9f…, `config_sha1` 58d1755… khớp `08_summary.json`).

Bảng từ `submission/results/comparison.md` (sinh bởi `scripts/summarize_results.py`):

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

AP50 theo lớp (trung bình 2 seed, từ `*_seed*.json`): car 0,738 → 0,738; person 0,822 → 0,823; bus 0,695 → 0,703; **truck 0,649 → 0,538** (clean seed 0/1: 0,590 / 0,486).

**Chênh lệch so với nhiễu.** mAP50 (clean − raw) = **−0,025**, bằng đúng độ lệch chuẩn giữa 2 seed của `clean` (0,025); hai seed của `clean` cách nhau 0,035 (0,718 / 0,683), lớn hơn cả chênh lệch giữa hai biến thể. Độ lệch ≈ 0 của `raw` (0,7256 / 0,7259) chỉ là trùng hợp với 2 seed, không có nghĩa `raw` ổn định hơn. mAP50-95 (−0,025) và recall (−0,024) cũng cùng cỡ nhiễu. **Kết luận: chưa kết luận được** `clean` tốt hơn hay kém hơn `raw`; với 2 seed và 100 ảnh test, khác biệt nằm trong nhiễu. Gần như toàn bộ chênh lệch đến từ **một lớp, truck**; ba lớp còn lại gần như bằng nhau.

**Thí nghiệm gần như không đo được tác dụng của làm sạch.** Theo log train, val mAP50 cao nhất của **cả 4 lần chạy đều ở epoch 1** (raw 0,801 / 0,800; clean 0,791 / 0,739), sau đó giảm (epoch 20: 0,728 / 0,705 / 0,710 / 0,617). Nên `best.pt` được đem đi test thực chất là yolo26n tiền huấn luyện COCO sau 1 epoch; dữ liệu train (raw hay clean) chưa kịp ảnh hưởng. `clean` seed 1 thấp vì đã khởi đầu kém ngay epoch 1, tức nhiễu do khởi động chứ không do dữ liệu.

**Giả thuyết và cách kiểm:**
1. **Rò rỉ test thổi phồng điểm `raw`.** Pipeline phát hiện 5 ảnh `LEAK_TEST` (img_0049, img_0101, img_0167, img_0174, img_0221 trùng test_033, test_039, test_044, test_085, test_009). `raw` được train trên chính 5 ảnh test này, `clean` thì không. *Kiểm:* tính lại mAP của cả hai mô hình trên test sau khi bỏ 5 ảnh đó; nếu khoảng cách thu hẹp thì một phần lợi thế của `raw` là do rò rỉ.
2. **AP truck rất nhiễu vì test có ít truck.** Test chỉ có 24 box truck trên 16 ảnh (so với 285 box person), nên một box đúng/sai làm AP truck dao động vài phần trăm; ngay trong `clean`, AP truck đã chênh 0,10 giữa 2 seed. *Kiểm:* chạy 5 seed và báo khoảng tin cậy riêng cho truck, hoặc dùng test lớn hơn.
3. **Nhãn car/truck/bus trong `clean` bị đổi.** Dựng lại 2 bộ train bằng `scripts/materialize_dataset.py`: `clean` có **truck 41 box** (raw 32), **car 101** (raw 122), bus 32 (raw 35). Autofix không đổi lớp, nên thay đổi này nhiều khả năng đến từ 80 ảnh được thay bằng nhãn người: ranh giới car/truck đã dịch chuyển, đúng nhóm lớp mà `second_opinion` yếu nhất (mục 4b: điểm mù truck↔bus). Nếu ranh giới car/truck trong nhãn mới không khớp với cách gán của test thì AP truck giảm. *Kiểm:* liệt kê ảnh có box truck thay đổi giữa raw và clean (`03_fixes.csv`, `06_review_log.csv`), xem bằng `viz_labels.py` và đối chiếu với guideline gán lớp.
4. **`raw` thật ra chỉ train 213 ảnh, `clean` vẫn còn lỗi.** Log Ultralytics: `raw` có `11 corrupt` (img_0010 và img_0136 hỏng; 9 ảnh có 1 dòng nhãn hỏng: id 93/7/4/−1, `nan`, thiếu cột) và `19 backgrounds` (gồm 6 ảnh chưa có file nhãn bị coi là "không có vật"), nên chỉ dùng **213/224 ảnh**, so với `clean` dùng đủ **202/202** (4 ảnh nền). Pipeline bắt đủ cả 11 ảnh này, và với 9 ảnh nhãn hỏng chỉ xoá đúng dòng lỗi thay vì bỏ cả ảnh. Khoảng cách dữ liệu thực tế chỉ là 213 so với 202, nhưng `clean` vẫn còn 38 ảnh có cảnh báo chưa duyệt (Hold). *Kiểm:* train thêm biến thể `oracle` (nhãn người) làm chặn trên.
5. **Fine-tune làm mô hình kém đi.** Như trên, `best.pt` đều là epoch 1. *Kiểm:* train lại với `freeze` backbone hoặc learning rate nhỏ hơn và so ở epoch cuối, xem khi mô hình thật sự học từ dữ liệu thì chênh lệch raw/clean có lộ ra không.

**Việc tiếp theo:** sửa thiết lập train để mô hình thật sự học từ dữ liệu (freeze backbone hoặc lr nhỏ, so ở epoch cuối); chạy 3–5 seed và bỏ 5 ảnh rò rỉ khỏi test để đo lại; train `oracle`; duyệt thêm ≥ 18 ảnh để `clean` đạt Release rồi train lại. Chỉ khi chênh lệch vượt rõ độ lệch giữa các seed mới kết luận được về tác dụng của pipeline lên mô hình.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: Hold**, không phát hành `clean_v1` (chỉ dùng làm bản nháp thử nghiệm). Để thành **Release** cần đưa tỉ lệ ảnh còn cảnh báo chưa duyệt xuống dưới 10%, tức tối đa 20/202 ảnh: người duyệt thêm **ít nhất 18 trong 38 ảnh** còn cảnh báo (ngân sách khoảng 98 ảnh thay vì 80, hoặc thêm một lượt duyệt), ưu tiên theo `05_review_queue.csv` từ hạng 81. **Không** tăng `second_opinion.conf` lên 0,8 chỉ để qua cổng, vì như vậy bỏ sót khoảng 25% box thiếu.

**(b) Ghi chú dùng AI (Claude):**
- **Prompt chính:** đưa docstring của stub + file test của từng module, yêu cầu giải thích thuật toán và các bẫy trước, rồi mới xin code mẫu; tự dán code vào file.
- **Cách kiểm:** chạy `pytest tests/test_<tên>.py` sau mỗi module (79/79 xanh), tự thử thêm ca một dòng nhiều lỗi và dòng trống ở giữa, đọc lại `common.py` để đối chiếu, chạy pipeline thật và mở xem ảnh bị cờ (`viz_labels.py`, các cặp ảnh trùng).
- **Một lần AI sai:** một AI khác review `second_opinion.py` và khẳng định phải thay bộ lọc nhãn bằng hàm ghép với `ds.valid_boxes` vì "`valid_boxes` có thể loại thêm box rỗng". Đọc `common.py` thì `valid_boxes` chỉ kiểm parse được và id lớp hợp lệ, giống hệt code đang có, nên tôi không sửa. Ngoài ra code `autofix` AI đưa lúc đầu chết với `FileNotFoundError` khi có `BAD_CLASS_NAME` mà thiếu `data.yaml`; tôi đã thêm kiểm tra file tồn tại.
