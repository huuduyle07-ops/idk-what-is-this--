# Phân loại file bài giảng

Bản đầu ngày 2026-10-28 bổ sung metadata cho từng file trong Materials. Nhãn giúp người học tìm và tổ chức tài liệu; nhãn không xác nhận nội dung đúng, mức độ khó hay khả năng của người học.

## Các trường

| Trường | Nội dung |
|---|---|
| Subject | Môn/lĩnh vực chính, tối đa 120 ký tự; có thể để trống. |
| Topics | Tối đa 5 chủ đề, mỗi chủ đề 80 ký tự. |
| Document role | Lecture, Exercises, Solutions, Reference, Syllabus hoặc Unknown. |
| Language | English, Chinese, Korean, Vietnamese, Mixed, Other hoặc Unknown. |
| Concepts | Tổng hợp từ các liên kết khái niệm đã gắn cho từng unit, kèm số unit hỗ trợ. |

Subject không mặc nhiên lấy từ tên bộ tài liệu: tên thư mục hoặc tên collection chưa phải môn học được xác nhận. AI được yêu cầu dùng tên chủ đề tiếng Anh và giữ nguyên code identifier; người dùng vẫn có thể sửa bằng ngôn ngữ của mình. Chưa có bảng alias hợp nhất tên tiếng Anh/Trung hay viết tắt ở cấp nhãn file.

Concepts tiếp tục thuộc graph ở cấp unit. Nhãn Topics của file không được sao chép xuống mọi trang/slide và không tạo quan hệ tiên quyết, nhân quả hay quan hệ cha/con. Sửa nhãn file không sửa nguồn, ghi chú ảnh hoặc graph.

## Luồng đề xuất và xác nhận

1. Chọn bộ tài liệu và file trong Materials, rồi xem/sửa các trường nhãn.
2. Bấm **Suggest labels** để gọi model được cấu hình cho chat. Chỉ thao tác này gọi model; tải trang, lọc và xác nhận thủ công không gọi AI.
3. Server lấy mẫu có giới hạn, tối đa 8 unit có chữ, mỗi đoạn tối đa 1.000 ký tự. Các unit được lấy trải đều; mẫu không bảo đảm bao phủ cả file. Với ảnh, chỉ dùng mô tả do người học viết, chưa nhận diện ảnh.
4. Model trả JSON đề xuất kèm trích đoạn hỗ trợ. Server kiểm tra cấu trúc, giới hạn, ID đoạn và quote có đúng nguyên văn trong mẫu hay không. Kiểm tra này không chứng minh suy luận của model đúng.
5. Bản **Suggested** được lưu riêng, giữ nguyên các nhãn **Confirmed** trước đó. Người học xem đoạn nguồn, đưa đề xuất vào biểu mẫu, chỉnh sửa rồi bấm **Confirm labels** để lưu. Có thể nhập nhãn thủ công khi model chưa được cấu hình hoặc không tạo được đề xuất.

Đề xuất chỉ trả về khi các trường có giá trị được gắn với trích đoạn hỗ trợ; thiếu bằng chứng có thể trả Unknown hoặc để trống. Văn bản không đọc được không được đoán từ tên file. Nội dung bài giảng được gửi như dữ liệu không đáng tin cậy, không phải chỉ dẫn hệ thống. Phản hồi sai định dạng bị từ chối, không tự gọi model lại để sửa.

Nếu mô tả ảnh đã thay đổi sau lúc đề xuất, snapshot cũ vẫn được giữ và được đánh dấu stale. Cần tạo lại đề xuất trước khi dùng nút áp dụng. Xác nhận nhãn thủ công không đồng nghĩa xác nhận độ đúng của nguồn.

## Lưu trữ và API

`core/learning/file_labels.py` lưu metadata trong `targeted_subject/<owner>/<collection_id>/labels.json`, tách khỏi manifest và bản trích xuất bất biến. Khóa file là SHA-256 source ID trong namespace owner + collection, không phải tên file. Đọc không tạo file mới. Ghi dùng file tạm và thay thế nguyên tử; lỗi metadata không bị coi là bộ nhãn rỗng để ghi đè.

- `GET /learn/api/materials/<collection_id>/labels`: các nhãn, đề xuất đang chờ, concepts tổng hợp và cấu hình công khai của model.
- `PUT /learn/api/materials/<collection_id>/sources/<digest>/labels`: nhãn người dùng xác nhận và `expected_revision`.
- `POST /learn/api/materials/<collection_id>/sources/<digest>/labels/suggest`: `expected_revision`; nguồn chỉ do server đọc.

Revision bảo vệ thay đổi giữa các tab. Kết quả model đến sau một thay đổi khác bị từ chối thay vì ghi đè. Xác nhận thủ công xóa đề xuất đang chờ. Mất phản hồi đề xuất cần tải lại nhãn để xem trạng thái; không tự gửi thêm một lượt AI. Có tối đa một lượt đề xuất đang chạy trong mỗi tiến trình web, không xếp hàng ngầm. Cơ chế khóa hiện tại phù hợp ứng dụng local một tiến trình; chưa phải điều phối tác vụ nhiều worker.

API dùng ownership cookie, auth, Origin/CSRF và private headers hiện có. Giới hạn nhãn/quote và việc dựng UI bằng textContent không thay thế việc người dùng xem lại chất lượng nhãn.

## Model và phạm vi hiện tại

Ollama được ưu tiên theo cấu hình chat; không tự chuyển sang Gemini. Nếu chọn Gemini rõ ràng ở server, các đoạn mẫu được gửi tới dịch vụ đó. Không gửi đường dẫn hệ thống, không tự tải model, không có coding tools hay bước train trên tài liệu. Giới hạn transport giữ nguyên adapter chat; timeout không bảo đảm model phía nhà cung cấp đã dừng tính toán.

Nhãn đã xác nhận phục vụ tìm/lọc file trong Materials. Chat vẫn truy xuất đoạn văn và liên kết khái niệm như trước; chưa dùng Subject/Topics để xếp hạng RAG hoặc sinh thêm cạnh trong bản đồ. Bước tiếp theo cần đo với file thật trước khi quyết định dùng metadata để chọn nguồn.

## Kiểm tra

Các kiểm thử tập trung nằm trong `tests/learning/test_file_labels.py`, `tests/learning/test_file_label_suggestions.py`, `tests/integration/test_learning_file_labels_web.py` và `tests/integration/test_learning_file_labels_browser.py`. Kho dữ liệu và responder trong kiểm thử được cô lập; không coi test giả lập là bằng chứng chất lượng phân loại.

Kết quả ngày 2026-10-28: **192 kiểm thử khác nhau vượt qua** — 61 lưu trữ nhãn, 49 đề xuất, 56 hồi quy provider, 11 API nhãn và 15 Chromium (7 nhãn mới, 6 upload/ảnh cũ, 2 liên kết nguồn). Lượt Chromium đầu có một lỗi thật ở việc cập nhật cảnh báo đề xuất sau khi lưu ghi chú ảnh; đã sửa và chạy lại ca đó thành công. Đã sửa class CSS chưa khớp ở form, chạy lại ca mobile và xem ảnh cuối. Các lượt chạy lại không được tính thêm vào tổng. Python/JavaScript qua kiểm tra cú pháp, diff qua kiểm tra whitespace. Không chạy toàn repository.

Server local cổng 5055 đã được khởi động lại sau khi kiểm tra không có lượt chat đang chờ còn hiệu lực. Trang Materials trả 200, script/CSS phục vụ khớp nội dung file hiện tại và API nhãn trả đúng 404 cho collection không tồn tại. Không nhập fixture vào kho bài giảng của người dùng.

Smoke local ngày 2026-10-28: `qwen3.5:4b` nhận 4 đoạn OS tổng hợp, trả Subject `Operating Systems`, Topics `synchronization`, `semaphores`, `mutexes`, `interrupt handling`, Role `lecture`, Language `English` trong **58,71 giây**. JSON và các quote qua kiểm tra, được lưu dưới dạng đề xuất chưa xác nhận. Đây là một mẫu nhỏ, chưa xác định trạng thái nạp model, không phải benchmark tốc độ/độ đúng trên file thật. Thời gian gần giới hạn transport 60 giây cho thấy còn cần đo và tối ưu độ trễ; không tự động chạy hàng loạt file.
