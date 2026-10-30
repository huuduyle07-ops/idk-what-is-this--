# Giữ hình và vị trí nguồn trước khi nối VLM

Bản đầu ngày 2026-10-29 thêm khung **Hình trong phần nguồn này** tại Materials.
Đây là bước lấy bản nhìn và giữ tham chiếu nguồn; chưa chạy OCR, phân loại sơ đồ,
đọc node/edge hoặc dùng ảnh làm đáp án cho Test Maker. Định dạng đã nhận không đồng
nghĩa toàn bộ nội dung của định dạng đó đã được hiểu.

## Luồng sử dụng

1. Mở một bộ tài liệu, chọn file và trang/slide/đoạn/bảng cần xem. Bộ cũ dùng được,
   không cần nhập lại chỉ để thấy khung hình nguồn.
2. **Chuẩn bị hình của phần này** tạo bản nhìn theo yêu cầu. Mở trang, chọn phần
   khác hoặc đọc lịch sử chỉ đọc trạng thái đã lưu, không tự render cả tài liệu.
3. Xem hình vừa khung hoặc phóng tới kích thước ảnh đã lưu. Trên mobile, ảnh phóng
   cuộn trong khung, không làm tràn toàn trang.
4. Đọc vị trí nguồn và cảnh báo. Mục **Thông tin nguồn chi tiết** giữ thông tin
   phần Office và vùng ảnh để đối chiếu; mặc định đóng.

| Nguồn | Phần đã giữ | Giới hạn hiện tại |
| --- | --- | --- |
| PDF | Render đúng trang được chọn bằng Poppler, gồm hình raster, đường vector và bố cục của trang. | Cần `pdftoppm` trong PATH; chưa tách riêng từng figure trên một trang. |
| PowerPoint `.pptx` | Bản render toàn slide được chọn, gồm cả sơ đồ vẽ bằng shapes/connectors, qua PowerPoint trên Windows. | Cần PowerPoint cục bộ và phần nguồn qua kiểm tra trước khi mở. Khi không render được, chỉ dùng ảnh PNG/JPEG nhúng nếu có và đánh dấu `partial`; slide chỉ có shapes không bị báo là đã lấy đủ hình. |
| Word `.docx` | PNG/JPEG nhúng trong đúng đoạn hoặc bảng của bộ trích xuất, cùng tên phần nguồn trong gói Office. | Chưa render toàn trang Word, chưa dựng lại sơ đồ vector và bố cục. Giữ chỉ số đoạn/bảng, không suy đoán số trang. |
| PNG/JPEG độc lập | Bản nhìn từ ảnh nguồn đã kiểm tra, gắn với vị trí ảnh 1. | Ảnh xem trước lớn được thu nhỏ; ảnh nguồn gốc và ghi chú người học giữ nguyên. |

Render PowerPoint dùng bản sao tạm chỉ đọc, không mở cửa sổ trình chiếu và không
ghi lên file gốc. Nếu PowerPoint của người dùng đang chạy thì không dùng chung
phiên ứng dụng để render; trả lý do chưa khả dụng hoặc ảnh nhúng có cảnh báo.
Chỉ đóng tài liệu tạm do bộ render mở. Vòng đời ứng dụng Office riêng được kiểm tra
tách khỏi kiểm thử giả lập; không đóng cửa sổ hoặc tài liệu của người dùng để chạy test.
Nếu render PowerPoint vượt 30 giây, phiên Office ẩn có thể còn giữ file tạm;
hệ thống báo lỗi và không tự đóng các phiên chưa xác minh, nên lần render sau có
thể cần chờ hoặc đóng phiên bị treo. Đây là giới hạn còn lại của nhánh COM.

Giới hạn bản nhìn: cạnh dài tối đa 1.800 pixel, tối đa 12 hình/phần và 16 MiB gồm
metadata. Quota hình lưu riêng là 64 MiB/bộ và 128 MiB/owner; tính cả các phần tạo
dở, không tính trùng một raster trong cùng bản ghi. Quota snapshot bài giảng hiện có
vẫn áp dụng riêng. PNG/JPEG được kiểm tra giải mã; không phục vụ SVG/HTML do nguồn
tự khai. Giới hạn và timeout không phải cam kết cách ly tuyệt đối parser bên ngoài.

## Provenance và lưu trữ

`core/learning/source_visuals.py` đọc/render nguồn theo locator. Bản nhìn giữ loại
capture, MIME, kích thước, locator, phần Office và vùng nguồn nếu xác định được.
Một `slide_render` là loại bản nhìn, chưa phải nhãn ngữ nghĩa “sơ đồ kiến trúc”.
Ảnh Word nhúng chưa có tọa độ trang được xác minh nên bbox để trống.

`source_visual_store.py` lưu riêng tại
`targeted_subject/<owner>/<collection>/visuals/<unit_id>/`. Bản ghi phiên bản
`source-visuals-v1` gắn source hash, unit ID, vị trí nguồn, UTC và hash raster.
Một ảnh xuất hiện ở các vị trí khác nhau giữ provenance riêng; raster trùng có
thể dùng chung file trong bản ghi. Không sửa manifest, units, chunks, nhãn hoặc
ghi chú ảnh cũ; không tự thêm thông tin vào graph hay RAG.

GET và đường xem ảnh kiểm lại nguồn và dữ liệu đã lưu. File nguồn bị thay thế,
ảnh hỏng hoặc metadata không khớp được báo lỗi; không tự ghi đè thành kho trống.
Prepare công bố cả thư mục hoàn chỉnh bằng rename sau khi kiểm tra dữ liệu và quota.
Lần gửi lại đọc bản đã công bố, không render lần nữa. Bản `partial` cũng là snapshot
được giữ; bản đầu chưa có thao tác thay thế snapshot đó bằng một lượt render mới.

Khóa và quota đồng bộ trong một process ứng dụng. Chưa tuyên bố bảo đảm đồng thời
giữa nhiều process/worker. Không tải tài nguyên ngoài từ liên kết trong Office để
render; không thực thi macro hoặc nội dung nhúng. DOCX được đọc thụ động, không
khởi động Word.

## API và UI

- `GET /learn/api/materials/<collection>/units/<unit>/visuals`: trạng thái
  `unprepared`, `ready` hoặc `partial`, cảnh báo và các bản nhìn đã lưu.
- `POST` cùng đường dẫn với body `{}`: chuẩn bị đúng phần nguồn; client không chọn
  đường dẫn máy chủ, model, câu hỏi hoặc hình học tùy ý.
- `GET .../visuals/<visual_id>/image`: raster riêng tư, kiểm tra owner và nguồn.

Giữ auth, cookie owner, Origin/CSRF và private headers hiện có. JS bỏ phản hồi của
nguồn vừa rời đi; khi mất xác nhận POST, đọc GET trước khi cho gửi lại. Lỗi bộ render
được giữ để người dùng biết nguyên nhân ngay cả khi bước phục hồi chưa tìm thấy ảnh.
Ghi chú ảnh cũ có luồng riêng và không bị khung hình nguồn thay thế.

## Kiểm tra và bước học tiếp

Các bộ kiểm thử mới: `tests/learning/test_source_visuals.py`,
`tests/learning/test_source_visual_store.py`,
`tests/integration/test_learning_source_visuals_web.py` và
`tests/integration/test_learning_source_visuals_browser.py`.
Kiểm thử parser/store/API dùng nguồn tổng hợp và kho tạm. PDF có kiểm tra render
thật đúng trang; kiểm tra UI dùng raster từ renderer giả lập để tách lỗi giao diện
khỏi khả năng của Office. Smoke PowerPoint thật chạy riêng khi môi trường cho phép.
Không lấy kiểm thử giả lập làm bằng chứng model hiểu sơ đồ.

Lộ trình [tự xây VLM từ tensor](../learning/vlm-from-zero-vi.md) nằm riêng với ứng dụng.
Bài đầu dùng NumPy và dữ liệu tổng hợp; chưa cài PyTorch, tải checkpoint hoặc train
trên bài giảng người dùng. Bước sản phẩm sau là chọn vùng figure, đề xuất cấu trúc
bằng VLM và đối chiếu trước khi dùng cho giải thích hoặc bài kiểm tra.

Hoàn tất ngày 2026-10-29: **140 kiểm thử khác nhau đạt** — 45 engine, 1 smoke
PowerPoint thật, 67 store, 15 API, 1 cổng bảo vệ route ghi, 7 Chromium mới và 4
hồi quy Materials/ghi chú ảnh/mobile. Năm ca symlink của store được bỏ qua do quyền
Windows; ca Office opt-in được chạy riêng và đạt, không tính lượt skip mặc định
của chính ca đó thành một khoảng chưa kiểm chứng. Không cộng các lượt chạy lại vào
tổng. Không chạy toàn repository.

Smoke Office tạo một PPTX chỉ có hai khối CPU/Memory và một connector, không có
ảnh trong `ppt/media`, rồi render hai lượt liên tiếp. Kiểm tra pixel và xem ảnh
xác nhận cả khối, chữ và đường nối; sau chạy không còn process PowerPoint thử nghiệm.
PDF có kiểm tra trang 2 khác trang 1; JPEG có kiểm tra hướng EXIF trước/sau thu nhỏ;
Word có ảnh nhúng cùng PAGE field và hyperlink không được thực thi. Phần browser
kiểm tra mất phản hồi, chuyển nguồn khi request còn chạy, lỗi bộ render, mobile
zoom và giữ ghi chú cũ.

Đã mở lại server cổng 5055 sau khi xác nhận không có lượt model đang chạy. Trang
Materials trả 200 với khung mới, script/CSS phục vụ khớp file hiện tại, API trả
JSON 404 riêng tư cho nguồn không tồn tại và thư mục tạm render ghi/đọc/dọn được.
Không thêm tài liệu fixture vào kho thật. Bài lab chạy độc lập: loss hồi quy mẫu
giảm từ 41 xuống khoảng 0.001242 sau 200 bước; đây là kiểm tra cơ chế cập nhật trên
dữ liệu train tổng hợp, không phải đánh giá khả năng VLM hoặc tổng quát hóa.
