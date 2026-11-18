# Báo cáo Day 09 — Lê Trần Phi Hùng, 2A202603353

## 1. Kết luận

**Hold.** Pipeline loại 19/224 ảnh ở cửa vào và xuất bản nháp gồm 205 ảnh. Sau khi duyệt 80/125 ảnh trong hàng đợi, số lỗi bắt buộc về 0 nhưng còn 38/205 ảnh có cảnh báo (18,54%), vượt ngưỡng 10%. [Kết quả gate](reports/08_summary.json)

## 2. Lỗi và phân việc

Mỗi mã dưới đây có số lần xuất hiện tương ứng trong [danh sách lỗi vòng 1](reports/02_error_list_v1.csv). Một ảnh hoặc một dòng nhãn có thể có nhiều mã.

| Mã lỗi | Số lần theo thứ tự mã | Xử lý |
|---|---|---|
| CORRUPT_IMAGE, BAD_SIZE | 2, 3 ảnh | Máy loại ảnh hỏng hoặc dưới kích thước tối thiểu. |
| DUP_IMAGE_EXACT, DUP_IMAGE_NEAR, LEAK_TEST | 8, 2, 4 ảnh | Máy loại bản trùng và ảnh trùng kho test/val. |
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX | 3, 6, 4, 7 dòng | Máy xóa dòng sai định dạng, lớp sai, box rỗng hoặc box lặp. |
| BOX_OUT_OF_IMAGE, BAD_CLASS_NAME | 8 dòng, 2 tên lớp | Máy cắt box theo biên ảnh và chuẩn hóa tên lớp. |
| MISSING_LABEL_FILE, EMPTY_LABEL | 6, 12 ảnh | Người gán nhãn thiếu hoặc xác nhận ảnh nền. |
| BOX_HUGE, BOX_TINY | 3, 6 dòng | Người kiểm tra kích thước box theo vật thể. |
| CLASS_RARE | 4 cảnh báo cấp bộ dữ liệu | Người kiểm tra thống kê lớp. |
| POSSIBLE_MISSING, POSSIBLE_LOOSE_BOX, POSSIBLE_WRONG_CLASS, POSSIBLE_FALSE_POS | 53, 28, 18, 25 cảnh báo | Người xem ảnh để xác nhận vật bị sót, box lỏng, sai lớp hoặc box thừa. |

`img_0020` đứng đầu với 11,524 điểm. Cảnh báo sai lớp đóng góp 3 × (1 + 0,9474), thiếu box đóng góp 2 × (1 + 0,8408), và một lần xóa dòng cộng 2 điểm. Tổng này vượt 10 điểm của ảnh chỉ thiếu file nhãn. Trong ngân sách 80 ảnh, người duyệt đã xem 74/103 ảnh có cờ ngữ nghĩa, tương ứng 94/123 cảnh báo sau autofix. Đây là số cờ được xem, còn số lỗi thật của raw chưa có đáp án. [Hàng đợi](reports/05_review_queue.csv) · [Nhật ký duyệt](reports/06_review_log.csv)

## 3. Calibration (2 ngưỡng)

Precision (P) là số cờ đúng trên tổng số cờ. Recall (R) là số ca phát hiện được trên tổng số ca chèn. Số liệu lấy từ [báo cáo sweep trên 39 ảnh calib](calibration/calibration_report.md).

| Tham số | Khởi đầu → Đã chọn | Precision / Recall (trước → sau) | Lý do |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → 4 | Gần trùng: P 3/3 → 4/4, R 3/6 → 4/6. Trùng byte: P và R đều giữ 3/3. | Bắt thêm 1 ca gần trùng trên calib. Ngưỡng 4 là mức thấp nhất đạt 4/6 trong sweep, giúp hạn chế xóa nhầm ảnh. |
| `second_opinion.conf` | 0.25 → 0.60 | Thiếu box: P 8/16 → 8/14, R giữ 8/8. Nhầm lớp: P 5/9 → 5/8, R giữ 5/6. Box lỏng: P 2/7 → 1/5, R 2/5 → 1/5. Box thừa: P giữ 5/14, R giữ 5/5. | Bớt 2 cờ sai thiếu box và 1 cờ sai nhầm lớp, đổi lại bỏ sót thêm 1 ca box lỏng trên calib. Cờ box thừa dùng `fp_conf` riêng. |

**Điểm dễ bị đánh lừa.** Ngưỡng pHash 16 đạt P 5/5 và R 5/6 trên calib, nhưng khi so ảnh trong raw, nó gắn cờ nhầm cặp `img_0011` (tennis) và `img_0008` (trượt tuyết). Ngưỡng 16 cũng bắt đúng cặp `img_0084` và `img_0074` (cùng cảnh người cầm ô, khác khung cắt), nên chọn ngưỡng 4 đồng nghĩa bỏ sót cặp này. Ở ngưỡng 4, đã mở xem cả 2 cặp gần trùng được gắn cờ trong raw. Hai cặp `img_0076`–`img_0042` và `img_0143`–`img_0037` đều là cùng ảnh xe buýt ở hai kích thước.

**Chạy thử trên raw.** Sau hiệu chỉnh, cửa vào vẫn loại 19/224 ảnh và nhận 205 ảnh. Hàng đợi giảm từ 145 xuống 125 ảnh. Sau khi duyệt 80 ảnh, còn cảnh báo trên 38/205 ảnh (18,54%), giảm từ 60/205 (29,27%). Kết quả vẫn là Hold.

## 4. Kiểm tra gate và điểm mù

Chạy lại pipeline với `--budget 0` trong thư mục riêng. Cả 6 ảnh thiếu file nhãn vẫn còn lỗi bắt buộc. Gate trả **Rework**, mã thoát **20** và không xuất dataset. Trong lần chạy chính thức, cả 6 ảnh được chuyển cho người gán.

Khi xem 10 ảnh phủ nhãn, có ba trường hợp thiếu box. Ở `img_0001`, người mặc quân phục bên phải thiếu box người. Ở `img_0004`, xe bạc góc dưới bên phải thiếu box xe. Ở `img_0007`, xe trắng phía sau máy bay thiếu box. Hai ảnh đầu được gắn cờ `POSSIBLE_MISSING`, còn ảnh thứ ba không có cờ trong danh sách vòng 1. Đây là một ví dụ model kiểm tra cũng bỏ sót vật nhỏ. Điểm mù thứ hai là ảnh trùng bị cắt khung. Cặp `img_0074` và `img_0084` ở mục 3 có khoảng cách pHash 16 nên lọt qua ngưỡng 4.

## 5. Train raw và clean

Colab chạy YOLO26n trong 20 epoch, seed 0 và 1 cho mỗi biến thể. Bảng tổng hợp từ bốn tệp kết quả trên cùng tập test 100 ảnh.

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 205 | 2 | 0.700 ± 0.030 | 0.486 ± 0.013 | 0.715 ± 0.073 | 0.615 ± 0.017 |

Chênh mAP50 (clean − raw) = **-0.025**.

Chênh lệch trung bình 0,025 nhỏ hơn độ lệch chuẩn giữa hai seed của clean (0,030). Ở seed 0, clean thấp hơn raw 0,0468 điểm mAP50. Ở seed 1, khoảng cách chỉ còn 0,0040. Hai seed chưa đủ để kết luận việc làm sạch khiến mô hình kém đi.

- Bốn ảnh raw bị gắn cờ trùng kho tham chiếu có thể làm điểm raw cao hơn. Kiểm bằng cách huấn luyện lại raw sau khi loại riêng các ảnh rò rỉ, giữ cùng seed và cấu hình.
- Clean có ít hơn raw 19 ảnh. Để tách ảnh hưởng của số ảnh khỏi ảnh hưởng của nhãn, huấn luyện trên cùng danh sách 205 ảnh với nhãn trước và sau QC, rồi so sánh theo từng seed.

## 6. Quyết định và ghi chú AI

**Giữ bản nháp ở trạng thái Hold.** Với 205 ảnh và 0 lỗi bắt buộc, tối đa 20 ảnh được phép còn cảnh báo để đạt Release. Cần xử lý cảnh báo của ít nhất 18 trong 38 ảnh còn lại và chạy lại gate trước khi phát hành.

**Cách dùng AI**

- **Prompt chính.** Đầu vào gồm nhãn YOLO `id cx cy w h`, ảnh, `data.yaml` và dự đoán YOLO26l đã lưu. Yêu cầu AI viết bốn module để kiểm nhãn, đối chiếu dự đoán, sửa lỗi theo quy tắc và áp dụng điều kiện của gate. Đầu ra gồm danh sách lỗi và cảnh báo, log thay đổi và quyết định của gate. Giới hạn thao tác sửa, xóa trong bản sao làm việc.
- **Cách kiểm.** Rà các lệnh ghi và xóa. `autofix` có thể xóa ảnh kèm nhãn và ghi đè file nhãn hoặc `data.yaml` trong bản sao làm việc. Chạy pytest (79/79 test đạt), chạy pipeline trên bản sao và đối chiếu tập calib (17/17 ca lỗi theo quy tắc được phát hiện).
- **Lỗi AI mắc.** Bản đầu của `label_format.run` thiếu `return issues`, nên test nhận `None`. Sau khi thêm dòng trả kết quả, 14/14 test của module đạt.

### Check bổ sung: tỷ lệ cạnh box

Chạy `python -m pipeline.checks.aspect_ratio` trên `work/run/ds`. Check đổi chiều rộng và chiều cao từ YOLO sang pixel rồi cảnh báo `BOX_EXTREME_ASPECT` khi cạnh dài lớn hơn 12 lần cạnh ngắn. Kết quả trên 205 ảnh sau duyệt là 0 cảnh báo ở ngưỡng này. Hai test kiểm cách đổi sang pixel, biên ngưỡng và xử lý dòng hỏng đều đạt, trong đó có một box chèn sẵn với tỷ lệ 50:1 được phát hiện. CSV được ghi riêng ở `work/aspect_ratio.csv`.

### Đối chiếu CVAT

Đã chuẩn bị hai gói import cho 5 ảnh từ hàng đợi duyệt. Tính theo nhãn YOLO và kích thước ảnh, bộ lọc `width < 20` dự kiến khớp 10 box. Số box theo ảnh là `img_0020` (3), `img_0053` (1), `img_0135` (2), `img_0030` (3) và `img_0124` (1). Khi chạy lại check trên cùng nhãn, cả năm ảnh đều không có `BOX_TINY`. Check này dùng cạnh ngắn dưới 12 px, còn bộ lọc CVAT chỉ xét chiều rộng dưới 20 px. Người gán có thể bật `can_review` khi muốn nhờ người khác xem một box khó. Trong pipeline, mã cảnh báo và điểm ưu tiên trong `05_review_queue.csv` giúp đưa các ảnh cần xem lên trước.

Trạng thái CVAT: còn chờ xác nhận bộ lọc trong giao diện và ảnh chụp.
