# Phân tích train raw và clean

YOLO26n được train 20 epoch, seed 0 và 1, batch 16, ảnh 640 trên T4, rồi đánh giá trên cùng 100 ảnh test. Clean dùng bản xuất 193 ảnh với pHash 16 và conf 0.6.

## 1. Chênh mAP50 và độ lệch chuẩn

| Biến thể | mAP50 seed 0 | mAP50 seed 1 | Trung bình | Độ lệch chuẩn mẫu |
|---|---:|---:|---:|---:|
| raw | 0.7256 | 0.7259 | 0.72575 | 0.00021 |
| clean | 0.7277 | 0.7311 | 0.72940 | 0.00240 |

Clean tăng **0.00365 mAP50 (0.365 điểm phần trăm)**, khoảng 1.52 lần độ lệch chuẩn của clean. Hai seed đều tăng, nhưng còn ít để khẳng định cải thiện ổn định. Độ lệch chuẩn raw hiển thị 0.000 do làm tròn.

| Chỉ số | raw, trung bình ± độ lệch chuẩn | clean, trung bình ± độ lệch chuẩn | clean − raw |
|---|---:|---:|---:|
| mAP50 | 0.72575 ± 0.00021 | 0.72940 ± 0.00240 | +0.00365 |
| mAP50–95 | 0.51170 ± 0.00382 | 0.49960 ± 0.00028 | −0.01210 |
| Precision | 0.76355 ± 0.06116 | 0.79365 ± 0.02850 | +0.03010 |
| Recall | 0.64900 ± 0.02814 | 0.61925 ± 0.00474 | −0.02975 |

Precision tăng, nhưng recall và mAP50–95 giảm. Cần thêm seed để đánh giá chắc hơn.

## 2. Số ảnh raw thực sự được train

Ultralytics bỏ 11 ảnh hoặc nhãn hỏng ở cả hai seed.

| Nguyên nhân trong log Ultralytics | Mã ảnh | Số ảnh |
|---|---|---:|
| Không đọc được ảnh hoặc ảnh bị cắt cụt | `img_0010`, `img_0136` | 2 |
| Tọa độ nhãn không hợp lệ hoặc vượt phạm vi | `img_0014`, `img_0022` | 2 |
| Mã lớp âm hoặc vượt phạm vi 0–3 | `img_0020`, `img_0099`, `img_0104`, `img_0117`, `img_0194`, `img_0199` | 6 |
| Cấu trúc nhãn không đồng nhất, không dựng được mảng | `img_0179` | 1 |
| **Tổng bị bỏ** | | **11** |

Raw thực sự train trên **213/224 ảnh**. JSON ghi 224 vì đếm file trước khi lọc. Các ảnh được coi là nền vẫn có thể tham gia train. Clean giữ đủ **193 ảnh**, có 3 backgrounds và 0 corrupt.

## 3. Rò rỉ test trong raw

Báo cáo đánh dấu **11/224 ảnh LEAK_TEST**. Cả 11 ảnh vẫn được nạp để train raw và đã bị loại khỏi clean.

| Ảnh raw | Ảnh test được báo khớp | Khoảng cách pHash |
|---|---|---:|
| `img_0013` | `test_087.jpg` | 16 |
| `img_0017` | `test_071.jpg` | 16 |
| `img_0021` | `test_048.jpg` | 16 |
| `img_0033` | `test_070.jpg` | 16 |
| `img_0038` | `test_002.jpg` | 16 |
| `img_0049` | `test_033.jpg` | 0 |
| `img_0101` | `test_039.jpg` | 6 |
| `img_0115` | `test_088.jpg` | 16 |
| `img_0167` | `test_044.jpg` | 2 |
| `img_0174` | `test_085.jpg` | 0 |
| `img_0221` | `test_009.jpg` | 0 |

Cặp img_0049–test_033.jpg cùng chụp người biểu diễn với quả bóng. Sáu cặp có pHash 16 cần xem thêm vì ngưỡng này có thể báo nhầm.

**Chưa đo được mức điểm raw bị thổi phồng.** Cần train lại raw sau khi loại các ca rò rỉ đã xác minh, giữ cùng cấu hình và seed để so sánh. Có thể thêm đối chứng loại ngẫu nhiên cùng số ảnh để kiểm ảnh hưởng của giảm dữ liệu. Các phép kiểm này chưa chạy.

## 4. Lớp được lợi nhiều nhất

| Lớp | raw seed 0 | raw seed 1 | raw trung bình | clean seed 0 | clean seed 1 | clean trung bình | Chênh trung bình |
|---|---:|---:|---:|---:|---:|---:|---:|
| car | 0.7511 | 0.7239 | 0.73750 | 0.7784 | 0.7276 | 0.75300 | +0.01550 |
| person | 0.8126 | 0.8315 | 0.82205 | 0.8136 | 0.8418 | 0.82770 | +0.00565 |
| truck | 0.6574 | 0.6395 | 0.64845 | 0.5865 | 0.6564 | 0.62145 | −0.02700 |
| bus | 0.6811 | 0.7087 | 0.69490 | 0.7321 | 0.6985 | 0.71530 | +0.02040 |

**Bus tăng AP50 trung bình nhiều nhất, 2.04 điểm phần trăm**, nhưng chỉ tăng ở seed 0. Truck giảm 2.70 điểm phần trăm.

Theo 02_error_list_v1.csv, img_0020 bị cảnh báo sai lớp. Khung truck trong raw được đổi thành bus sau duyệt mô phỏng. Sửa nhầm lớp có thể giúp bus học tốt hơn, nhưng chưa đủ để giải thích toàn bộ mức tăng. Cần giữ cùng tập ảnh, chỉ thay nhãn và chạy thêm seed để kiểm.

## 5. Những lỗi còn lại trong clean

Hàng đợi có **121 ảnh**, vượt ngân sách 80 ảnh. Sau duyệt mô phỏng, còn **34/193 ảnh có cảnh báo (17.62%)**, nên gate kết luận Hold.

| Mã cảnh báo | Số dòng trên ảnh chưa duyệt |
|---|---:|
| POSSIBLE_LOOSE_BOX | 15 |
| POSSIBLE_FALSE_POS | 10 |
| BOX_TINY | 6 |
| EMPTY_LABEL | 3 |
| BOX_HUGE | 3 |
| POSSIBLE_MISSING | 1 |
| **Tổng** | **38 dòng trên 34 ảnh** |

Bảng đếm cảnh báo trên ảnh chưa duyệt. Một ảnh có thể có nhiều cảnh báo.

**Clean chưa đạt chặn trên chất lượng dữ liệu sạch.** Ngoài các cảnh báo còn lại, ngưỡng pHash 16 đã loại nhầm hai cặp ảnh khác cảnh. Cần duyệt thêm, xem lại ảnh bị loại và lấy mẫu ảnh không có cảnh báo để tìm lỗi bị bỏ sót.

