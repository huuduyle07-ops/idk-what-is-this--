# Test Maker: bài tính, sơ đồ và tự luận

Bản đầu ngày 2026-10-29 bổ sung `/learn/test-maker`. Người học chọn chủ đề, làm một đề có dữ liệu thay đổi theo seed, lưu bài và nộp toàn bộ đề để đối chiếu. Tạo đề, lưu và chấm phần khách quan đều chạy tại ứng dụng, không gọi Ollama/Gemini.

## Nội dung ban đầu

| Nhóm | Chủ đề | Cách trả lời và đánh giá |
| --- | --- | --- |
| Machine Learning | MSE, Gini impurity, TPR | Nhập số thập phân hoặc phân số; TPR nhận thêm phần trăm có `%`. Đáp án được tính từ dữ liệu của đề. |
| Operating Systems | Dịch địa chỉ qua bảng trang | Nhập địa chỉ byte vật lý dạng số nguyên thập phân hoặc `0x` hexadecimal. Đề nêu kích thước trang và bảng ánh xạ hợp lệ. |
| Linear Algebra | Nhân ma trận 2×3 với 3×2 | Điền ma trận 2×2; mỗi ô đúng nhận một điểm. |
| Sơ đồ | Vòng lặp train model; producer–consumer | Điền trực tiếp vào các ô trống trên SVG. Chấm từng ô theo danh sách nhãn tương đương đã soạn. |
| Tự luận | Điều kiện deadlock; ISR/semaphore; R³ và không gian con; Entropy/Information Gain/Gini | Lưu câu trả lời, mở bài giải tham khảo và rubric sau khi nộp; cần người xem lại, chưa tự chấm điểm. |

Có 11 chủ đề, chọn tối đa một câu cho mỗi chủ đề. Seed là số nguyên từ 0 đến 2³¹−1; cùng phiên bản, tập chủ đề và seed cho cùng đề, không phụ thuộc thứ tự gửi các chủ đề. Đổi seed thay đổi số liệu bài tính/ma trận; sơ đồ và tự luận hiện là mẫu cố định. Nội dung câu hỏi bằng tiếng Anh, giao diện điều hướng bằng tiếng Việt.

Các câu hỏi do dự án soạn kèm tham khảo từ scikit-learn, OSTEP, NumPy, Google ML Crash Course, MIT OpenCourseWare và FreeRTOS. Đây là bộ mẫu độc lập với tài liệu người học đã nhập. Practice tiếp tục phục vụ câu hỏi trắc nghiệm dựa trên bài giảng; Test Maker chưa tự tạo bài tính hoặc rubric từ PDF/PPTX/DOCX.

## Luồng làm bài

1. Chọn một hoặc nhiều chủ đề và seed, bấm **Create test**.
2. Chuyển giữa các câu để nhập số, điền ma trận/sơ đồ hoặc viết tự luận. Nội dung đang viết được giữ khi chuyển câu trong trang.
3. **Save draft** lưu bài lên máy chủ. Tải lại trang chỉ khôi phục phần đã lưu; trình duyệt cảnh báo khi rời trang còn bài chưa lưu.
4. **Review & submit** mở xác nhận nộp toàn bộ đề, kể cả câu còn trống. Sau khi nộp không sửa bài cũ; có thể tạo đề khác để làm lại.
5. Đối chiếu kết quả, giải thích và rubric. Tổng điểm tự động chỉ gồm bài số, ma trận và sơ đồ; tự luận được đếm riêng là đã trả lời/chờ xem lại. Không có điểm tổng suy diễn hoặc kết luận thành thạo.

API không trả answer key, lời giải hoặc rubric khi đề đang làm. Save không chấm bài và không tiết lộ đúng/sai. Submit mới tính kết quả. Câu số có chuỗi chưa hợp lệ vẫn được lưu như bài đang viết, rồi được đánh giá sai khi nộp; không dùng `eval` hay chạy code người học. Bộ đọc số giới hạn độ dài, số mũ và độ lớn trước khi chuyển thành phân số. Bài số thông thường có sai số tuyệt đối 1/10000; địa chỉ và từng ô ma trận cần khớp chính xác. Điểm sơ đồ chia theo số ô đúng; tên viết khác chỉ được nhận nếu thuộc các alias đã soạn, không có model suy đoán ý nghĩa.

Sơ đồ là hình vector dựng từ các node/edge tin cậy trong mẫu, với ô nhập HTML ở vị trí tương ứng. Trên màn hình nhỏ, cuộn bên trong sơ đồ. Bản này chưa cho tải hình tùy ý và đánh dấu vùng trống trên hình.

## Lưu trữ và phục hồi

`core/learning/test_maker.py` sở hữu mẫu có phiên bản, sinh số liệu, kiểm tra cấu trúc câu trả lời và chấm phần khách quan. `test_maker_store.py` lưu snapshot riêng tại `.agent/learning/test_maker.sqlite3`; có thể đổi bằng `LEARNING_TEST_MAKER_STORE_PATH`. Mỗi owner có tối đa 30 đề đang lưu, 1.000 request tạo đã ghi nhận và 200 thao tác lưu/nộp trên một đề.

Snapshot `test-maker-v1` được kiểm lại với bộ dựng v1 đã đóng băng. Khi đổi nội dung, hình học, rubric hoặc quy tắc sinh đề, phải tạo phiên bản mới và giữ bộ kiểm tra/dựng v1 để bài cũ tiếp tục đọc được. Không sửa bộ dựng v1 rồi âm thầm chấm lại bài đã lưu bằng đề mới. Kết quả đã nộp được đối chiếu với snapshot và bài làm; dữ liệu hỏng không bị coi như kho rỗng để ghi đè.

Mọi thao tác lưu/nộp có request ID và expected revision. Gửi lại đúng request không nộp hai lần. Khi chưa rõ phản hồi, UI giữ request và nội dung đã gửi để kiểm tra lại. Khi tab khác sửa bài, người học đọc bản mới rồi chọn dùng bài đã lưu hoặc giữ bản đang viết; không tự ghi đè. Xóa đề giữ dấu request tạo tối thiểu để lần gửi lại cũ không tạo lại đề đã xóa.

## API và kiểm tra

- `GET /learn/api/test-maker/catalog`: 11 chủ đề và loại câu hỏi.
- `GET /learn/api/test-maker`: danh sách đề của owner.
- `POST /learn/api/test-maker`: `request_id`, `topic_ids`, `seed`.
- `GET /learn/api/test-maker/<id>`: đề và bài làm; kết quả chỉ có sau khi nộp.
- `POST /learn/api/test-maker/<id>/actions`: `action` là `save` hoặc `submit`, `payload.answers`, `expected_revision`, `request_id`.
- `DELETE /learn/api/test-maker/<id>`: xóa đề và bài làm.

Các route giữ auth, ownership, Origin/CSRF và private headers của Teacher. Client không được gửi câu hỏi, đáp án chuẩn, rubric hoặc hình SVG tùy ý. Nội dung dựng bằng DOM/textContent; không thực thi HTML trong câu trả lời.

Kiểm thử tập trung ở `tests/learning/test_test_maker.py`, `tests/learning/test_test_maker_store.py`, `tests/integration/test_learning_test_maker_web.py` và `tests/integration/test_learning_test_maker_browser.py`. Số liệu được kiểm bằng phép tính độc lập trên nhiều seed; kiểm thử UI dùng kho tạm, không gọi model hoặc thêm bài mẫu vào dữ liệu thật của người học.

Kết quả ngày 2026-10-29: **126 kiểm thử khác nhau vượt qua** — 54 engine, 47 store, 14 API, 1 cổng bảo vệ route ghi, 7 Chromium Test Maker và 3 hồi quy điều hướng/mobile Materials, Java, chat. Chỉ chạy lại ca bị ảnh hưởng sau sửa, không cộng các lượt chạy chồng vào tổng. Kiểm tra tích hợp đã phát hiện và sửa thứ tự chủ đề chưa thống nhất; kiểm tra phục hồi giữ được bản nháp khi mất phản hồi Save rồi tab khác sửa/nộp bài. Kiểm tra ảnh đã phát hiện quy tắc icon chung thu nhỏ SVG; kích thước và ngắt dòng nhãn được sửa riêng cho sơ đồ, kèm kiểm tra hình học thực tế. Tự luận bỏ trống cũng không hiển thị điểm tự động. Python/JavaScript qua kiểm tra cú pháp; không chạy toàn repository.

Máy chủ học local tại cổng 5055 đã được mở bản mới sau khi kiểm tra không có yêu cầu model còn hiệu lực. Trang trả 200, catalog có đủ 11 chủ đề, API giữ private headers và trả 404 đúng cho đề không tồn tại. Không thay cấu hình model hiện có hoặc tạo bài mẫu trong kho dữ liệu thật.
