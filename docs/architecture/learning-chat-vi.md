# Chat với bài giảng được chọn

Cập nhật 2026-10-28. `/learn/chat` có chat kiến thức chung và chat theo một bộ bài giảng người học chọn. Người học bắt đầu bằng câu hỏi; hệ thống giữ lịch sử và trình bày giải thích, code, bảng, sơ đồ khái niệm cùng các đoạn nguồn để đối chiếu. Bài thực hành Java soạn sẵn vẫn ở `/learn`; kho tài liệu và liên kết khái niệm ở `/learn/materials`. Bộ câu hỏi từ các phần bài giảng đã chọn ở `/learn/practice`; xem [luồng Practice](learning-practice-vi.md).

## Phạm vi đang chạy

- Tạo, mở lại và xóa hội thoại; mỗi cookie người học có kho hội thoại riêng về mặt truy cập.
- Gửi câu hỏi và phần lịch sử gần nhất tới một model được cấu hình. Không tự gọi AI khi mở trang hoặc bấm gợi ý điền câu hỏi.
- Hiển thị đoạn văn, danh sách, tiêu đề, bảng và code có nút sao chép. Nội dung từ model được dựng bằng DOM/textContent; HTML và code không được thực thi.
- Giữ bản nháp khi lỗi, đối chiếu bản mới khi hai tab cùng gửi, khôi phục sau khi mất phản hồi. Nhãn phạm vi cho biết **Kiến thức chung** hay tên bộ bài giảng của hội thoại.
- Chọn bộ tài liệu trước khi mở hội thoại mới. Nguồn cố định trong hội thoại để các câu hỏi tiếp nối không vô tình đổi bộ tài liệu. Hội thoại cũ giữ chế độ kiến thức chung.
- Tìm các đoạn trích liên quan, lưu cùng câu trả lời và mở ngay dưới câu trả lời: tên file, trang/slide/đoạn, văn bản đã cung cấp, mã nguồn và cảnh báo trích xuất.
- Ollama là mặc định theo lựa chọn của người dùng. Gemini có adapter riêng; không tự chuyển hội thoại sang cloud khi Ollama lỗi. llama.cpp là hướng bổ sung sau qua cùng giao diện responder.
- Ngôn ngữ giải thích mặc định là **English**, kể cả khi câu hỏi hoặc giao diện bằng tiếng Việt. Nếu câu hỏi mới yêu cầu rõ một ngôn ngữ khác, model được hướng dẫn làm theo. Nhãn giao diện vẫn chủ yếu tiếng Việt; thuật ngữ, code và đoạn trích giữ nguyên ngôn ngữ nguồn.
- Hội thoại theo tài liệu có **Concept map** tải khi mở. Chọn nút để xem nguồn, tô sáng các khái niệm chung phần nguồn, lọc tên hoặc chỉ hiện nút liên quan. **Ask about…** chỉ điền bản nháp, không tự gọi AI.

Đã có RAG đơn giản bằng tìm từ khóa, chưa có tìm kiếm ngữ nghĩa/embedding hoặc dịch truy vấn giữa các ngôn ngữ. Chưa có ảnh đầu vào model, công cụ chạy code hoặc podcast/TTS. Chat không tự mở bài kiểm tra; Practice có luồng tạo câu trắc nghiệm riêng và chấm lựa chọn theo đáp án model đã lưu, chưa chấm tự luận. Hiện câu trả lời hiện khi model hoàn tất, chưa truyền từng token. Các nút “Giải thích đơn giản hơn” và “Cho thêm ví dụ” điền bản nháp để người dùng quyết định gửi.

## Hỏi theo bài giảng

1. Trong `/learn/materials`, nhập tài liệu và xem phần văn bản đã trích xuất. Với ảnh, ghi chú do người học viết là dữ liệu riêng, không phải OCR hay nhận diện sơ đồ.
2. Tại `/learn/chat`, chọn bộ bài giảng ở phần nguồn cho hội thoại mới, rồi mở hội thoại. Với màn hình chưa có hội thoại, gửi câu đầu tiên cũng dùng lựa chọn đó.
3. Hỏi bằng thuật ngữ xuất hiện trong nguồn; mở **Đối chiếu bài giảng** dưới câu trả lời để đọc đoạn đã được gửi. Muốn đổi nguồn, mở hội thoại mới.

`chat_retrieval.py` chỉ đọc bộ tài liệu thuộc owner hiện tại qua `MaterialLibrary`, tìm theo từ khóa Unicode và xếp hạng theo độ phủ/tần suất của từ. Có chuẩn hóa dấu tiếng Việt và n-gram cho CJK/Hangul, nhưng không dịch tiếng Việt sang tiếng Anh/Hàn/Trung. Tối đa 5 đoạn, 1.600 ký tự/đoạn và 8.000 ký tự tổng. Câu hỏi tiếp nối dùng câu hỏi có nội dung gần nhất; yêu cầu tóm tắt lấy mẫu giới hạn từ các file và UI nói rõ không phải toàn bộ bài giảng. Yêu cầu ngôn ngữ đầu ra như `Answer in English` không bị tính là từ khóa chủ đề.

Khi câu hỏi khớp chính xác tên khái niệm đã gắn (ví dụ `Explain ISR.`), retriever dùng các unit ID do người học liên kết qua graph. Dấu câu trong nhãn được giữ để C++ không lẫn C#. Trong các unit đó, ưu tiên đoạn chứa từ khóa; nếu tên chỉ là alias không xuất hiện trong nguồn thì lấy phần đầu giới hạn. Snapshot ghi `selection: concept_link` và `concept_link_origin: user`. Liên kết của người dùng giúp tìm nguồn, chưa xác nhận nguồn định nghĩa khái niệm đúng.

## Sơ đồ kết nối

`LearningKnowledgeGraph.collection_map()` tái sử dụng `ProgramGraph`, không tạo kho graph mới. Endpoint đọc `/learn/api/materials/<collection_id>/map` kiểm tra owner và không gọi model hay ghi dữ liệu. Nó hiển thị tối đa 30 khái niệm, 10 file và 60 cạnh chung nguồn; mỗi nút có tối đa 5 phần nguồn xem trước, 500 ký tự/phần. UI báo rõ khi rút gọn. `concept_links()` phục vụ tra cứu tất cả nhãn trong quota hiện có, không bị giới hạn 30 nút của hình vẽ.

Nút gốc là tên bộ tài liệu. Cạnh tới file là cấu trúc chứa nguồn; cạnh tới khái niệm là nhãn người dùng đã gắn. Cạnh nét đứt giữa hai khái niệm chỉ được vẽ nếu chúng cùng gắn vào đúng một unit, với `derived_from_user_links`. Đây không phải quan hệ nhân quả, `is-a` hoặc thứ tự học tiên quyết.

Để tạo ví dụ OS → Semaphore/ISR: nhập bộ bài giảng OS, chọn các phần nguồn trong Materials và gắn nhãn tiếng Anh phù hợp. Mở chat của bộ đó rồi mở Concept map. Khi chưa có nhãn, sơ đồ vẫn hiện file để đi tới nguồn và gắn khái niệm; không chèn dữ liệu minh họa vào tài liệu người dùng. Liên kết từ bản đồ mở đúng collection/unit trong tab mới, giữ hội thoại hiện tại. Sau khi sửa nhãn, nhấn **Refresh map**. Việc chọn nút không đánh giá mức độ hiểu của người học và không tự tạo thêm quan hệ.

Không tìm được đoạn phù hợp: trả thông báo xác định, không gọi model và không tự chuyển sang trả lời kiến thức chung. Khi có đoạn phù hợp: model nhận chúng như dữ liệu không đáng tin cậy trong user content, với chỉ dẫn riêng yêu cầu trích `[S1]`, `[S2]` và phân biệt ví dụ tự tạo. Đoạn trích không cấp quyền chạy công cụ, đọc file khác hoặc truy cập mạng. Prompt là hướng dẫn hành vi, không bảo đảm model không bị nội dung nguồn gây ảnh hưởng.

Server kiểm tra mã trích dẫn có thuộc tập đoạn vừa gửi hay không. Mã lạ không trở thành liên kết; nguồn chỉ được cung cấp nhưng chưa được model dẫn được hiển thị riêng. Đây là kiểm tra danh tính nguồn, **chưa kiểm chứng rằng nguồn chứng minh nhận định**. Trạng thái `grounding_ready` của kho tài liệu vẫn không được nâng thành đã duyệt. Các đoạn trích và ghi chú ảnh đều có thể cần người học đối chiếu.

## Chạy cục bộ

Từ thư mục repository, mở Ollama rồi xem model đã cài bằng `ollama list`. Ví dụ máy thử có `qwen3.5:4b`:

```powershell
python scripts/run_learning_chat.py --model qwen3.5:4b
```

Mở `http://127.0.0.1:5055/learn/chat`. Script chỉ đặt biến môi trường cho tiến trình này, không sửa `.env` hay cấu hình hệ thống. Repo hiện có thể lấy `.env` từ thư mục cha; không tạo một `.env` mới chỉ để chat rồi vô tình che cấu hình đang dùng. Đường khởi động thông thường vẫn nhận `LEARNING_CHAT_PROVIDER`, `LEARNING_CHAT_MODEL` và `OLLAMA_HOST`. Model cần được chọn rõ; thiếu cấu hình được báo trên UI.

Gemini dùng `GOOGLE_API_KEY` phía máy chủ và model có trong tài khoản:

```powershell
python scripts/run_learning_chat.py --provider gemini --model TEN_MODEL_CUA_BAN
```

Không nhập API key vào hội thoại. Script này tắt mặc định các dependency DB/embedding không cần cho bản chat; những biến môi trường đã đặt vẫn được giữ. Model local có thể cần thời gian nạp trước lượt đầu; không tự tải model hoặc đổi model khi lỗi.

## Ranh giới và lưu trữ

`core/learning/chat_store.py` lưu vào `.agent/learning/chats.sqlite3`. Khóa `owner` lấy từ cookie người học, không từ body của trình duyệt. Có tối đa 50 hội thoại/người dùng, 100 lượt/hội thoại; câu hỏi 8.000 ký tự, câu trả lời 24.000 ký tự. Lịch sử gửi model tối đa 48.000 ký tự, giữ các cặp hỏi/đáp hoàn chỉnh gần nhất. Đây là giới hạn ký tự, chưa phải bộ đếm token chính xác của từng model.

Mỗi lượt có request ID và revision. Transaction đặt chỗ trước khi gọi model; model chạy ngoài transaction. Gửi lại cùng request ID và nội dung không tạo lượt gọi thứ hai, kể cả khi lượt đầu lỗi. Thử lại sau lỗi model là một lượt gửi mới do người dùng chủ động. Lượt đang chờ hết hạn sau 120 giây; kết quả đến muộn không được ghi đè trạng thái mới. Không cho xóa hội thoại đang có lượt còn hiệu lực.

`core/learning/chat_provider.py` nhận lịch sử role/content và tùy chọn các đoạn nguồn do server lấy. Adapter không tự đọc corpus, graph, đáp án bài Java hoặc công cụ coding. Các đoạn nguồn chiếm chỗ trong cùng ngân sách 48.000 ký tự; lịch sử được cắt theo cặp hỏi/đáp cũ nhất. Model được ghim cho từng request, không có vòng fallback hoặc retry tự động ở adapter.

SQLite nâng schema v1 lên v2 trong transaction, giữ nguyên hội thoại cũ. Mỗi hội thoại mới lưu collection ID/title cố định; mỗi câu trả lời theo bài giảng giữ snapshot bằng chứng tối đa 64 KiB, bao gồm source/unit ID, vị trí và văn bản thực tế, phiên bản ghi chú ảnh nếu có. Sửa ghi chú sau đó không làm đổi nguồn lịch sử. Mã `[S#]` cũ được bỏ khỏi lịch sử gửi model để không bị hiểu là nguồn của lượt hiện tại; câu trả lời lưu vẫn nguyên văn. Request tạo chat cũng ràng buộc với lựa chọn nguồn khi thử lại sau mất phản hồi.

Ollama chỉ nhận host loopback, không theo redirect và không dùng proxy từ biến môi trường. Gemini dùng SDK hiện có. Cả hai bỏ phần thinking riêng; phản hồi bị cắt vì giới hạn sinh không được lưu như câu trả lời hoàn chỉnh. Giới hạn transport là 60 giây đọc; Ollama còn kiểm tra thời gian giữa các chunk. Đây chưa phải cơ chế hủy tính toán cứng: model có thể tiếp tục ở phía nhà cung cấp sau khi trình duyệt hoặc request timeout. Lease bảo vệ dữ liệu trước kết quả muộn.

Hội thoại được lưu cục bộ nhưng chưa mã hóa riêng. Đổi/xóa cookie có thể mất quyền mở lại dữ liệu qua web. Khi chọn Gemini, lịch sử và những đoạn bài giảng đã chọn được gửi ra dịch vụ đó; xóa hội thoại tại C.A.T.T.U.S không xóa bản mà dịch vụ có thể giữ. Với Ollama chúng được gửi tới endpoint loopback đã cấu hình. API giữ auth, Origin/CSRF và private headers hiện có.

## Cơ sở giao diện tương tác

Ý tưởng dùng phần trình bày phù hợp với nội dung được tham khảo từ [ChatKit widgets](https://developers.openai.com/api/docs/guides/chatkit-widgets) và [hướng dẫn UI trong hội thoại](https://developers.openai.com/plugins/concepts/ui-guidelines). Đây là tham chiếu thiết kế công khai, không khẳng định đó chính là cơ chế của tính năng “Intelligent UI” người dùng nhìn thấy.

Bản đầu dùng component của repository để tránh thêm runtime mới. Mở rộng tiếp theo nên dùng các dạng dữ liệu có schema rõ như bảng so sánh, sơ đồ từng bước hoặc câu hỏi ngắn; ứng dụng kiểm tra dữ liệu rồi chọn component hiển thị. Chưa cho model tự phát sinh HTML/JavaScript để chạy trong trang.

## Các bước tiếp theo

1. Thử hội thoại thật: câu trả lời có ích, thời gian nạp/lượt trả lời, chất lượng tiếng Việt và khả năng giải thích code. Tách kết quả local với Gemini nếu sau này so sánh.
2. Đo độ tìm đúng nguồn với câu hỏi thật, cách diễn đạt khác và câu hỏi khác ngôn ngữ tài liệu; cân nhắc embedding đa ngôn ngữ nếu từ khóa bỏ sót nhiều. RAG không phải huấn luyện model trên bài giảng.
3. Kiểm tra chất lượng diễn giải và mức hỗ trợ của từng trích dẫn bằng tập câu hỏi có đáp án tham chiếu, trước khi dùng chúng để sinh hoặc chấm bài.
4. Thêm một dạng trình bày tương tác có ích cho bài đang học, rồi mới thêm nhóm câu hỏi và kiểm chứng đáp án. Đo xem nó giúp hiểu hơn hay chỉ làm giao diện phức tạp hơn.

## Kiểm thử

Lượt English-first ngày 2026-10-26: 56 kiểm thử provider vượt qua; 36 truy xuất, 27 API chat và 57 graph/API bản đồ vượt qua. Bốn ca symlink cũ được bỏ qua vì quyền Windows; các ca ownership, database lỗi và đọc không ghi vẫn chạy. Truy xuất alias có ca kiểm tra ISR không có trong văn bản, C++/C# riêng biệt và từ khóa nằm cuối unit dài. Liên kết sâu từ sơ đồ tới đúng file/unit có 2 kiểm thử Chromium riêng.

Hoàn tất giao diện ngày 2026-10-27: 17 ca Chromium khác nhau vượt qua (7 bản đồ, 5 chat cũ, 5 chat bài giảng). Hai ca cuối được chạy lại sau khi sửa đồng bộ chờ hội thoại trong test và đối chiếu focus đúng panel; không bỏ qua lỗi sản phẩm. Tính cùng 2 ca liên kết sâu ở trên, tổng phạm vi English-first/bản đồ là **195 passed, 4 skipped**, không đếm lại các lượt chạy chồng nhau. Đã xem ảnh desktop/mobile, kiểm tra cú pháp JavaScript/Python, whitespace và xác nhận server local phục vụ đúng script hiện tại. Không chạy toàn repository.

Smoke model thật sau khi sửa prompt: `qwen3.5:4b` trả tiếng Anh cho câu hỏi/lịch sử tiếng Việt trong **3,08 giây**; yêu cầu rõ tiếng Việt trả tiếng Việt trong **2,80 giây**, cả hai có `[S1]`. Nguồn là đoạn OS tổng hợp. Bản prompt đầu vẫn trả sai ngôn ngữ nên đã bổ sung ví dụ chính sách ngôn ngữ trước hai lượt thử cuối. Bản tiếng Việt vẫn có thuật ngữ dịch chưa tốt; không coi các mẫu này là bảo đảm chất lượng đa ngôn ngữ hay tốc độ ổn định.

Kiểm tra domain/provider, API và Chromium dùng kho tạm cùng model giả lập. Chúng xác minh ownership, revision, thời hạn, retry, không gọi thêm model, context giữa các cuộc chat, lỗi được che thông tin nhạy cảm, renderer văn bản/code/bảng, mobile và giữ bản nháp. Chúng không chứng minh độ đúng của model hoặc chất lượng học.

Các file kiểm tra: `tests/learning/test_chat_store.py`, `tests/learning/test_chat_provider.py`, `tests/integration/test_learning_chat_web.py`, `tests/integration/test_learning_chat_browser.py`.

Bổ sung tích hợp bài giảng ngày 2026-10-25: **229 kiểm tra khác nhau vượt qua** — 52 store, 52 provider, 28 retrieval, 17 API chat cũ, 10 API chat bài giảng, 60 API hồi quy tài liệu/ảnh/graph và 10 Chromium (5 chat cũ + 5 bài giảng). Các lượt chạy có phần chồng nhau không được đếm hai lần. File mới: `tests/learning/test_chat_retrieval.py`, `tests/integration/test_learning_chat_grounding_web.py`, `tests/integration/test_learning_chat_grounding_browser.py`. Đã xem ảnh desktop/mobile, kiểm tra cú pháp Python/JavaScript và whitespace. Chromium cần quyền chạy ngoài sandbox để truy cập loopback; các phiên bị chặn đã dừng trước khi chạy lại. Không chạy toàn repository.

Smoke test thật riêng với `qwen3.5:4b`, một đoạn bài giảng Java tổng hợp (không dùng tài liệu riêng tư): trả đúng `Cat.speak()` và mã `[S1]` trong **19,12 giây**. Model trả lời tiếng Việt dù câu hỏi tiếng Anh; đây là một giới hạn làm theo yêu cầu ngôn ngữ cần cải thiện/đo thêm, không coi mẫu này là xác nhận hỗ trợ đa ngôn ngữ hay chất lượng trích dẫn trên toàn bộ bài giảng. Thời gian trên gồm gọi provider, không phải benchmark UI end-to-end.

Lượt tích hợp 2026-10-25: **170 kiểm tra vượt qua** — 76 domain/provider, 17 API chat, 1 cổng bảo vệ route ghi, 71 hồi quy API Teacher/tài liệu/ảnh/graph và 5 Chromium chat. JavaScript qua kiểm tra cú pháp; ảnh giao diện desktop/mobile đã được xem lại. Không chạy toàn repository.

Thử model thật cùng ngày với `qwen3.5:4b` đã có trên máy: lần đầu adapter (ngữ cảnh 16.384) timeout sau 60,22 giây; probe cực ngắn với ngữ cảnh 4.096 cũng timeout sau 60,04 giây trong khi nạp. Sau đó Ollama báo model đã nạp trên GPU. Gọi lại adapter chat trả lời đúng câu hỏi override `Animal a = new Cat(); a.speak();` trong **14,15 giây**. Đây là một mẫu smoke test, chưa phải benchmark độ trễ/chất lượng hoặc bằng chứng mọi lượt đều nhanh. Cần đo thêm lúc nạp lạnh và khi đã sẵn sàng; UI chưa có streaming từng token để giảm cảm giác chờ.
