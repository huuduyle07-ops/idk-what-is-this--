# Flashcards từ Practice đã hoàn thành

Bản đầu ngày 2026-10-29 bổ sung `/learn/flashcards`. Người học chọn câu hỏi từ một bộ Practice đã hoàn thành, tự nhớ đáp án rồi đối chiếu. Thẻ giữ câu hỏi, đáp án và nguồn đã lưu của Practice; tạo thẻ, mở đáp án và tự đánh giá không gọi thêm model.

## Cách dùng

1. Hoàn thành một bộ Practice. Bộ được hoàn thành khi các câu đã được giải quyết theo luồng Practice, kể cả trường hợp chủ động xem lời giải để tiếp tục.
2. Bấm **Create flashcards** trong phần kết quả, hoặc mở Flashcards rồi chọn một bài đã hoàn thành.
3. Những câu từng sai ở lần đầu, dùng gợi ý hoặc đã xem đáp án/lời giải được chọn sẵn. Có thể đổi lựa chọn trước khi tạo 1–5 thẻ; nếu không có câu nào thuộc nhóm này, chọn sẵn tất cả.
4. Tự trả lời câu hỏi ở mặt trước. Nếu câu hỏi phụ thuộc các phương án trắc nghiệm gốc, dùng **Show original choices** như một gợi ý. **Reveal answer** mở đáp án, giải thích và các đoạn nguồn để đối chiếu.
5. Chọn **Again** hoặc **Got it** sau khi mở đáp án. Đây là tự đánh giá; ứng dụng không chấm câu trả lời bạn nghĩ hoặc nói ra.

Các bộ lọc gồm **Due now**, **Needs review** và **All cards**. Thẻ mới đến hạn ngay. Sau khi đánh giá, thẻ được úp lại, các phương án gợi ý được ẩn và danh sách chuyển sang thẻ tiếp theo. Có thể xem tất cả để ôn thêm trước hạn. Dùng **Cập nhật lịch ôn** khi thời gian đã qua hoặc muốn đọc trạng thái mới từ tab khác.

Lịch ban đầu dùng quy tắc cố định: Again đặt lần ôn sau 10 phút và đánh dấu Needs review; Got it đặt lần ôn sau 1 ngày, rồi 3 ngày và tối đa 7 ngày theo chuỗi Got it. Again đặt lại chuỗi này. Needs review được xóa sau Got it, nhưng điều đó không chứng minh đã thành thạo hay nhớ lâu. Chưa có thuật toán ước lượng khả năng nhớ, thông báo ngoài ứng dụng hoặc tác vụ tự gửi lời nhắc.

## Nội dung và nguồn

Mặt trước dùng nguyên câu hỏi của Practice. Phương án gốc là gợi ý tùy chọn; mặt sau gồm nội dung phương án đúng theo đáp án model, giải thích và evidence đã lưu. Không tự tạo lại câu hỏi bằng một model khác, không tự biến mục tiêu học thành câu hỏi mới. Bản đầu chưa có sửa nội dung thẻ hoặc tạo thẻ trực tiếp từ tài liệu chưa làm Practice.

Chỉ cho tạo từ Practice hoàn thành để flashcards không trở thành đường mở đáp án của một bài chưa làm. Một bộ hoàn thành có thể bao gồm câu đã xem lời giải và chưa trả lời; không suy ra tất cả câu đã được người học tự giải đúng.

Snapshot của thẻ bao gồm collection/unit/source ID, vị trí trang/slide/đoạn, quote, nguồn model và phiên bản ghi chú ảnh nếu có. Sửa hoặc xóa Practice sau đó không đổi snapshot này. Liên kết Materials mở nguồn hiện tại; quote trên thẻ là bản đã lưu khi tạo bài. Ghi chú ảnh vẫn là ghi chú do người học viết, không được gọi là OCR.

Đáp án kế thừa độ đúng và giới hạn của bộ Practice. Trích đoạn khớp nguồn không tự chứng minh đáp án hoặc cách diễn giải chính xác. Người học có thể mở nguồn để xem lại trước khi dùng thẻ làm tài liệu ôn chính.

## Lưu trữ và phục hồi

`core/learning/flashcard_store.py` quản lý `.agent/learning/flashcards.sqlite3`; cấu hình bằng `LEARNING_FLASHCARD_STORE_PATH`. Kho này tách khỏi bài Practice và phiên Java, gắn với owner của cookie người học. Mỗi owner có tối đa 30 bộ còn lưu, 1.000 request tạo đã ghi nhận và tối đa 500 hành động/bộ.

Request tạo ràng buộc với Practice ID và tập question ID. Gửi lại đúng request trả bộ đã lưu, kể cả khi Practice gốc đã bị xóa. Xóa bộ thẻ giữ dấu request tối thiểu để một lần gửi lại cũ không tạo lại bộ đã xóa. Đọc không tạo kho mới; dữ liệu lỗi hoặc đường dẫn bị chuyển hướng không bị coi là danh sách rỗng để ghi đè.

Mọi thao tác mở đáp án, xem phương án, úp thẻ và đánh giá có request ID cùng expected_revision. Gửi lại đúng một thao tác không tăng review_count hoặc dời hạn ôn lần hai. Xung đột tab yêu cầu đọc bản đã lưu trước khi đánh giá tiếp. UI giữ nguyên card ID, rating và request ID khi chưa rõ phản hồi; không áp dụng lượt cũ lên thẻ vừa được chuyển tới.

Hạn ôn được tính bằng thời gian UTC của server, theo số giây đã trôi qua. Đọc lại tính lại due/counts tại thời điểm đọc mà không tăng revision. Nhật ký rating giữ việc đã mở đáp án và đã xem các lựa chọn, nhưng không được gọi là bằng chứng thành thạo.

## API

- `GET /learn/api/flashcards`: danh sách bộ của người học, không kèm đáp án.
- `POST /learn/api/flashcards`: `request_id`, `practice_id`, `question_ids`.
- `GET /learn/api/flashcards/<id>`: mặt trước, trạng thái ôn và đáp án/phương án chỉ khi đã mở.
- `POST /learn/api/flashcards/<id>/actions`: `action`, `payload`, `expected_revision`, `request_id`; action gồm reveal, choices, hide, rate.
- `DELETE /learn/api/flashcards/<id>`: xóa bộ thẻ và lịch ôn của bộ.

Các route giữ auth, ownership, Origin/CSRF và private headers hiện có. Nội dung thẻ/nguồn dựng bằng DOM/textContent; không chạy HTML hoặc code trong tài liệu. API lấy Practice ở server theo owner, không nhận câu hỏi/đáp án/quote tự khai từ body tạo bộ.

## Kiểm tra

Các kiểm thử tập trung nằm trong `tests/learning/test_flashcard_store.py`, `tests/integration/test_learning_flashcards_web.py` và `tests/integration/test_learning_flashcards_browser.py`. Dùng Practice/model giả lập và SQLite tạm; lịch ôn được kiểm tra bằng clock riêng để không thay đổi clock của cookie xác thực. Các kiểm thử kiểm tra dữ liệu, quyền, phục hồi và UI, không đo hiệu quả ghi nhớ của người học.

Hoàn tất ngày 2026-10-29: **73 kiểm thử khác nhau vượt qua** — 50 domain Flashcards, 13 API, 1 cổng bảo vệ route ghi, 6 Chromium Flashcards và 3 hồi quy mobile/điều hướng Materials, Java, chat. Ca clock API được sửa để không thay clock cookie; ca bàn phím được chạy lại sau khi thêm focus cho danh sách đến hạn rỗng. Không cộng các lượt chạy lại vào tổng. Python/JavaScript qua kiểm tra cú pháp, diff qua kiểm tra whitespace; đã xem ảnh desktop/mobile. Không chạy toàn repository.

Server local cổng 5055 đã mở bản mới. Trang Flashcards trả 200, script/CSS phục vụ khớp nội dung file hiện tại; API giữ `Cache-Control: no-store` và trả 404 đúng cho bộ không tồn tại. Không tạo bộ thẻ hoặc bài giảng mẫu trong dữ liệu người học, không gọi thêm model để kiểm tra flashcards.
