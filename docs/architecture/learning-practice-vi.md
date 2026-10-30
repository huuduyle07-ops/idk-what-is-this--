# Luyện tập từ các phần nguồn đã chọn

Bản đầu ngày 2026-10-28 nối tài liệu bài giảng với một bộ 3–5 câu trắc nghiệm tại `/learn/practice`. Bài Java soạn sẵn tiếp tục ở `/learn`. Từ 2026-10-29, bộ đã hoàn thành có thể chuyển thành [flashcards với lịch ôn đơn giản](learning-flashcards-vi.md); bài tính, điền sơ đồ và tự luận có rubric nằm ở [Test Maker dùng mẫu có phiên bản](learning-test-maker-vi.md). Nhập nguồn nghiên cứu qua URL/DOI vẫn là bước sau.

## Luồng người học

Trong Materials, mở một phần nguồn rồi chọn liên kết Practice; hoặc vào Practice để chọn bộ tài liệu và 1–8 trang/slide/đoạn. Xem đoạn văn sẽ được gửi, chọn 3–5 câu rồi bấm Generate questions. Tải trang, chọn nguồn và mở bộ câu hỏi cũ không gọi model.

Mỗi unit chỉ gửi tối đa 1.000 ký tự đầu có nội dung. Đây là phạm vi người học chọn, không phải tóm tắt hay đánh giá toàn bộ file. Ảnh chỉ dùng mô tả đã lưu của người học, chưa nhận diện hình. Phần không có chữ dùng được bị từ chối trước khi gọi model.

Model tạo câu hỏi, mục tiêu, bốn lựa chọn, đáp án, giải thích, hai gợi ý và 1–2 quote cho mỗi câu. Server kiểm tra cấu trúc, số lượng, giới hạn, câu hỏi/lựa chọn trùng và quote khớp nguyên văn với các đoạn đã gửi. Kiểm tra quote xác nhận vị trí nguồn; chưa chứng minh câu hỏi, phương án nhiễu hoặc đáp án đúng về mặt nội dung.

Bộ mới ở trạng thái Draft. Người học xem câu hỏi/lựa chọn và có thể chủ động Review answer & source trước khi bắt đầu. Việc mở đáp án được ghi nhận; không coi lần trả lời sau đó là kết quả độc lập. Start practice chuyển sang làm lần lượt từng câu.

Trả lời sai chưa mở đáp án đầy đủ. Người học có thể thử lại, xin gợi ý tăng dần hoặc chủ động xem lời giải. Sau khi chọn đúng theo đáp án model, hoặc đã mở lời giải, người học có thể chuyển câu. Phần giải thích tự viết được lưu để xem lại, chưa được AI chấm. Không chạy code trong bộ câu hỏi này.

Kết quả ghi số câu đã trả lời, đúng ở câu trả lời đầu, đúng sau hỗ trợ, gợi ý và đáp án đã xem trước buổi làm. Các số này phản ánh thao tác trong ứng dụng và sự khớp với đáp án model; không chứng minh khả năng thành thạo hay việc không dùng trợ giúp bên ngoài.

## Lưu trữ và quyền truy cập

`core/learning/practice_store.py` quản lý `.agent/learning/practice.sqlite3`, cấu hình được bằng `LEARNING_PRACTICE_STORE_PATH`. Bộ câu hỏi gắn với owner từ cookie, tách khỏi phiên Java và lịch sử chat. Lưu bản chụp đoạn nguồn, source/unit ID, vị trí, phiên bản ghi chú ảnh, model, câu hỏi và đáp án cùng bộ bài. Sửa nhãn hoặc ghi chú nguồn sau này không sửa lịch sử bài đã tạo. Liên kết tới Materials mở nguồn hiện tại; đoạn trích lưu trong bài là snapshot lúc tạo.

Có tối đa 30 bộ còn lưu cho mỗi owner và 100 hành động trên một bộ. Xóa bộ giải phóng chỗ lưu nhưng giữ dấu request ID tối thiểu để yêu cầu tạo cũ không vô tình gọi model lại. Kho dấu yêu cầu tạo có trần 1.000/owner, không được đặt lại bằng cách xóa bài. Cookie không phải tài khoản khôi phục: mất cookie có thể mất quyền truy cập qua web.

Yêu cầu tạo có request ID, phạm vi cố định và lease 180 giây. Transaction đặt chỗ trước model; model chạy ngoài transaction. Gửi lại đúng request ID và phạm vi trả trạng thái hiện có, kể cả khi nguồn hoặc cấu hình model đã đổi. Yêu cầu đã lỗi, hết hạn hoặc bị xóa không tự gọi model lại. Muốn thử một lượt AI mới cần chủ động tạo yêu cầu mới.

Các hành động làm bài có request ID và expected_revision. Gửi lại cùng hành động không tăng số lần làm; tab cũ không được ghi đè bản mới. UI giữ bản nháp khi lỗi/xung đột, cho đọc bản đã lưu hoặc kiểm tra lại đúng yêu cầu. Không tự gửi lại model. Có tối đa một lượt tạo practice trong mỗi tiến trình web, không xếp hàng ngầm; đây chưa phải hệ thống hàng đợi nhiều worker.

## API và provider

- `GET /learn/api/practice/config`: cấu hình model công khai.
- `GET /learn/api/practice`: danh sách bộ của người học.
- `POST /learn/api/practice`: `request_id`, `collection_id`, `unit_ids`, `count`.
- `GET /learn/api/practice/<id>`: mở/tiếp tục bộ đã lưu.
- `POST /learn/api/practice/<id>/actions`: `action`, `payload`, `expected_revision`, `request_id`; hành động gồm review_answer, start, answer, hint, solution, next.
- `DELETE /learn/api/practice/<id>`: xóa bộ đã kết thúc tạo.

API giữ auth, ownership, Origin/CSRF và private headers hiện có. Draft chưa mở đáp án không gửi correct_option, giải thích, quote đáp án hoặc gợi ý chưa mở tới client. Trạng thái lỗi tạo đã được lưu trả dưới dạng `practice.status=failed`; lỗi dữ liệu yêu cầu, quyền và quota vẫn dùng HTTP error thích hợp.

`practice_generation.py` chuẩn bị và kiểm tra nguồn; `ChatResponder.generate_practice()` dùng adapter Ollama/Gemini hiện có với prompt JSON riêng. Provider chỉ nhận excerpt_id/text/origin và số câu, không nhận đường dẫn hệ thống, tên nguồn hoặc owner. Nội dung nguồn là dữ liệu không đáng tin cậy, không cấp quyền công cụ. Ollama không tự chuyển cloud; chọn Gemini ở cấu hình server sẽ gửi các đoạn mẫu tới dịch vụ đó.

Timeout transport không bảo đảm dừng tính toán phía provider. Schema sai hoặc thiếu nguồn làm bộ chuyển Failed; không tự gọi AI lần hai để sửa đầu ra. Tiếng Anh là ngôn ngữ yêu cầu cho câu hỏi; quote giữ nguyên ngôn ngữ nguồn. Chưa đánh giá độ đúng theo một ngân hàng câu hỏi chuẩn.

Riêng yêu cầu tạo Practice với Ollama truyền JSON Schema qua `format`, dùng nhiệt độ 0 để giảm lỗi định dạng. Schema cho phép đúng số câu đã yêu cầu hoặc mảng rỗng khi không đủ nguồn; mảng rỗng vẫn bị từ chối để không bắt đầu một bộ thiếu câu. Kiểm tra semantic/quote vẫn thực hiện ở server. Chat và phân loại file giữ cấu hình transport trước đó. Cách truyền schema dựa trên [tài liệu Structured Outputs của Ollama](https://docs.ollama.com/capabilities/structured-outputs); không tự gọi lại khi model/phiên bản không hỗ trợ.

## Kiểm chứng

Các kiểm thử nằm trong `tests/learning/test_practice_generation.py`, `tests/learning/test_practice_store.py`, `tests/integration/test_learning_practice_web.py` và `tests/integration/test_learning_practice_browser.py`. Dùng kho tạm và responder giả lập để kiểm tra hợp đồng, trạng thái, ownership, phục hồi và giao diện. Smoke model local trên tài liệu tổng hợp được ghi riêng; không cộng vào số kiểm thử tự động.

Kết quả hoàn tất: **277 kiểm thử khác nhau vượt qua** — 87 generation, 56 provider, 49 hồi quy đề xuất nhãn, 58 store, 14 API Practice, 1 cổng bảo vệ các route ghi, 9 Chromium Practice và 3 hồi quy Chromium cho Materials/Java/chat. Chỉ chạy lại ca bị ảnh hưởng sau sửa; không cộng lượt chạy chồng vào tổng. Đã sửa tràn điều hướng mobile khi thêm liên kết Practice và giữ riêng nhiều bản nháp khi tab khác chuyển câu trong lúc khôi phục request. Đã xem ảnh desktop/mobile, kiểm tra cú pháp Python/JavaScript và whitespace. Không chạy toàn repository.

Server local cổng 5055 đã được khởi động lại sau khi kiểm tra không có lượt model còn hiệu lực; trang Practice trả 200, config chỉ đúng Ollama `qwen3.5:4b`, API trả 404 đúng cho ID không tồn tại và script được phục vụ khớp file hiện tại. Không nhập dữ liệu kiểm thử vào kho bài giảng của người dùng.

Smoke `qwen3.5:4b` trên bốn đoạn OS tổng hợp: các lượt đầu bị từ chối do đầu ra chưa đạt hợp đồng (27,43 giây; lượt chẩn đoán 6,21 giây chỉ có một câu; sau prompt số lượng 22,00 giây JSON chưa hợp lệ). Sau khi thêm JSON Schema, một lượt **35,18 giây** tạo đúng ba câu về mutex, semaphore và ISR. Các quote khớp nguồn, bộ ở Draft và API chưa lộ đáp án. Đã đọc lại ba đáp án với đoạn nguồn tổng hợp; đây là smoke nhỏ, chưa đo tỷ lệ thành công với file thật hoặc bảo đảm mọi câu hỏi đều đúng/hữu ích.
