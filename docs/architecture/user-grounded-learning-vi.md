# Teacher dựa trên bài giảng của người học

Mục tiêu: bắt đầu bằng trò chuyện về tài liệu của người học, rồi đề xuất một nhóm câu hỏi có mục đích rõ. Ưu tiên đúng phạm vi môn học và truy lại được nguồn trước khi mở rộng thành tutor tổng quát. Người dùng đã chọn PowerPoint, PDF và Word làm nguồn, sau đó bổ sung nhu cầu giữ hình ảnh/sơ đồ để học.

## Phạm vi triển khai

Bản [chat tại `/learn/chat`](learning-chat-vi.md) có lưu hội thoại và trình bày giải thích/code/bảng, ưu tiên Ollama. Người học chọn kiến thức chung hoặc một bộ bài giảng cố định cho hội thoại mới. Chat theo bài giảng truy xuất từ khóa, giữ snapshot các đoạn đã gửi và hiển thị nguồn để đối chiếu; chưa có tìm kiếm ngữ nghĩa hay kiểm chứng diễn giải tự động.

Nền tảng nhập tài liệu cục bộ được đặt tại [`scripts/prepare_learning_materials.py`](../../scripts/prepare_learning_materials.py): nhận `.pptx`, `.pdf`, `.docx`, `.png`, `.jpg` và `.jpeg`, lưu bản sao nguồn và SHA-256 của byte nguồn; tài liệu chữ được trích xuất thành đơn vị có vị trí, rồi chia đoạn với offset đối chiếu được trong văn bản đã trích xuất. Mỗi lần nhập phải qua trạng thái `review_required` trước khi được coi là tài liệu đã duyệt. Offset không phải vị trí byte trong file Office/PDF.

Trang **Tài liệu của tôi** tại `/learn/materials` đã hỗ trợ chọn hoặc kéo thả file/thư mục, đặt tên bộ tài liệu, nhập và xem lại từng trang/slide/đoạn/bảng. Thư mục con được duyệt trong trình duyệt; file không được hỗ trợ được báo bỏ qua. Chỉ gửi sau khi người dùng nhấn **Nhập tài liệu**, không tự đồng bộ thư mục. Nội dung trích xuất được hiển thị như văn bản cùng cảnh báo, không diễn giải thành HTML.

Ảnh PNG/JPEG độc lập đã có xem vừa khung/kích thước gốc và mô tả do người dùng viết. Kiểm tra signature, định dạng và giải mã bằng Pillow; giới hạn 12 triệu pixel, 10.000 pixel mỗi chiều, một khung hình và 20 MiB/file. APNG/MPO nhiều khung bị từ chối. `.jpg`/`.jpeg` cùng nội dung được gộp, bản gốc được giữ nguyên byte. Đường xem ảnh yêu cầu đúng cookie người học và quyền truy cập hiện có, kiểm tra hash trước khi trả ảnh, không công khai cả thư mục nguồn. Ảnh không có OCR mang trạng thái `needs_visual_review`, không bị coi là nguồn rỗng hoặc nguồn đã hiểu.

Mô tả giới hạn 4.000 ký tự, lưu riêng trong `annotations.json` với `origin: user` và revision, không sửa manifest/chunks/ảnh gốc hoặc tự kích hoạt tutor. Ghi nguyên tử và kiểm tra revision ngăn tab cũ ghi đè bản mới; gửi lại đúng nội dung sau khi mất phản hồi không tăng revision lần nữa. UI giữ bản đang viết khi lỗi, chặn chuyển nguồn khi chưa giải quyết ghi chú và cho đọc/đối chiếu bản đã lưu trước khi thay thế. Đây chưa phải lịch sử ghi chú nhiều phiên bản hoặc cơ chế phối hợp nhiều worker.

Chưa chạy OCR, chưa diễn giải sơ đồ bằng model, chưa trích ảnh nhúng hoặc render toàn trang PDF/Office. Bước kế tiếp là bản xem trang PDF giữ cả hình và ngữ cảnh, sau đó OCR/diễn giải trên phần được chọn. Nội dung ảnh gốc, chữ OCR và lời diễn giải phải tách nguồn gốc; lời diễn giải chưa duyệt không tự thành đáp án chuẩn.

Đường nhập này xử lý cục bộ, giới hạn kích thước/số lượng đầu vào và độ dài văn bản, không gọi model. Chưa có sandbox giới hạn CPU/RAM cho parser PDF; chưa dùng bộ nhập này làm dịch vụ upload công khai. Chat có thể dùng bản trích xuất theo lựa chọn rõ ràng của người học, luôn giữ cảnh báo chưa duyệt. Chưa có sinh/chấm câu hỏi từ tài liệu hay nút xác nhận nguồn đã duyệt. [Teacher pilot hiện tại](teacher-pilot-vi.md) vẫn sử dụng ba bài Java soạn sẵn. Các mục bên dưới là thiết kế dài hạn; phạm vi thực chạy theo tài liệu chat được liên kết ở trên.

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

Corpus tiếp tục dùng file có cấu trúc. Lớp liên kết nhỏ dưới đây tận dụng biểu diễn graph hiện có; chưa thêm vector database hay framework nhiều agent để thử vòng học đầu tiên.

## Liên kết nguồn và khái niệm

`core/learning/knowledge_graph.py` dùng lại `graph.schema.ProgramGraph` để trả về một graph nhỏ quanh phần nguồn đang xem. Cấu trúc gồm **nguồn → trang/slide/đoạn/bảng/ảnh → khái niệm**. Quan hệ `contains` được lấy từ corpus; quan hệ `related_to_concept` do người dùng gắn và có `origin: user`, `status: user_confirmed`. Gắn khái niệm chỉ xác nhận một liên hệ, không duyệt nguồn hoặc đánh giá mức hiểu của người học.

Trong `/learn/materials`, mục **Khái niệm liên quan** cho gắn/bỏ nhãn trên phần nguồn hiện tại. **Nguồn liên quan** liệt kê các phần cùng khái niệm và mở đúng nguồn, đúng vị trí khi chọn. Nhãn được chuẩn hóa Unicode, khoảng trắng và chữ hoa/thường, giữ dấu tiếng Việt. Một bộ tài liệu là một phạm vi khái niệm: cùng tên ở hai bộ không tự hợp nhất. Nhập lại file thành bộ mới cũng chưa tự chuyển nhãn.

Từ 2026-10-26, chat theo bài giảng có **Concept map** tương tác ở cấp bộ tài liệu: bấm nút để đọc nguồn, lọc nút, tô sáng khái niệm chung một phần nguồn và điền câu hỏi tiếng Anh. Nhãn khái niệm vẫn do người dùng gắn, chưa tự khai thác bằng AI. Liên kết từ sơ đồ mở đúng collection/unit trong Materials. Chat nhận diện tên nhãn chính xác để dùng nguồn đã gắn, kể cả alias như ISR. Xem [phạm vi và giới hạn hiện tại](learning-chat-vi.md).

SQLite tại `targeted_subject/<owner>/knowledge.sqlite3` chỉ giữ khái niệm, liên kết và revision; bản sao nguồn, manifest, units và chunks không bị sửa. Đọc không tạo database. Ghi dùng transaction và kiểm tra revision để hai tab không âm thầm ghi đè nhau; gửi lại cùng tập nhãn sau khi mất phản hồi có thể trả bản đã lưu. Nhãn gỡ khỏi mọi phần sẽ được dọn khỏi chỉ mục. Đây chưa phải lịch sử chỉnh sửa có thể khôi phục.

Giới hạn: 12 nhãn/phần, 80 ký tự/nhãn, 500 khái niệm và 5.000 liên kết/bộ. Truy vấn trả tối đa 30 nguồn liên quan, mỗi trích đoạn tối đa 300 ký tự; ưu tiên số khái niệm chung rồi thứ tự nguồn. Graph chỉ gồm phần đang xem và các kết quả đó. API đọc/ghi giữ phân tách người học, auth và Origin/CSRF hiện có; dữ liệu không đi vào cache graph của coding harness.

Chưa tự suy ra quan hệ tiên quyết, đồng nghĩa, mâu thuẫn hay mức thành thạo; chưa tự gắn nhãn bằng AI. `grounding_ready` vẫn là `false`. Lớp liên kết không khôi phục hình nhúng còn thiếu và chưa tạo bài học/câu hỏi từ nguồn. Bước tích hợp tiếp theo là chọn phạm vi đã kiểm tra để hội thoại có thể dẫn lại đúng nguồn.

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

Cập nhật 2026-10-24 cho liên kết khái niệm: **112 kiểm tra vượt qua, 4 bỏ qua** trong lượt tích hợp này: 30 kiểm tra domain graph, 13 API graph, 58 hồi quy API tài liệu/ảnh/Teacher, 1 cổng bảo vệ mọi route ghi và 10 Chromium (4 graph mới, 6 nhập liệu/ảnh hiện có). Bốn kiểm tra symlink bị bỏ qua vì Windows không cho tạo symlink; kiểm tra đường database/sidecar bị chiếm bởi thư mục và lỗi truy cập vẫn chạy. Không chạy lại toàn repository.

Các kiểm tra graph xác nhận phân tách owner/bộ tài liệu, liên kết đúng bản nguồn và vị trí của PDF/PPTX/DOCX/ảnh, đọc không ghi, giới hạn kết quả, transaction/quota, gửi lại, hai lượt ghi cạnh tranh và bỏ/gắn lại nhãn. Chromium kiểm tra chuyển đúng đoạn Word ↔ ảnh, giữ ghi chú chưa lưu, hiển thị nhãn giống HTML như văn bản, màn hình 390 px, xung đột hai tab có đối chiếu, mất phản hồi sau khi server lưu và phản hồi đọc đến muộn không thay phần đang xem. Đây là kiểm tra kết nối và thao tác, chưa đánh giá chất lượng học hoặc tốc độ trên thư viện lớn.

Cập nhật 2026-10-24 cho ảnh độc lập: **153 kiểm tra vượt qua** trong phạm vi nhập liệu/Teacher liên quan (67 extractor, 80 kiểm tra corpus/thư viện/API ảnh/API tài liệu/Teacher/cổng bảo vệ, 6 Chromium). `tests/integration/test_learning_images_web.py` kiểm tra ảnh gốc và MIME, quyền xem, hash nguồn, JPEG alias, ghi chú tách nguồn, revision/retry, dữ liệu sai và lỗi ghi. Ba kiểm tra ảnh trong browser bổ sung xem PNG/JPEG thật, zoom, ghi chú có nội dung giống HTML vẫn là dữ liệu, mở lại, xung đột hai tab và mất phản hồi sau khi lưu. Các fixture đều tự tạo trong kho tạm; chưa đánh giá khả năng đọc hiểu sơ đồ hoặc chất lượng học từ bài giảng thật. Phần ghi chú và ảnh không gọi model.

Ngày 2026-10-23: **110 kiểm tra vượt qua**, gồm 98 kiểm tra nền tảng nhập tài liệu và 12 kiểm tra hồi quy Teacher/cổng bảo vệ hiện có. Chạy các file `tests/learning/test_document_extractors.py`, `test_materials.py`, `test_material_library.py`, `tests/integration/test_learning_materials_web.py`, `test_learning_materials_browser.py`, `test_learning_web.py` và test `test_every_mutating_route_is_decided_by_the_gate_before_its_handler` trong `tests/test_auth_web1.py`.

Các fixture tự tạo kiểm tra thứ tự trang/slide, Word có bảng xen đoạn văn, nguồn mã hóa/lỗi, liên kết slide không hợp lệ, giới hạn kích thước, hash/bản sao nguồn, offset, chống ghi đè, lỗi ghi giữa chừng và CLI chạy từ thư mục khác. Kiểm tra web bao gồm owner/auth/Origin/CSRF, đường dẫn tương đối, giới hạn body trước đọc form, lượt gửi lại và tài liệu nhiều đoạn trống. Giới hạn 32 MiB cho đơn vị nguồn đã được thống nhất giữa ghi/đọc, kiểm tra trước khi tạo bundle để không xuất hiện bản đã lưu nhưng không mở được.

Ba kiểm tra Chromium ban đầu dùng kho tạm đã xác nhận chọn file, chọn thư mục con, kéo thả thư mục qua nhiều batch, hiển thị nội dung có HTML như văn bản, chuyển phần nguồn, tải lại, màn hình rộng 390 px và gửi lại sau khi server đã lưu nhưng phản hồi bị mất. Các kết quả này không thay cho đánh giá chất lượng trích xuất trên bài giảng thật; chưa chạy lại toàn repository.

## Thứ tự thực hiện và điều kiện chuyển bước

| Bước | Kết quả cần có |
| --- | --- |
| 1. Nhập và xem lại nguồn | Nhập được một bộ bài giảng thật; mở lại đúng vị trí; cảnh báo phần thiếu và xác nhận phạm vi được sử dụng. |
| 2. Hội thoại có nguồn | Giải thích trong phạm vi đã duyệt; trích dẫn kiểm tra được; xử lý thiếu nguồn/mâu thuẫn và nội dung giả dạng chỉ dẫn. |
| 3. Nhóm câu hỏi nhỏ | Chọn câu hỏi/rubric đã duyệt, kiểm chứng đáp án, tách nội dung công khai khỏi đáp án; lưu trợ giúp cùng bài làm. |
| 4. Đánh giá vòng học | Thử với người học đầu tiên: câu trả lời có ích đến đâu, nguồn có đúng chỗ, có vận dụng được bài mới và phải chờ bao lâu. Ghi số liệu thực tế trước khi đặt mục tiêu hoặc thêm hạ tầng. |

Với bộ bài giảng đã nhập, bước thử tiếp theo là **chọn một chương nhỏ**, đối chiếu phần chữ/code/hình quan trọng và gắn vài khái niệm chung để kiểm tra việc nối nguồn. Chưa cần chuẩn bị một bộ dữ liệu huấn luyện lớn. Các phần đã kiểm tra sẽ làm đầu vào cho hội thoại có nguồn ở bước sau.
