# Teacher pilot: bài học Java đầu tiên

Trạng thái: đã có vòng học chạy được tại `/learn`. Đây là bản thử trải nghiệm Teacher với ba tình huống Java về kế thừa và chọn method khi chạy. Chưa phải tutor tổng quát cho repository bất kỳ, và chưa hoàn thành toàn bộ M1 trong [kế hoạch Teacher](tutor-learning-plan-vi.md).

Bổ sung 2026-10-28: [Practice từ bài giảng](learning-practice-vi.md) chạy riêng ở `/learn/practice`, tạo 3–5 câu từ các unit được chọn. Bài Java và đáp án soạn sẵn mô tả dưới đây giữ luồng riêng.

## Thử bài

Trong web app đang chạy, mở `/learn` hoặc chọn **Học cùng C.A.T.T.U.S** từ trang chính. Nhấn **Bắt đầu bài học**, đọc code và chọn dự đoán. Có thể viết thêm cách suy nghĩ, xin gợi ý từng bước hoặc xem lời giải rồi tiếp tục.

Để mở riêng bản thử cục bộ từ thư mục gốc repository, trong môi trường Python đã cài các dependency của dự án:

```powershell
$env:DB_ENABLED='false'
$env:INDEX_USE_EMBEDDINGS='false'
$env:ROUTER_USE_EMBEDDINGS='false'
$env:RETRIEVER_USE_DB='false'
$env:EMBEDDING_PROVIDER='off'
python -m flask --app web.app run --host 127.0.0.1 --port 5055 --no-debugger --no-reload
```

Mở `http://127.0.0.1:5055/learn`. Các biến trên chỉ áp dụng cho tiến trình chạy từ cửa sổ này. Nếu đã cấu hình xác thực web, đăng nhập theo cơ chế hiện có. Đây là cách chạy thử trên máy cá nhân, không phải cấu hình triển khai doanh nghiệp.

## Đã triển khai

- Giao diện tiếng Việt, đọc code có số dòng, chọn đáp án bằng bàn phím, bố cục thích ứng với màn hình nhỏ.
- Phản hồi sai đưa gợi ý trước; lời giải đầy đủ chỉ xuất hiện khi trả lời đúng hoặc chủ động yêu cầu xem.
- Ba tình huống liên tiếp, có bài vận dụng; đánh dấu các dòng code liên quan trong phản hồi/lời giải.
- Lưu đáp án, phần giải thích đã gửi và mức trợ giúp; tải lại trang để tiếp tục phiên gần nhất. Có tải bài làm dạng JSON và xóa phiên hiện tại.
- Phân biệt đúng ngay khi chưa dùng trợ giúp trong phiên, sai ở lần đầu và đúng sau trợ giúp. Xem lời giải rồi chuyển bài không được tính là đã trả lời.
- Lưu phiên bản nội dung/rubric cùng phiên học và nhật ký sự kiện. Sửa nội dung bài mới không âm thầm đổi bài đang học.
- Yêu cầu gửi lại sau lỗi mạng dùng cùng mã yêu cầu để tránh ghi nhận hai lần. Thao tác từ tab cũ bị từ chối nếu phiên đã thay đổi.
- Link chuyển sang không gian Coding hiện có. Decision độc lập chưa có giao diện; đánh giá hiện tại là luật theo rubric.

Luồng Teacher này không gọi model/API, không đọc repository được người học nhập vào, không chạy shell và không thực thi Java trong lúc học. Ba đoạn Java đã được biên dịch/chạy riêng để kiểm tra đáp án trước khi dùng cho bản thử.

## Dữ liệu và giới hạn đánh giá

Phiên nằm tại `.agent/learning/sessions.sqlite3` trên máy chạy web app, tách khỏi lịch sử Coding. Cookie ngẫu nhiên `HttpOnly`, `SameSite=Strict`, thời hạn 30 ngày gắn trình duyệt với các phiên học. Cookie này không thay thế xác thực web và không cấp quyền Coding.

Tải lại trang hoặc khởi động lại server vẫn giữ bài đã gửi nếu còn cookie và file dữ liệu. Xóa/hết hạn cookie, đổi trình duyệt hay dùng cửa sổ riêng tư có thể làm mất khả năng truy cập phiên cũ; chưa có tài khoản hoặc công cụ khôi phục/nhập lại JSON. UI hiện mở phiên gần nhất, chưa có danh sách chọn phiên cũ. Phần giải thích còn đang gõ chưa được lưu cho đến khi gửi đáp án.

Xóa phiên loại bỏ phiên, sự kiện và bản lưu phản hồi dùng cho gửi lại trong cơ sở dữ liệu của ứng dụng. Thao tác này không xóa bản JSON đã tải, bản sao lưu hay bảo đảm xóa vật lý trên mọi thiết bị lưu trữ. File dữ liệu chưa được mã hóa riêng bởi ứng dụng.

Hệ thống chỉ chấm lựa chọn theo rubric; phần giải thích tự viết chưa được chấm. Nó không biết người học có dùng tài liệu bên ngoài, nhớ đáp án từ phiên trước hay đoán đúng. Các nhóm kết quả có thể trùng nhau khi một câu sai ban đầu được làm đúng sau trợ giúp. Không suy ra mức thành thạo hoặc khả năng ghi nhớ dài hạn từ ba câu này.

Giới hạn hiện tại: tối đa 50 phiên mỗi định danh trình duyệt, 100 hành động mỗi phiên; API giới hạn kích thước yêu cầu. Đây là ràng buộc cho bản thử, chưa phải cơ chế quota nhiều người dùng hoặc bảo vệ dịch vụ công khai.

## Các phần mã nguồn

| Phần | Trách nhiệm |
| --- | --- |
| [`core/learning/lesson.py`](../../core/learning/lesson.py) | Nội dung bài, rubric, gợi ý và dòng code làm bằng chứng. |
| [`core/learning/store.py`](../../core/learning/store.py) | Trạng thái học, lưu SQLite, phân biệt mức trợ giúp, phiên bản và gửi lại yêu cầu. |
| [`web/routes/learning_routes.py`](../../web/routes/learning_routes.py) | API, định danh phiên học và ranh giới truy cập. |
| [`web/templates/learn.html`](../../web/templates/learn.html), [`learn.js`](../../web/static/learn.js), [`learn.css`](../../web/static/learn.css) | Trải nghiệm học và phục hồi sau lỗi. |
| [`tests/learning/`](../../tests/learning/), [`test_learning_web.py`](../../tests/integration/test_learning_web.py), [`test_learning_browser.py`](../../tests/integration/test_learning_browser.py) | Kiểm tra trạng thái, API và luồng người dùng trên Chromium. |

## Bằng chứng kiểm tra

- **46 kiểm tra vượt qua** với `python -m pytest tests/learning tests/integration/test_learning_web.py tests/integration/test_learning_browser.py -q --disable-warnings`.
- **4 kiểm tra xác thực web hiện có vượt qua**: nguồn yêu cầu khác host/port, cổng kiểm soát mọi route thay đổi dữ liệu, không đưa token vào HTML và vòng đăng nhập/CSRF/khởi động lại. Chạy chọn lọc từ `tests/test_auth_web1.py`.
- Chromium kiểm tra vòng sai → gợi ý → sửa đúng, tiếp tục sau tải lại, xuất/xóa dữ liệu thử, màn hình rộng 390 px, bàn phím và trường hợp server ghi nhận nhưng phản hồi bị mất. Dữ liệu kiểm thử dùng cơ sở dữ liệu tạm, tách khỏi bài học của người dùng.
- Cả ba đoạn Java biên dịch và chạy thành công bằng JDK 26.0.2.1 đã cài trên máy; đầu ra khớp rubric. JDK không phải điều kiện để sử dụng giao diện bài học này.

Đây là kiểm tra cho phần Teacher và các ranh giới tích hợp liên quan; không phải lần chạy lại toàn bộ repository hoặc xác nhận an toàn doanh nghiệp. Chưa đo hiệu quả học thật, độ trễ ở tải nhiều người dùng hay chất lượng dạy bằng LLM.

## Sau buổi học đầu tiên

Ưu tiên quan sát xem người học hiểu câu hỏi, tự giải thích được lựa chọn và vận dụng sang bài khác đến đâu. Ghi lại nơi phải đoán ý giao diện hoặc nơi phản hồi chưa giúp hiểu. Sau đó sửa nội dung và nhịp tương tác trước khi mở rộng chủ đề.

Bước tiếp theo của Teacher là bài ôn mới ở lần học sau và hội thoại giải thích có giới hạn rõ. Dạy trên code repository cần thêm nguồn code có phiên bản, rubric phù hợp và kiểm chứng riêng. Chỉ đưa mô hình đánh giá/thích nghi vào khi có dữ liệu đủ để so với cách chấm đơn giản hiện tại.
