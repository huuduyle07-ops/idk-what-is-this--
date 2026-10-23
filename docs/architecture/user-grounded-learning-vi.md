# Teacher dựa trên bài giảng của người học

Mục tiêu: bắt đầu bằng trò chuyện về tài liệu của người học, rồi đề xuất một nhóm câu hỏi có mục đích rõ. Ưu tiên đúng phạm vi môn học và truy lại được nguồn trước khi mở rộng thành tutor tổng quát. Người dùng đã chọn PowerPoint, PDF và Word làm nguồn; chưa cung cấp file hoặc đường dẫn bài giảng thực tế.

## Phạm vi triển khai

Nền tảng nhập tài liệu cục bộ được đặt tại [`scripts/prepare_learning_materials.py`](../../scripts/prepare_learning_materials.py): nhận `.pptx`, `.pdf`, `.docx`, lưu bản sao nguồn và SHA-256 của byte nguồn; trích xuất thành đơn vị có vị trí, rồi chia đoạn với offset đối chiếu được trong văn bản đã trích xuất. Mỗi lần nhập phải qua trạng thái `review_required` trước khi được coi là tài liệu đã duyệt. Offset không phải vị trí byte trong file Office/PDF.

Trang **Tài liệu của tôi** tại `/learn/materials` đã hỗ trợ chọn hoặc kéo thả file/thư mục, đặt tên bộ tài liệu, nhập và xem lại từng trang/slide/đoạn/bảng. Thư mục con được duyệt trong trình duyệt; file không được hỗ trợ được báo bỏ qua. Chỉ gửi sau khi người dùng nhấn **Nhập tài liệu**, không tự đồng bộ thư mục. Nội dung trích xuất được hiển thị như văn bản cùng cảnh báo, không diễn giải thành HTML.

Đường nhập này xử lý cục bộ, giới hạn kích thước/số lượng đầu vào và độ dài văn bản, không gọi model. Chưa có sandbox giới hạn CPU/RAM cho parser PDF; chưa dùng bộ nhập này làm dịch vụ upload công khai. Nó chuẩn bị corpus để kiểm tra; chưa có hội thoại dựa trên nguồn, sinh câu hỏi hay nút xác nhận nguồn đã duyệt. [Teacher pilot hiện tại](teacher-pilot-vi.md) vẫn sử dụng ba bài Java soạn sẵn. Những mục hội thoại bên dưới là kế hoạch, không phải chức năng đã chạy.

Thư mục gốc [`targeted_subject/`](../../targeted_subject/README.md) đã được tạo và bỏ qua nội dung cá nhân trong Git. Bản nhập từ web nằm trong `targeted_subject/<owner>/<collection-id>/`; tên môn/chương và đường dẫn tương đối của file nằm trong metadata. Người dùng có thể đặt các thư mục môn học ở đây, nhưng cần chọn/kéo chúng vào trang để nhập; server không tự quét. Đường dẫn phía trình duyệt không được dùng làm đường dẫn ghi trên máy chủ. Các bộ tài liệu được phân tách theo cookie người học và giữ cơ chế xác thực, Origin/CSRF hiện có. Xóa/đổi cookie có thể mất liên kết truy cập qua web, không đồng nghĩa xóa dữ liệu trên đĩa.

Ví dụ cách nhập từ thư mục repository sau khi thay các đường dẫn bằng file thực tế:

```powershell
python scripts/prepare_learning_materials.py --title "Java OOP" --output .agent/learning/materials/java-oop --files "path/lecture.pptx" "path/notes.pdf" "path/handout.docx"
```

CLI chỉ nhập các file được chỉ định, không quét thư mục. Thư mục output phải chưa tồn tại. Giới hạn mặc định: 10 file, 20 MiB mỗi file, tổng 64 MiB. Trên web, mỗi cookie có tối đa 20 bộ và 256 MiB bản sao nguồn; giới hạn request là 65 MiB tính cả multipart, được kiểm tra trước khi đọc form. Lượt gửi lại cùng mã và nội dung trả về bộ đã nhập, tránh nhân đôi sau khi mất phản hồi. Output gồm `manifest.json` (hash nguồn, phiên bản extractor, cảnh báo, `review_required` trên từng nguồn), bản sao trong `sources/`, `units.jsonl`, `chunks.jsonl` và `preview.txt` để đọc toàn bộ chữ đã trích xuất cùng nhãn nguồn. Bản trùng byte cùng định dạng được gộp. Bản nhập web có thêm `web.json` để giữ đường dẫn tham chiếu và đối chiếu lượt gửi lại. Output không tự sinh câu hỏi hoặc tự được kích hoạt cho tutor.

Mỗi bundle có `grounding_ready: false`; đây là dữ liệu chờ xem lại, chưa có API chuyển sang đã duyệt. Bộ tiêu thụ tương lai phải từ chối thư mục thiếu manifest hoặc còn `IMPORT_INCOMPLETE`; thư viện web cũng không liệt kê bản thiếu metadata web. Nếu xảy ra lỗi ghi, thư mục chưa hoàn tất được giữ để kiểm tra, không ghi đè khi thử lại. File nguồn được sao chép đầy đủ vào bundle; `.agent/` và nội dung `targeted_subject/` đã nằm trong gitignore, nhưng bundle chưa được mã hóa riêng hoặc quản lý xóa qua UI. Nút xóa bài làm hiện tại chỉ xóa phiên học, không xóa kho bài giảng này. Khóa nhập hiện tại áp dụng trong một tiến trình; chưa thiết kế cho nhiều worker hoặc dịch vụ công khai.

## “Dataset” gồm những gì?

| Nhóm | Nội dung và vai trò | Ranh giới |
| --- | --- | --- |
| Corpus bài giảng | Bản nguồn, đơn vị trích xuất, đoạn văn, vị trí, cảnh báo và trạng thái duyệt | Là bằng chứng tham khảo; nhập tài liệu không đồng nghĩa huấn luyện model. |
| Ngân hàng câu hỏi | Mục tiêu, câu hỏi, họ bài, nguồn liên quan, đáp án, rubric, cách kiểm chứng và phiên bản | Tạo/duyệt riêng sau khi nguồn đạt yêu cầu. Đáp án và rubric nội bộ không nằm trong dữ liệu công khai gửi tới màn hình câu hỏi. |
| Hội thoại và bài làm | Câu hỏi của người học, câu trả lời, trợ giúp đã nhận, kết quả và nguồn được sử dụng | Tách khỏi corpus và lịch sử sửa code của agent; không tự trở thành đáp án chuẩn. |
| Dữ liệu huấn luyện | Tập ví dụ được chọn và cho phép sử dụng cho việc cập nhật model | Chưa cần cho bước này; không tự gom bài giảng hay bài làm vào tập huấn luyện. |

Ban đầu dùng file có cấu trúc và chức năng tra cứu đơn giản. Chưa cần graph tri thức, vector database hay framework nhiều agent mới để thử vòng học đầu tiên.

## Giữ đúng nội dung nguồn

- PowerPoint: giữ số slide và thứ tự văn bản đã trích xuất. Văn bản trong ảnh, sơ đồ, hiệu ứng và thứ tự đọc trực quan cần kiểm tra trên bản gốc; trích xuất được chữ không chứng minh đã hiểu slide.
- PDF: giữ số trang vật lý của file; không tự coi đó là số trang in trong bài giảng. Trang không trích được chữ được đánh dấu cần xem lại/OCR. Chưa tự nhận diện mọi trang scan hoặc trang có lớp chữ OCR kém; chưa nhận đã đọc được ảnh, công thức hay bố cục nhiều cột.
- Word: giữ vị trí đoạn văn và bảng trong tài liệu. Không bịa số trang vì phân trang phụ thuộc trình xem/font; nếu cần tham chiếu trang ổn định, dùng bản PDF tương ứng.
- `.ppt` và `.doc` cũ cần chuyển sang `.pptx`/`.docx` bằng ứng dụng phù hợp trước khi nhập. Bản chuyển đổi phải được xem lại; lưu quan hệ với bản gốc nếu sau này bổ sung quản lý phiên bản.
- OCR, đọc sơ đồ và công thức là bước bổ sung sau. Khi chưa xử lý được, ghi rõ phần thiếu và không tạo câu hỏi cần bằng chứng từ phần đó.

SHA-256 xác định đúng bản file đã nhập; nó không xác nhận tài liệu đúng, đầy đủ hay an toàn. Nguồn thay đổi tạo phiên bản mới; bài học đang làm phải giữ liên kết với phiên bản cũ thay vì âm thầm đổi đáp án.

Đợt duyệt đầu cần đối chiếu một số trang/slide chứa code, bảng, dấu tiếng Việt và hình quan trọng; loại phần mất ngữ cảnh khỏi phạm vi dạy. Đoạn chia nhỏ không được làm mất tiêu đề, điều kiện áp dụng hoặc ghi chú cần thiết để hiểu ví dụ.

## Học trong phạm vi môn học

Thiên hướng theo giáo trình là lựa chọn sản phẩm hợp lý khi được nói rõ: “Đang học theo tài liệu X, phiên bản Y”. Mỗi lời giải dựa trên nguồn cần chỉ tới trang/slide/đoạn phù hợp; người học có thể mở ngữ cảnh. Trích dẫn hỗ trợ kiểm tra, không tự bảo đảm diễn giải của tutor đúng.

Nếu hai tài liệu mâu thuẫn, tutor nêu hai phát biểu cùng vị trí và điều kiện áp dụng, rồi hỏi người học đang theo nguồn nào. Không lặng lẽ hợp nhất hoặc chọn nguồn có vẻ tự tin hơn. Nếu không đủ bằng chứng trong bài giảng, trả lời rằng nguồn chưa giải quyết được câu hỏi; kiến thức ngoài phạm vi chỉ được bổ sung khi được phân biệt rõ với nội dung môn học.

Với lập trình, khi ví dụ trong tài liệu khác kết quả thực thi, giữ lại mâu thuẫn và phiên bản/ngữ cảnh chạy để kiểm tra. Không chấm người học sai chỉ để khớp một slide có lỗi. Việc kiểm chứng code phải đi qua cơ chế thực thi được kiểm soát riêng, không thực thi tự động lúc nhập tài liệu.

Nội dung tài liệu, kể cả câu “bỏ qua hướng dẫn trước”, là dữ liệu trích dẫn. Nó không được sửa chính sách tutor, mở quyền công cụ, yêu cầu đọc file khác hay gửi dữ liệu đi. Bản nhập offline không có nghĩa luồng hội thoại tương lai cũng offline; trước khi nối LLM cần hiển thị cấu hình gửi dữ liệu và giới hạn phần nguồn được chuyển tới model.

## Phác thảo UI cho vòng học kế tiếp

1. **Chọn tài liệu** → xem tên, phiên bản, số đơn vị và cảnh báo → mở nguồn đối chiếu → xác nhận phần được dùng. Không gắn nhãn “sẵn sàng” chỉ vì parser chạy xong.
2. **Trò chuyện trước:** “Hôm nay bạn muốn hiểu điều gì trong tài liệu này?” Hiển thị phạm vi nguồn đang dùng; cho phép chọn slide/trang hoặc nhập đoạn code. Khung nguồn/code mở bên cạnh khi cần.
3. **Cùng làm rõ mục tiêu:** giải thích ngắn có tham chiếu, hỏi thêm khi cần và cho phép người học phản biện. Không ép đủ số lượt chat mới mở bài tập.
4. **Đề xuất 2–3 câu:** nói rõ sẽ kiểm tra điều gì, có nút **Thử ngay**, **Trao đổi thêm** và **Đổi mục tiêu**. Câu hỏi đã duyệt có thể được chọn trước; câu tự sinh phải qua kiểm tra riêng.
5. **Làm từng câu trong cùng phiên:** giữ chat và nguồn truy cập được. Ghi trợ giúp liên quan đến chính câu đang làm; không giấu lời giải trong HTML/JSON rồi chỉ che bằng giao diện.
6. **Nhìn lại bằng chứng:** nói cụ thể đã làm được bài nào, với trợ giúp gì, còn thiếu kiểm tra nào. Đề xuất bài vận dụng hoặc ôn sau; người học có thể dừng, xuất hoặc xóa dữ liệu theo phạm vi được hỗ trợ.

Lời giải thích trôi chảy trong chat và câu “tôi hiểu rồi” không tự nâng mức thành thạo. Được dạy một khái niệm trước đó không khiến mọi câu sau thành có trợ giúp; nếu chat đã tiết lộ cách giải/đáp án của chính câu hiện tại thì lần trả lời đó phải được ghi nhận có trợ giúp.

Đánh giá vận dụng cần một bài khác về tình huống hoặc cấu trúc suy luận, không chỉ đổi tên biến hay con số. Giữ một nhóm bài đánh giá chưa dùng trong hội thoại/luyện tập, tách theo họ bài để tránh rò rỉ đáp án; làm đúng một ví dụ chưa chứng minh nhớ lâu hoặc hiểu toàn bộ chủ đề.

## Kiểm tra nền tảng nhập liệu

Ngày 2026-10-23: **110 kiểm tra vượt qua**, gồm 98 kiểm tra nền tảng nhập tài liệu và 12 kiểm tra hồi quy Teacher/cổng bảo vệ hiện có. Chạy các file `tests/learning/test_document_extractors.py`, `test_materials.py`, `test_material_library.py`, `tests/integration/test_learning_materials_web.py`, `test_learning_materials_browser.py`, `test_learning_web.py` và test `test_every_mutating_route_is_decided_by_the_gate_before_its_handler` trong `tests/test_auth_web1.py`.

Các fixture tự tạo kiểm tra thứ tự trang/slide, Word có bảng xen đoạn văn, nguồn mã hóa/lỗi, liên kết slide không hợp lệ, giới hạn kích thước, hash/bản sao nguồn, offset, chống ghi đè, lỗi ghi giữa chừng và CLI chạy từ thư mục khác. Kiểm tra web bao gồm owner/auth/Origin/CSRF, đường dẫn tương đối, giới hạn body trước đọc form, lượt gửi lại và tài liệu nhiều đoạn trống. Giới hạn 32 MiB cho đơn vị nguồn đã được thống nhất giữa ghi/đọc, kiểm tra trước khi tạo bundle để không xuất hiện bản đã lưu nhưng không mở được.

Ba kiểm tra Chromium dùng kho tạm đã xác nhận chọn file, chọn thư mục con, kéo thả thư mục qua nhiều batch, hiển thị nội dung có HTML như văn bản, chuyển phần nguồn, tải lại, màn hình rộng 390 px và gửi lại sau khi server đã lưu nhưng phản hồi bị mất. Chưa có bài giảng thật của người dùng để đánh giá chất lượng trích xuất; chưa chạy lại toàn repository.

## Thứ tự thực hiện và điều kiện chuyển bước

| Bước | Kết quả cần có |
| --- | --- |
| 1. Nhập và xem lại nguồn | Nhập được một bộ bài giảng thật; mở lại đúng vị trí; cảnh báo phần thiếu và xác nhận phạm vi được sử dụng. |
| 2. Hội thoại có nguồn | Giải thích trong phạm vi đã duyệt; trích dẫn kiểm tra được; xử lý thiếu nguồn/mâu thuẫn và nội dung giả dạng chỉ dẫn. |
| 3. Nhóm câu hỏi nhỏ | Chọn câu hỏi/rubric đã duyệt, kiểm chứng đáp án, tách nội dung công khai khỏi đáp án; lưu trợ giúp cùng bài làm. |
| 4. Đánh giá vòng học | Thử với người học đầu tiên: câu trả lời có ích đến đâu, nguồn có đúng chỗ, có vận dụng được bài mới và phải chờ bao lâu. Ghi số liệu thực tế trước khi đặt mục tiêu hoặc thêm hạ tầng. |

Đầu vào còn cần từ người dùng là **một bộ bài giảng thực tế**, có thể kéo file/thư mục vào `/learn/materials`. Nếu tiện, bổ sung tên môn/chủ đề đang học và phần muốn ưu tiên; chưa cần chuẩn bị một bộ dữ liệu huấn luyện lớn. Bắt đầu với một chương nhỏ có cả văn bản, code và một vài hình/bảng để biết việc trích xuất đang thiếu gì.
