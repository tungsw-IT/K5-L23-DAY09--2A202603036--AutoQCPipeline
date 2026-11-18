# Báo cáo Day 09 — Hà Thanh Tùng-2A202603036


## 1. Kết luận trước
Pipeline kết luận HOLD. Lô đầu vào có 224 ảnh, trong đó 193 ảnh qua cửa vào và được xuất vào bản nháp clean_v1. Sau lượt duyệt mô phỏng, 34/193 ảnh (17,62%) vẫn còn cảnh báo, vượt ngưỡng 10%, nên dataset chưa được phát hành.

## 2. Lỗi và phân việc


| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `POSSIBLE_MISSING` | 53 | Người | Kiểm tra vật thể bị bỏ sót và bổ sung khung nếu cần. |
| `POSSIBLE_FALSE_POS` | 28 | Người | Kiểm tra khung có bao vật thể thật hay không. |
| `POSSIBLE_LOOSE_BOX` | 27 | Người | Xem và chỉnh khung lỏng hoặc lệch. |
| `POSSIBLE_WRONG_CLASS` | 17 | Người | Kiểm tra và sửa lớp của vật thể. |
| `EMPTY_LABEL` | 11 | Người | Kiểm tra ảnh nền hay ảnh có vật thể bị bỏ sót. |
| `LEAK_TEST` | 11 | Máy (cửa vào) | Loại ảnh bị phát hiện trùng với kho test/val. |
| `BOX_OUT_OF_IMAGE` | 8 | Máy | Cắt khung về trong ảnh, xóa dòng nếu phần còn lại không có diện tích. |
| `DUP_IMAGE_EXACT` | 8 | Máy (cửa vào) | Loại ảnh trùng hệt. |
| `DUP_IMAGE_NEAR` | 7 | Máy (cửa vào) | Loại ảnh bị đánh dấu gần trùng theo ngưỡng pHash. |
| `DUP_BOX` | 7 | Máy | Xóa dòng nhãn có khung trùng. |
| `BOX_TINY` | 6 | Người | Kiểm tra khung quá nhỏ theo quy tắc gán nhãn. |
| `MISSING_LABEL_FILE` | 6 | Người | Máy đưa ảnh vào hàng đợi để người gán nhãn. |
| `BAD_CLASS_ID` | 6 | Máy | Xóa dòng có mã lớp không hợp lệ. |
| `CLASS_RARE` | 4 | Người | Xem lại phân bố của các lớp ít xuất hiện. |
| `BOX_ZERO` | 4 | Máy | Xóa dòng có khung không có diện tích. |
| `BAD_SIZE` | 3 | Máy (cửa vào) | Loại ảnh có kích thước không đạt yêu cầu. |
| `BOX_HUGE` | 3 | Người | Kiểm tra khung lớn có bao đúng vật thể hay không. |
| `BAD_FORMAT` | 3 | Máy | Xóa dòng nhãn sai định dạng. |
| `CORRUPT_IMAGE` | 2 | Máy (cửa vào) | Loại ảnh hỏng, không đọc được. |
| `BAD_CLASS_NAME` | 2 | Máy | Ghi lại danh sách tên lớp chuẩn trong `data.yaml`. |

img_0020 đứng đầu hàng đợi vì vừa có một dòng nhãn bị máy xóa, vừa có hai cảnh báo thiếu khung và sai lớp với độ tin cậy cao. Sáu ảnh thiếu file nhãn xếp ngay sau vì cần người gán nhãn. Trong 80 ảnh được duyệt mô phỏng, 74 ảnh có cảnh báo ngữ nghĩa, chiếm 94/120 dòng cảnh báo ngữ nghĩa trước duyệt.

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 16 | Ảnh gần trùng: 100% / 50% → 100% / 83% | Trên tập calib, phát hiện được 5/6 ca gần trùng thay vì 3/6. Tôi chọn ngưỡng 16 để bắt thêm ảnh gần trùng, chấp nhận rủi ro loại nhầm ảnh trên lô raw. |
| `second_opinion.conf` | 0.25 | 0.6 | Thiếu khung: 50% / 100% → 57% / 100%. Sai lớp: 56% / 83% → 62% / 83%. Khung lỏng: 29% / 40% → 20% / 20%. | Cảnh báo thiếu khung và sai lớp chính xác hơn, đồng thời vẫn phát hiện 8/8 ca thiếu khung và 5/6 ca sai lớp. Đổi lại, số ca khung lỏng phát hiện được giảm từ 2/5 xuống 1/5. |


 Ở ngưỡng phash_dist: 16, precision phát hiện ảnh gần trùng đạt 100% trên tập calib. Khi mở ba cặp ảnh trên lô raw có khoảng cách pHash bằng 16, tôi thấy hai cặp bị báo nhầm. img_0011 là ảnh đánh tennis còn img_0008 là ảnh trượt tuyết. img_0177 là ảnh lướt sóng còn img_0113 là ảnh người ngồi ở bàn ăn. Cặp img_0084 và img_0074 gần trùng thật vì cùng chụp cảnh người cầm ô với khung hình cắt khác nhau. Việc kiểm tra trực tiếp cho thấy kết quả 100% trên tập calib có thể khiến tôi đánh giá quá cao độ chính xác của ngưỡng 16 trên lô raw.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) Kiểm tra cửa chặn.
Tôi chạy pipeline với --budget 0. Vì không có ảnh nào được duyệt, 6/193 ảnh vẫn thiếu file nhãn. Pipeline kết luận Rework, trả mã thoát 20 và không xuất dataset.

(b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).
| STT | Mã ảnh | Vật thể và vị trí | Lỗi quan sát được |
| --- | --- | --- | --- |
| 1 | `img_0001` | vật thể người ở giữa ảnh | Không được gán box cho lớp person |
| 2 | `img_0002` | Vật thể động cơ chân vịt,ở phía bên phải của ảnh,cạnh box người | gán nhầm thành class person |
| 3 | `img_0004` | [Vật thể ô tô ở sát mép ảnh bên phải] | không được gán box cho lớp car |
## 5. Train: raw vs clean (tùy chọn, chấm riêng)
| Biến thể | #ảnh train ban đầu | Số seed | mAP50 (TB ± độ lệch) | mAP50–95 (TB ± độ lệch) | Precision (TB ± độ lệch) | Recall (TB ± độ lệch) |
|---|---:|---:|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 193 | 2 | 0.729 ± 0.002 | 0.500 ± 0.000 | 0.794 ± 0.028 | 0.619 ± 0.005 |

Clean có mAP50 cao hơn raw khoảng 0,00365, tương đương 0,365 điểm phần trăm. Mức tăng này khoảng 1,52 lần độ lệch chuẩn của clean (0,00240). Cả hai seed đều tăng, nhưng tôi mới chạy hai seed nên chưa thể khẳng định kết quả ổn định. Recall và mAP50–95 của clean cũng giảm.

Tôi nghĩ có hai nguyên nhân cần kiểm tra thêm:
- Raw có ảnh trùng với test, có thể khiến điểm cao hơn thực tế. Tôi sẽ xác minh các cặp bị báo LEAK_TEST, loại những ảnh rò rỉ rồi train lại với cùng cấu hình và seed để so sánh.
- Clean vẫn còn nhãn máy chưa được duyệt, có thể ảnh hưởng đến kết quả. Tôi sẽ duyệt và sửa các nhãn còn lại, giữ nguyên tập ảnh rồi train lại để xem mức cải thiện.

## 6. Quyết định và ghi chú AI
Tôi giữ quyết định HOLD vì 34/193 ảnh (17,62%) vẫn còn cảnh báo. Cần duyệt thêm, sửa lỗi được xác nhận và kiểm lại ảnh bị loại nhầm. Sau đó chạy lại QC, chỉ phát hành khi không còn lỗi bắt buộc và tỷ lệ ảnh chưa duyệt còn cảnh báo dưới 10%.
 
 (b)Yêu cầu với AI: Hỗ trợ hoàn thiện label_format, gate, autofix và second_opinion theo yêu cầu của lab.

Cách kiểm tra: Tôi chạy test, đối chiếu log, mở ảnh kiểm tra và thử --budget 0 để xác nhận cửa chặn hoạt động đúng.

Một lần AI sai: AI tự thêm số liệu chưa có trong kết quả chạy. Tôi phải đối chiếu lại log và sửa theo số liệu thực tế.