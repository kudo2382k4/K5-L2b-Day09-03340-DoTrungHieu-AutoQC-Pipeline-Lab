# Phân tích train: raw vs clean

Cấu hình: yolo26n.pt, 20 epoch, imgsz 640, batch 16, seed 0 và 1, Colab T4. Cùng val `data/gold_val` (40 ảnh), cùng test `data/test` (100 ảnh, nhãn người). Chỉ khác dữ liệu train. `clean` = bản nháp **Hold** `submission/export/clean_v1` (202 ảnh).

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 202 | 2 | 0.701 ± 0.025 | 0.487 ± 0.008 | 0.759 ± 0.003 | 0.625 ± 0.019 |

## 1. Chênh mAP50 so với độ lệch giữa các seed
mAP50 (clean − raw) = **−0,025**, bằng đúng độ lệch chuẩn giữa 2 seed của `clean` (0,025). Hai seed của `clean` cách nhau 0,035 (0,718 / 0,683), lớn hơn cả chênh lệch giữa hai biến thể. Độ lệch ≈ 0 của `raw` (0,7256 / 0,7259) là trùng hợp khi chỉ có 2 seed.
**Kết luận được đến đâu:** với 2 seed và 100 ảnh test, khác biệt **nằm trong nhiễu**, nên chưa kết luận được `clean` tốt hơn hay kém hơn `raw`. Muốn kết luận cần ít nhất 3–5 seed và báo khoảng tin cậy.

**Phát hiện quan trọng từ log train: cả 4 `best.pt` đều là trọng số sau epoch 1.** Ultralytics chọn `best.pt` theo mAP trên val, và val mAP50 cao nhất của mọi lần chạy đều rơi vào **epoch 1**, rồi giảm dần khi train tiếp:

| Lần chạy | val mAP50 epoch 1 | val mAP50 epoch 20 | val mAP50 của `best.pt` |
|---|---:|---:|---:|
| raw seed 0 | 0,801 | 0,728 | 0,803 |
| raw seed 1 | 0,800 | 0,705 | 0,801 |
| clean seed 0 | 0,791 | 0,710 | 0,793 |
| clean seed 1 | 0,739 | 0,617 | 0,740 |

Như vậy điểm test đo gần như **yolo26n tiền huấn luyện COCO sau 1 epoch**, chứ không phải mô hình đã học từ dữ liệu train. Với khoảng 200 ảnh, fine-tune 20 epoch làm val giảm (quá khớp hoặc quên kiến thức COCO), nên chất lượng nhãn train gần như không có cơ hội thể hiện. Điều này cũng giải thích `clean` seed 1 thấp (test 0,683): ngay sau epoch 1, val của nó đã chỉ 0,739 so với 0,79–0,80 ở các lần khác, tức nhiễu đến từ bước khởi động chứ không phải từ dữ liệu. **Thí nghiệm hiện tại không đủ nhạy để đo tác dụng của làm sạch.** *Cách sửa:* giảm learning rate hoặc đóng băng backbone (`freeze`), train lâu hơn với nhiều dữ liệu hơn, hoặc so mô hình ở epoch cuối thay vì `best.pt`.

## 2. `raw` thật sự train trên bao nhiêu ảnh?
`train_images` ghi 224, nhưng log Ultralytics ở ô 6 cho thấy: `216 images, 19 backgrounds, 11 corrupt` và **`Using 213 train`**. Vậy `raw` thực sự chỉ train trên **213/224 ảnh**; `clean` dùng đủ **202/202** (`4 backgrounds, 0 corrupt`). 11 ảnh bị Ultralytics bỏ (giống hệt ở cả 2 seed):

| Lý do bị bỏ (log Ultralytics) | Số ảnh | Ảnh | Pipeline xử lý thế nào |
|---|---:|---|---|
| `cannot identify image file` | 1 | img_0010 | `CORRUPT_IMAGE`, loại ở bước 1 |
| `image file is truncated` | 1 | img_0136 | `CORRUPT_IMAGE`, loại ở bước 1 |
| `Label class 93/7/4 exceeds dataset class count` | 4 | img_0020, img_0104, img_0194, img_0199 | `BAD_CLASS_ID`: chỉ xoá dòng hỏng, giữ ảnh và các box còn lại |
| `negative label values [-1.]` | 2 | img_0099, img_0117 | `BAD_CLASS_ID` (id −1): xoá dòng |
| `non-normalized or out of bounds coordinates []` | 2 | img_0014, img_0022 | `BAD_FORMAT` (dòng chứa `nan`): xoá dòng |
| `inhomogeneous shape` (dòng thiếu cột) | 1 | img_0179 | `BAD_FORMAT`: xoá dòng |

Điểm đáng chú ý:
- Ultralytics **bỏ cả ảnh** chỉ vì **1 dòng** hỏng, nên 9 ảnh có nhãn hỏng mất luôn mọi box đúng khác. Pipeline chỉ xoá hoặc cắt đúng dòng lỗi, nên giữ lại được các ảnh này (ví dụ img_0020 vẫn còn trong `clean` với nhãn đã sửa).
- `raw` có **19 ảnh nền** so với 4 ở `clean`. Trong đó có **6 ảnh không có file nhãn** (img_0031, 0053, 0126, 0135, 0170, 0219) mà Ultralytics coi là "không có vật nào", dù thật ra chỉ là chưa gán, cùng các file nhãn rỗng. Mô hình `raw` bị dạy sai trên các ảnh đó. Pipeline tránh được việc này: không tạo file nhãn rỗng và đẩy 6 ảnh chưa có nhãn sang người gán.
- Tôi từng ước lượng 214/224 bằng cách mô phỏng quy tắc kiểm của Ultralytics trên máy. Bản ước lượng sót img_0014, img_0022 (dòng chứa `nan`, mà `nan > 1` và `nan < 0` đều sai nên lọt qua phép so sánh của tôi) và img_0136 (ảnh bị cắt cụt vẫn qua được `PIL.verify()`), đồng thời đếm nhầm 2 ảnh khác. Pipeline thì bắt đủ cả 11 ảnh. Log thật là căn cứ đúng.

## 3. `raw` có ảnh trùng với tập test không?
**Có.** Pipeline phát hiện 5 ảnh `LEAK_TEST` (`01_intake.csv`): img_0049 = test_033, img_0101 = test_039, img_0167 = test_044, img_0174 = test_085, img_0221 = test_009. `raw` được train trên đúng 5 ảnh test này, `clean` thì không, nên điểm của `raw` có thể bị thổi phồng. Ngoài ra `raw` còn 8 ảnh trùng byte và 4 ảnh gần trùng, làm các ảnh đó có trọng số gấp đôi.
**Thổi phồng bao nhiêu:** chưa đo được bằng số liệu hiện có. **Cách kiểm:** đánh giá lại `best.pt` của cả hai biến thể trên test **bỏ 5 ảnh** test_009, test_033, test_039, test_044, test_085 (95 ảnh). Nếu khoảng cách raw − clean thu hẹp hoặc đảo chiều thì phần chênh lệch là do rò rỉ. Có thể so thêm AP của `raw` trên riêng 5 ảnh đó với 95 ảnh còn lại.

## 4. Lớp nào được lợi nhất?
AP50 trung bình 2 seed (raw → clean): car 0,738 → 0,738; person 0,822 → 0,823; **bus 0,695 → 0,703 (+0,008, lợi nhất nhưng trong nhiễu)**; **truck 0,649 → 0,538 (−0,111, bị hại)**.
- **person** là lớp có nhiều lỗi nhất trong `02_error_list_v1`: 41/53 `POSSIBLE_MISSING` và 12/18 `POSSIBLE_WRONG_CLASS` là person. Clean có 574 box person so với 537 ở raw (+37 box bổ sung qua người duyệt). Nhưng person đã có hơn 500 box và AP sẵn ở mức 0,82, nên thêm khoảng 7% box gần như không đổi được AP.
- **truck/bus** gần như không bị `second_opinion` cờ (1 `MISSING` truck, 1 `WRONG_CLASS` truck, 1 bus), vậy mà số box vẫn đổi: truck 32 → 41, car 122 → 101, bus 35 → 32. Autofix không đổi lớp, nên thay đổi đến từ 80 ảnh được thay bằng nhãn người: ranh giới car/truck dịch chuyển. Đúng nhóm này là điểm mù của pipeline (REPORT §4b: `WRONG_CLASS` sót ca truck→bus trên calib).
- AP truck rất nhiễu: test chỉ có 24 box truck trên 16 ảnh, và ngay trong `clean` AP truck đã chênh 0,10 giữa 2 seed (0,590 / 0,486).

## 5. `clean` còn lỗi gì? Đã là chặn trên chưa?
**Chưa.** `clean_v1` là bản nháp **Hold**: hàng đợi duyệt có 125 ảnh nhưng ngân sách chỉ 80, nên **38/202 ảnh (18,8%)** còn cảnh báo chưa ai xem (`07_error_list_v3`: 21 ảnh `POSSIBLE_FALSE_POS`, 20 `POSSIBLE_LOOSE_BOX`, 12 `POSSIBLE_MISSING`, 3 `POSSIBLE_WRONG_CLASS`, 4 `EMPTY_LABEL`…). Thêm vào đó là các điểm mù pipeline không bắt được: box lỏng vừa phải (recall 0,20 trên calib), nhầm truck↔bus, và cặp ảnh trùng biến đổi mạnh img_0084/img_0074 vẫn còn. 122/202 ảnh không được người duyệt (77 ảnh không vào hàng đợi, cộng 45 ảnh vượt ngân sách) vẫn mang **nhãn máy (yolo26n)**, chưa qua mắt người.
Chặn trên thật sự là biến thể **`oracle`** (cùng ảnh với `clean`, nhãn người). **Việc tiếp theo:** thêm `"oracle"` vào `VARIANTS` trong notebook và chạy 3–5 seed; đo lại trên test bỏ 5 ảnh rò rỉ; duyệt thêm ≥ 18 ảnh để `clean` đạt Release rồi train lại.
