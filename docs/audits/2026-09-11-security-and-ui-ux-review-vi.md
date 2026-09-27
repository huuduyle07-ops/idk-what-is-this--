**C.A.T.T.U.S — rà soát lỗ hổng còn lại và UI/UX, 11/09/2026**

Project vẫn còn các lỗi đáng ưu tiên trước khi giao codebase quan trọng hoặc dùng chung trong nhóm. UI/UX cần polish, trước hết ở tính đúng đắn của trạng thái, sự rõ ràng của quyền Apply và độ ngắn của luồng coding. Giao diện hiện tại có nhiều thành phần hữu ích, nhưng người dùng phải hiểu quá nhiều khái niệm nội bộ trước khi chạy một tác vụ đơn giản.

Đây là đợt audit bổ sung, **chưa sửa mã sản phẩm**. Không chạy lại toàn bộ 58 ca của đợt khắc phục trước, không gọi model thật hay DB. Những lỗi cũ chỉ được đối chiếu source; các phát hiện mới có probe riêng. Bằng chứng đầy đủ, source hash và nội dung script tái hiện được lưu trong [JSON của đợt này](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-11-security-and-ui-ux-results.json). Các báo cáo lịch sử được giữ nguyên.

**Các lỗi mức P1 cần xử lý trước**

| ID | Phát hiện và bằng chứng | Cần thay đổi |
|---|---|---|
| SEC-01 | **Evidence viewer thực thi JavaScript trong report.** Mở Markdown tổng hợp qua UI thật đã chạy `onerror`; payload chỉ đánh dấu chính ảnh thử nghiệm, không gửi dữ liệu hay gọi mutation. Backend giữ raw HTML và frontend chèn bằng `innerHTML`. Local Critique có một đường tương tự: output model vào HTML nguyên văn; đường này đã xác minh bằng handler thật với DOM/fetch giả lập, chưa thực thi riêng trên browser. | Escape dữ liệu dạng text; dùng renderer/sanitizer allowlist cho Markdown. Kiểm tra cả thuộc tính sự kiện và URL nguy hiểm. Cô lập các renderer, thêm CSP như lớp bổ trợ. |
| DATA-01 | **Undo có thể phục hồi backup của repo khác.** HTTP Undo cho B/app.py đã chép nội dung backup A/app.py sang B và xóa backup A. Probe seed backup theo đúng format production; không gọi model/Apply để tạo backup. Namespace backup hiện thiếu repository/run identity. | Định danh backup bằng repo canonical + đường dẫn không collision + transaction/run; Undo nhận đúng backup ID, kiểm tra phiên bản file và phục hồi theo byte. |
| EXEC-01 | **Plan sai kiểu có thể ghi một phần rồi trả HTTP 500.** Operation đầu tạo file thành công; operation thứ hai có `op: 7` làm `.strip()` ném lỗi ngoài đường rollback. File đầu vẫn tồn tại, response không phải JSON. | Validate toàn bộ schema trước mutation; bao toàn transaction bằng xử lý exception có rollback; mọi đường thất bại phải trả trạng thái và liệt kê file còn thay đổi. |
| AUTH-01 | **Dream Apply không gắn với đúng report vừa review.** Xem item 1 của run A, tạo run B mới rồi Apply `selection=1`: server chọn item 1 của B, ghi `unreviewed.txt`, nhưng receipt nói người dùng đã duyệt “exact candidate”. Probe dùng artifact giả, Apply và pytest thật; Git được chặn tìm lên repo cha bằng ceiling, không commit. | Gửi report/run ID và fingerprint của đúng candidate đã review; server kiểm lại identity/content trước ghi. Không tự chuyển sang `latest`; artifact thay đổi phải yêu cầu review lại. |
| DATA-02 | **Rollback lỗi nhưng receipt vẫn báo đã rollback.** Khi giả lập `PermissionError` đúng bước restore, file vẫn giữ bản sửa nhưng result có `rollback_performed=true`, `patch_ops_rollback_protected=true`; lỗi restore chỉ được print. | Phân biệt attempted/completed/failed; trả lỗi và đường dẫn chưa phục hồi, kiểm chứng byte/hash sau restore; giữ backup để phục hồi và hiện trạng thái cần can thiệp. |

Nguồn SEC-01: [Markdown renderer](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:2159), [Evidence HTML sink](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:8749), [Local Critique sink](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:10043), [model fields](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/agents/ollama_client.py:174). Điều kiện khai thác là người dùng mở report/nội dung model có HTML không tin cậy; không phải mọi report hiện tại đều độc hại. Payload Evidence đã thực thi trong origin ứng dụng, nhưng audit không thử đánh cắp dữ liệu hay thực hiện thao tác ghi qua payload.

Nguồn DATA-01: [Undo route](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:646), [nơi tạo backup](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/routes/patch_routes.py:219). Đây là lỗi khác với `.bak` cố định của patch engine trong audit cũ.

Nguồn EXEC-01: [parse operation sau khi đã bắt đầu ghi](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_plan_executor.py:331). Đây là malformed input gây partial write; không chứng minh vượt path safety để ghi ra ngoài repo.

Nguồn AUTH-01: [Dream chọn latest tại Apply](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:937), [thực thi candidate vừa đọc lại](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:1049). Các gate ở đường coding chính không tự bảo vệ đường Dream này.

Nguồn DATA-02: [rollback nuốt exception](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_plan_executor.py:93), [metadata mặc định](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/validation_side_effects.py:63). Đây là fault injection có chủ đích, không phải khẳng định máy người dùng đang có lỗi quyền ghi.

**Các lỗi P2 về truy cập và trải nghiệm**

| ID | Điều đã xác minh | Hướng xử lý |
|---|---|---|
| SEC-02 | Origin gate bỏ port/scheme và coi localhost tương đương 127.0.0.1. Khi token tắt, POST từ origin localhost:7999 hoặc 127.0.0.1:7999 đến localhost:5000 đã tạo Dream reference thật; hostname không liên quan bị 403. | So đầy đủ scheme/host/effective port theo allowlist; xử lý Origin thiếu/sai một cách có chủ đích; thêm CSRF cho UI local. Chưa chứng minh website Internet bất kỳ tấn công được localhost. |
| UX-01 | Bật WEB_AUTH_TOKEN thì GET vẫn mở UI, nhưng form POST không mang token bị 401; đối chứng có header đúng được 200. Source frontend không có transport token. | Cung cấp luồng xác thực UI phù hợp và transport thống nhất. Không giải quyết bằng cách tắt auth hoặc nhúng secret vào HTML công khai. Probe là HTTP + source, chưa hoàn tất lần submit qua browser với token bật. |
| UX-02 | Generate A → đổi repo B → Generate B → B trả trước, A trả sau: UI đang ở B nhưng hiển thị patch A. Handler JS thật đã tái hiện với response giả lập. | Gắn response với request/repo/run; bỏ response cũ, clear candidate khi đổi context. Chưa chứng minh vượt backend Apply gate. |
| UX-03 | Undo trả `success:false` nhưng frontend vẫn ghi `last_action=undone`. | Chỉ xác nhận Undo khi backend báo thành công; giữ trạng thái failed và chỉ dẫn phục hồi khi không có backup. |
| UX-04 | `Full + Ask → Chat → Instant Run` thành `Retrieve + Plan`, trong khi nút vẫn ghi Run. | Lưu cấu hình theo mode, phục hồi có chủ đích và hiển thị hành vi/quyền thực thi ngay cạnh nút chính. |
| UX-05 | Khi thiếu Mermaid do CDN không tải, toàn inline script ném `mermaid is not defined`; patch state chưa được khởi tạo. Xác minh bằng JS thật trong VM, không phải browser ngắt mạng. | Bundle local hoặc lazy-load Graph, guard lỗi và tách startup coding khỏi Graph. Đây là lỗi phụ thuộc/fallback, không phải kết luận về CVE. |
| UX-06 | Tab không active được đặt `tabindex=-1`, nhưng không có Arrow/Home/End handler tương ứng; modal chưa có vòng đời focus đầy đủ. Đây là kiểm tra source, chưa phải audit accessibility toàn diện. | Chuẩn hóa keyboard navigation, focus trap/restore và tên truy cập cho control; kiểm tra bằng bàn phím thật. |

Nguồn: [Origin gate](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/auth_gate.py:40), [token gate](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/auth_gate.py:95), [form](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:80), [Generate](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:9742), [Undo response](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:9824), [mode switch](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:2251), [Mermaid startup](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:2293), [tab focus](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/templates/index.html:6124).

**UI cần gọt ở đâu**

Trên trang mới, viewport 1280×720, nút Run ở khoảng **y=1.310 px**, dưới màn hình đầu gần hai lần chiều cao viewport. Ở 390×844, sau đưa scroll về 0, nút ở **y=2.393 px**. Layout có 47 control đang được bố trí hiển thị trên toàn trang desktop; đây không phải số control cùng nằm trong viewport. Màn hình hẹp không có overflow ngang đáng kể trong phép đo, nhưng người dùng phải đi qua sidebar và nhiều thẻ hướng dẫn trước khi chạy.

![Giao diện desktop hiện tại](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/assets/2026-09-11-ui/desktop.png)

Ảnh bổ sung: [màn hình hẹp](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/assets/2026-09-11-ui/narrow.png). Đều là dữ liệu thử riêng, không chứa repo/session thật của người dùng.

1. **Rút màn hình đầu còn repo + yêu cầu + Run + quyền ghi.** Đưa nút chính sát ô nhập; mặc định chỉ cần người dùng diễn đạt việc muốn làm. Project tag, engine mode, reviewer/planner và environment nằm trong tùy chọn khi cần.
2. **Thu gọn 4W1H thành phần trợ giúp tùy chọn.** Năm thẻ hiện là văn bản hướng dẫn, không phải các trường nhập, nhưng chiếm phần lớn chiều cao. Giữ Goal Brief Builder cho tác vụ cần làm rõ thay vì đặt toàn bộ lời giải thích trên mọi lượt chạy.
3. **Giảm lớp chọn mode.** Sidebar Chat/Instant, Mode Preview, Ask/Preview Run và dropdown Retrieve/Deep/Control/Full tạo nhiều cách gọi cho hành vi liên quan. Cho người dùng thấy một mục đích chính và quyền Apply; routing kỹ thuật nằm trong phần chi tiết.
4. **Bỏ copy nội bộ khỏi luồng chính.** Các câu “Visual integration only; existing behavior is preserved”, tên phase, cờ server và thông báo về route không giúp khách hàng quyết định tác vụ. Chuyển chúng sang tài liệu/debug. Giữ thông tin thiết thực: đọc hay ghi, file nào, đang kiểm chứng gì, bước tiếp theo.
5. **Đặt kết quả, diff và bằng chứng test ở trung tâm Review.** Cho thấy “đã thay đổi/chưa thay đổi”, pass/fail/inconclusive, rollback thành công hay cần phục hồi. Nhãn `safe` từ path checks nên nói rõ phạm vi kiểm tra; confidence của model không thay bằng chứng test.
6. **Cải thiện trải nghiệm chờ bằng job thật.** Luồng POST chính còn đồng bộ, progress polling mặc định tắt — đây là phát hiện cũ được đối chiếu source, không đo lại latency. Cần nhận job nhanh, có run ID trước khi chờ, elapsed time, bước đang chạy, trạng thái qua reload và Stop gắn với backend/process thật. Không thể chữa bằng thanh tiến độ giả.

Phần đáng giữ: tách Review/Apply, khả năng mở diff/evidence, sidebar session và nhóm Advanced. Màu tối và hệ thống thẻ đã có nền tảng; ưu tiên giảm mật độ và làm rõ phân cấp hành động. Chưa cần đổi toàn bộ visual identity hay chuyển framework chỉ để làm đẹp.

**Cần tổ chức lại mã UI để các lỗi trên khó quay lại**

`web/templates/index.html` đã hơn 11.000 dòng, trộn markup, nhiều workflow và toàn bộ state/HTTP handlers. Đây không tự thân là lỗ hổng, nhưng các lỗi response race, mode reset và failure-state cho thấy chi phí duy trì đã hiện ra trong hành vi.

Nên tách dần template shell và các partial; JavaScript riêng cho API/auth, run state, candidate review, Dream và các công cụ nâng cao. Dùng một module state làm chủ quan hệ repo → run → candidate → Apply receipt, thay vì để mỗi nút đọc repo hiện tại và patch hiện tại độc lập. Tách theo hành vi có test, không đổi mọi file cùng lúc. Bộ kiểm tra UI cần thêm browser tests cho race, lỗi HTTP, switching mode, keyboard và CDN unavailable; test tìm chuỗi trong HTML không bảo vệ được những hợp đồng này.

**Các vấn đề lịch sử vẫn mở**

Source hiện tại vẫn còn cơ chế của các phát hiện CRLF single-file, backup `.bak` cố định, retry/self-correction thiếu tái kiểm phạm vi/basis, GET history không xác thực, JSON session lost update và timeout chưa quản lý chắc cây process. Dream commit còn dùng Git index chung. Những probe cũ không chạy lại và không được cộng thành phát hiện mới. Chi tiết/bằng chứng gốc: [audit 09/09](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-09-product-and-code-review-vi.md).

**Thứ tự khắc phục đề xuất**

| Đợt | Phạm vi | Điều kiện hoàn tất |
|---|---|---|
| 1 | XSS, backup/Undo, schema + transaction, Dream approval identity, rollback truthfulness; ghép xử lý CRLF và backup ownership cũ | Payload HTML không thực thi; malformed plan không để lại partial write; Undo không chạm repo khác; Apply đúng candidate đã review; restore lỗi phải hiện rõ |
| 2 | Auth đọc/ghi, Origin, UI login/transport, legacy retry authority | UI hoạt động với auth bật; dữ liệu đọc được bảo vệ; mọi candidate mới phải qua kiểm chứng/cấp quyền tương ứng |
| 3 | State UI, form gọn, mode/Undo/race, keyboard, CDN fallback | Repo switch không giữ candidate cũ; trạng thái đúng với backend; nút Run dễ thấy; luồng coding vẫn dùng được khi Graph/CDN lỗi |
| 4 | Durable jobs, session concurrency, cancellation/process tree, đo p50/p95 với model thật | Run sống qua reload/restart theo hợp đồng; không mất update; Stop có tác dụng thật; có số đo thời gian/chi phí theo loại tác vụ |

Ba runtime probes và một auth probe đạt assertion vì **đã tái hiện lỗi**, không phải vì lỗi đã được sửa. Dream được chạy lại riêng sau khi siết Git isolation; không tính là ca mới. Bốn handler scenarios và một CDN scenario dùng adapter xác định. Browser đã xác minh layout và Evidence XSS; lượt chạy giả có delay chủ đích chỉ phục vụ xem UI, không dùng làm benchmark hay SLA.

Với vai trò khách hàng, tôi vẫn chỉ chọn pilot local có người review sau khi đóng các lỗi ghi/ủy quyền ưu tiên. Lõi kiểm chứng còn giá trị, nhưng việc xem đúng candidate rồi Apply đúng candidate, và báo đúng trạng thái sau thất bại, phải đáng tin trước. Polish hữu ích nhất lúc này là giúp người dùng thực hiện và hiểu đúng các thao tác đó.
