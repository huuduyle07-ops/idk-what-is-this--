# C.A.T.T.U.S: lựa chọn nghiên cứu và kế hoạch cho hướng dạy, học, hiểu code

Ngày lập kế hoạch: 2026-10-22. Trạng thái: **đang triển khai; đã có bản thử Teacher với nội dung soạn sẵn**.

Định hướng tiếp theo đã chốt: [học qua trò chuyện dựa trên bài giảng của người học](user-grounded-learning-vi.md). Đã bổ sung bộ chuẩn bị nguồn PDF/PPTX/DOCX và ảnh PNG/JPEG chạy cục bộ, cùng lớp liên kết khái niệm do người dùng xác nhận để đi qua lại giữa các phần nguồn. [Chat theo bài giảng](learning-chat-vi.md) đã có chọn bộ tài liệu, truy xuất từ khóa và mở các đoạn nguồn; nhóm câu hỏi phù hợp và kiểm chứng diễn giải là bước tiếp theo.

Cập nhật triển khai: [bài thử Teacher tại `/learn`](teacher-pilot-vi.md) đã có ba tình huống Java, gợi ý, phản hồi, lưu/tiếp tục và xuất/xóa bài làm. Bản thử này chưa gọi LLM, chưa dạy trên repository bất kỳ và chưa hoàn thành toàn bộ M1. Các mục bên dưới vẫn mô tả thiết kế và kế hoạch rộng hơn; tài liệu bản thử ghi phạm vi đã kiểm chứng.

Tài liệu này chọn lọc bản bổ sung *Mapping C.A.T.T.U.S into a Lightweight Coding Tutor and Self-Evaluation Research Branch*, đối chiếu có chọn lọc với mã nguồn và nối tiếp [đợt tổ chức repository đầu tiên](repository-organization.md). Không kiểm toán lại toàn repository, không chạy lại các kiểm tra đã xác minh và không thay đổi runtime trong lượt lập kế hoạch này.

## 1. Quyết định sản phẩm

**Trải nghiệm Teacher giúp người dùng hiểu và tự làm được trên code thực tế. Theo định hướng bổ sung, sản phẩm có ba chế độ: Coding, Teacher và Self-evaluating/Decision-making, dùng chung nền tảng.** Hướng dạy học vẫn là trọng tâm khác biệt của kế hoạch này; Coding có workflow sử dụng riêng, Decision có thể chạy độc lập và cung cấp khả năng đánh giá cho các workflow khác.

Xem [thiết kế ba chế độ](three-agent-modes-vi.md) cho ranh giới, routing và thứ tự triển khai chung. Các mốc M0–M4 dưới đây là kế hoạch nhánh Teacher; không yêu cầu hoàn thành learner model trước khi có chế độ Decision dựa trên luật và bằng chứng.

Phạm vi Decision đã được người dùng chốt: bắt đầu với code và việc học, mở rộng lĩnh vực sau. Trong nhánh Teacher, Decision hỗ trợ chọn gợi ý, bài vận dụng hoặc bước kiểm chứng tiếp theo; đánh giá người học vẫn dựa trên rubric và bài làm có phạm vi rõ.

**Ưu tiên thực hiện đã chốt: Teacher trước.** Mốc gần nhất là một vòng học dùng được trong UI, có phản hồi và bằng chứng từ bài làm. Coding hiện có cung cấp các khả năng cần thiết; Decision trước mắt là phần đánh giá/chọn bước học bằng luật. UI Decision độc lập, mô hình học máy, Dream và graph dashboard không phải điều kiện để phát hành vòng học đầu tiên.

Giữ phần hạ tầng hữu ích mà không cần đặt harness làm sản phẩm chính như executive summary của nghiên cứu đề xuất. Đó là lựa chọn định vị của báo cáo, không phải kết luận bắt buộc từ bằng chứng nghiên cứu.

Giả định cho bản đầu: phục vụ người đã biết cú pháp nhưng gặp khó khi đọc một codebase hoặc giải thích hành vi của code. Chọn một chủ đề Java nhỏ để thử trước; chỉ mở rộng ngôn ngữ và chủ đề sau khi vòng học có ích.

Giá trị cần chứng minh: người học hiểu một đoạn code, giải quyết được tình huống khác và còn làm được ở lần sau, với thời gian và mức trợ giúp hợp lý. Số phase, số agent hoặc độ phức tạp của mô hình không phải thước đo giá trị đó.

## 2. Chọn gì từ nghiên cứu

| Quyết định | Thành phần | Lý do và cách áp dụng |
| --- | --- | --- |
| Dùng ngay | Tự giải thích, bài vận dụng khác, ôn lại sau một khoảng thời gian | Tạo bằng chứng về việc học thay vì chỉ đọc một lời giải hay. Bắt đầu bằng bài và rubric được kiểm tra trước. |
| Dùng ngay | Nhật ký bài làm và nhận định trước kết quả | Lưu hệ thống đã thấy gì, chọn hành động nào và vì sao; sau đó mới ghi kết quả. Có thể kiểm tra lại một đánh giá sai. |
| Dùng ngay | Tách năng lực, độ tin cậy đánh giá và Memory Temperature | Memory Temperature hỗ trợ chọn thông tin; không biến thành xác suất người học hiểu hay đã quên. |
| Dùng ngay | Luật đơn giản, có trạng thái chưa đủ bằng chứng | Dễ giải thích, sửa và kiểm thử khi chưa có dữ liệu người học thật. Không hiển thị phần trăm mastery thiếu căn cứ. |
| Dùng ngay | Baseline, phiên bản hóa và tiêu chí bỏ bớt | Mỗi thành phần mới phải cải thiện trải nghiệm hoặc kết quả đo được so với cách đơn giản hơn. |
| Dùng có điều chỉnh | LLM | Dùng đường LLM hiện có cho giải thích và hội thoại từ bản đầu. Nhận xét của LLM là một nguồn quan sát; không tự trở thành bằng chứng người học đã hiểu. |
| Làm sau | Logistic với lịch sử bài làm; BKT | Logistic là thử nghiệm đầu tiên khi có dữ liệu. Chỉ thêm BKT khi có chuỗi bài và ánh xạ kỹ năng đủ rõ. Không đưa cả hai vào dependency bắt buộc ngay. |
| Làm sau | Lịch ôn thích nghi, mô hình độ khó, learner graph | Cần dữ liệu và một baseline ôn đơn giản trước. Ban đầu dùng concept ID, quan hệ tiên quyết và liên kết tới code. |
| Hoãn khỏi bản đầu | PID, deep knowledge tracing, semantic entropy nhiều lượt gọi, mô hình local lớn, nhiều agent đánh giá | Chưa có bằng chứng lợi ích đủ bù độ phức tạp, thời gian chờ và công bảo trì cho sản phẩm này. |
| Không áp dụng nguyên trạng | PNF chưa định nghĩa; số mastery/confidence mẫu; ngưỡng thắng và lịch 12 tuần | Chưa phải định nghĩa hay cam kết đã được kiểm chứng. Không chuyển ví dụ trong nghiên cứu thành contract sản phẩm. |

Nghiên cứu về tự giải thích hỗ trợ việc yêu cầu người học liên hệ lời giải với nguyên lý, nhưng nghiên cứu gốc không chứng minh hiệu quả của C.A.T.T.U.S trên code. Cần kiểm tra riêng trong sản phẩm. [Chi và cộng sự, 1989](https://doi.org/10.1207/s15516709cog1302_1).

Retrieval practice và học giãn cách cung cấp cơ sở để thử bài nhớ lại/vận dụng ở lần sau. Chúng không cung cấp sẵn lịch ôn tối ưu cho từng người học lập trình. [Karpicke & Blunt, 2011](https://learninglab.psych.purdue.edu/downloads/2011/2011_Karpicke_Blunt_Science.pdf), [Cepeda và cộng sự, 2006](https://pubmed.ncbi.nlm.nih.gov/16719566/).

## 3. Tận dụng mã hiện có đến đâu

Các nhận định dưới đây dựa trên đọc mã có chọn lọc; không phải xác nhận một workflow mới đã chạy end-to-end.

| Điểm có thể tái sử dụng | Dùng cho kế hoạch | Giới hạn phải giữ rõ |
| --- | --- | --- |
| [`prompter.build_prompt`](../../core/prompter.py), [`pipeline.run_draft_pipeline`](../../core/pipeline.py) | Prompt hướng dẫn người dùng, ngữ cảnh project chỉ đọc | Có chính sách tutor trong prompt; chưa có hồ sơ người học hay kiểm chứng mức hiểu. |
| [`context_search_runtime`](../../core/context_search_runtime.py), [`direct_context_runtime`](../../core/direct_context_runtime.py) | Tìm kiếm và đọc code trong phạm vi/budget có giới hạn | Selector đề xuất tập file khác với runtime thực sự đọc; phải báo đúng phần đã đọc. |
| [`lesson_store`](../../core/lesson_store.py), [`lesson_retrieval`](../../core/lesson_retrieval.py), [`lesson_teaching_card`](../../core/lesson_teaching_card.py) | Nguồn case tham khảo và định dạng thẻ giải thích/bài tập | Lesson hiện là tri thức sửa lỗi của agent. Teaching card là formatter, chưa chấm bài hay điều chỉnh cách dạy. Nội dung dùng để dạy cần rubric riêng. |
| [`evidence_verification`](../../core/evidence_verification.py), [`evidence_promotion_gate`](../../core/evidence_promotion_gate.py) | Tham khảo contract liên kết phát biểu với nguồn code và biểu diễn thiếu bằng chứng | Chưa nối vào live path đã kiểm tra. Cần adapter và kiểm chứng integration; citation đúng không tự chứng minh diễn giải đúng. |
| [`replay_recorder`](../../core/replay_recorder.py) | Tận dụng cách ghi artifact/manifest để truy vết | Không tự che dữ liệu nhạy cảm; không mặc định đổ toàn bộ bài làm vào replay coding. |
| [`experiments`](../../core/experiments.py), [`prompt_cost_quantifier`](../../core/prompt_cost_quantifier.py) | So báo cáo, model calls, thời gian và chi phí | Chưa có metric kết quả học hay cơ chế chia nhóm người học. Budget preview không phải enforcement khi chạy. |

Phần cần thiết kế mới: sự kiện bài làm, trạng thái người học theo khái niệm, rubric đánh giá, lựa chọn bước dạy tiếp theo và giao diện cho vòng học. Dùng adapter nhỏ nối các phần có sẵn; không bắt luồng dạy đi qua toàn bộ hệ thống governance.

## 4. Vòng học nhỏ nhất đáng làm

Ví dụ đầu tiên: Java overriding và runtime dispatch. Nội dung phải được xác minh trước, có bài vận dụng khác cấu trúc thay vì chỉ đổi tên biến.

1. Trong Teacher, người học chọn đoạn code và mục tiêu, với **Giải thích ngay** hoặc **Hướng dẫn tôi tự làm**; **Làm giúp tôi** là điểm chuyển sang Coding với phạm vi rõ. Đây là lựa chọn tương tác, khác với ba chế độ sản phẩm. Không ép người chỉ muốn giải thích phải làm quiz.
2. Trong chế độ hướng dẫn, tutor hỏi một câu dự đoán hành vi hoặc yêu cầu giải thích một quyết định trong code.
3. Tutor phản hồi bằng đoạn code liên quan và rubric. Người học có thể xin gợi ý từng mức, xem lời giải, sửa phản hồi sai hoặc dừng bài.
4. Tutor đưa một bài vận dụng mới. Với bài có đáp án thực thi, harness kiểm tra trong môi trường đã xác minh; với giải thích mở, dùng rubric và cho phép kết luận chưa đủ bằng chứng.
5. Ghi kết quả, mức trợ giúp và nguồn kiểm chứng. Hiển thị nhận định có phạm vi, ví dụ: “Bạn đã giải đúng bài dispatch này mà không cần gợi ý; chưa kiểm tra ở tình huống khác.”
6. Lần học sau có thể đưa bài nhớ lại/vận dụng mới, đối chiếu nhận định trước với kết quả mới.

UI đầu tiên gồm đoạn code, hội thoại ngắn, nút gợi ý/lời giải/thử bài khác và phần “Vì sao có nhận xét này?”. Đưa UI vào cùng vòng chức năng đầu tiên; graph dashboard có thể chờ.

Chế độ “Làm giúp tôi” dùng harness theo quyền hiện có. Code do hệ thống làm không được ghi thành thành tích tự làm của người học. Có thể đề nghị giải thích hoặc bài tự kiểm tra sau đó.

## 5. Dữ liệu và ranh giới đánh giá

Một record bài làm tối thiểu cần có:

- ID người học cục bộ, phiên học, khái niệm, bài và họ bài; phiên bản bài/rubric/policy; phiên bản model/prompt nếu dùng.
- Tham chiếu code kèm revision hoặc content hash để nhận ra code đã thay đổi; tránh lưu toàn bộ repository vào hồ sơ học.
- Nhận định và hành động được ghi trước kết quả; liên kết tới bằng chứng có trước thời điểm đó. Khi chưa có mô hình đã hiệu chỉnh, không bắt buộc trường xác suất.
- Kết quả theo rubric, loại và thời điểm trợ giúp, lời giải đã được tiết lộ hay chưa; tình trạng kiểm tra và lỗi môi trường riêng biệt.
- Kết quả đánh giá độc lập: thành công, chưa thành công hoặc chưa quan sát được. Lưu liên kết prediction–outcome khi có dự đoán hợp lệ.

**Xin gợi ý không đồng nghĩa trả lời sai.** Nếu người học đã thấy trợ giúp trước khi trả lời, năng lực làm độc lập ở lượt đó có thể chưa được quan sát. Nếu họ thử sai trước rồi mới xin gợi ý, lưu hai sự kiện đúng thứ tự. Không suy đoán mức hỗ trợ AI từ tốc độ gõ hay văn phong.

Test pass chỉ chứng minh hành vi đã được test trong điều kiện đó. Giải thích trôi chảy, compile thành công hoặc tự chấm “đã hiểu” đều chưa đủ để kết luận hiểu toàn bộ khái niệm. Lỗi hạ tầng, timeout và hủy bài không tự trở thành lỗi người học.

Trạng thái ban đầu nên mô tả bằng chứng: **chưa đủ bằng chứng**, **đang luyện với trợ giúp**, **đã làm độc lập trong phạm vi này**, **đến lúc kiểm tra lại**. Mốc ôn tập không phải kết luận người học đã quên. Trạng thái “đã làm độc lập” vẫn cần bằng chứng riêng khi mở rộng sang bài khác.

Learner state có owner riêng trong ranh giới `core/learning/` đã dự kiến; tổ chức tên/module theo trách nhiệm sau khi xác định dependency. Agent lessons và hồ sơ người học phải có schema, storage namespace và test riêng dù cùng nằm dưới nhóm learning. Không bổ sung điểm mastery vào canonical code graph hoặc nhét toàn bộ logic vào `pipeline.py`.

Lịch sử học lưu cục bộ theo mặc định của phần mới, có xuất/xóa và chính sách lưu nội dung rõ ràng. Chọn phần gửi tới model theo cấu hình dữ liệu của người dùng. Event log có truy vết không có nghĩa giữ dữ liệu cá nhân vĩnh viễn; replay và bản sao cũng phải nằm trong phạm vi xóa. Không coi các yêu cầu thiết kế này là tính năng bảo mật đã được kiểm chứng.

## 6. Thứ tự thực hiện và điều kiện hoàn thành

### M0 — Chốt ranh giới cấu trúc và baseline

Tiếp tục việc tổ chức repository theo [kế hoạch hiện có](repository-organization.md): phân biệt test ghi nhận một trạng thái lịch sử với regression test của hành vi hiện tại; xác định dependency family của lessons/teaching trước khi di chuyển. Phân loại test theo trách nhiệm và phạm vi kiểm chứng, không theo số phase.

Với ưu tiên Teacher, giới hạn M0 vào entrypoint, owner và dependency thực sự cần cho M1. Có thể dùng adapter tới module hiện tại; chưa cần di chuyển cả họ lesson/context nếu việc đó không chặn vòng học. Tách việc di chuyển file khỏi thay đổi hành vi để dễ kiểm tra hồi quy.

[Kết quả đợt trước](organization-validation.json) ghi nhận 1.810/1.814 test liên quan pass, với bốn lỗi đã tái hiện trước đợt di chuyển: hai lỗi BANK fixture và hai assertion lịch sử về owner chưa tồn tại. Đây là baseline cũ, không phải kết quả test mới của tài liệu này. Giữ các lỗi này thành đầu việc có nguyên nhân/phạm vi rõ, giữ nguyên bằng chứng lịch sử và không thêm skip chỉ để xanh. Chúng chỉ chặn Teacher nếu đường học được chọn thực sự phụ thuộc phần lỗi đó; không bắt Teacher chờ sửa lỗi ngoài phạm vi.

**Hoàn thành khi:** ranh giới owner và test của vòng học rõ; các kiểm tra đang dùng cho đường thực thi đầu tiên đáng tin; lỗi ngoài phạm vi được ghi nhận đúng. Không yêu cầu chuyển toàn bộ hàng trăm file trước khi làm một vòng học. Nếu bài cần Java execution, phải xác minh runtime/fixture tương ứng trước khi dùng kết quả chấm người học.

### M1 — Một vòng học dùng được, gồm UI và nhật ký

Làm một chủ đề với bộ bài nhỏ có đáp án/rubric đã kiểm tra. Tận dụng prompt/context/card hiện có; thêm owner cho session, sự kiện và luật phản hồi tối thiểu. Cấu hình được hỗ trợ đầu tiên gồm một UI và một đường model hiện có cho hội thoại, với snippet và rubric được kiểm tra trước. Chỉ yêu cầu execution động nếu bài cụ thể cần nó; câu hỏi dự đoán/giải thích có đáp án đã kiểm tra không cần đợi một hệ thống chạy mọi bài Java.

Nếu model lỗi, giữ phiên, báo đúng trạng thái và cho thử lại/dừng hoặc xem nội dung soạn sẵn. Một tutor offline có hội thoại và chấm bài tương đương không phải điều kiện nghiệm thu M1. “Làm giúp” tái sử dụng điểm vào Coding hiện có với phạm vi rõ, chưa cần xây cơ chế handoff tổng quát.

Thứ tự công việc trong M1:

1. Nối lối vào Học trên UI với đường ngữ cảnh chỉ đọc; chọn mục tiêu và cách tương tác Giải thích/Hướng dẫn, bảo toàn phạm vi file đã đọc.
2. Hoàn thiện một chủ đề Java với ví dụ, gợi ý và bài vận dụng có rubric được kiểm tra trước. Phân biệt giải thích code tự do với bài đã có tiêu chí chấm; chưa tuyên bố chấm được mọi codebase hay câu trả lời mở.
3. Lưu phiên và bài làm cùng thời điểm trợ giúp, phiên bản nguồn/rubric; tạo phản hồi và chọn bước tiếp theo bằng luật. Đánh giá chưa đủ bằng chứng phải được biểu diễn rõ.
4. Cho người học thử bài khác, xem căn cứ nhận xét, xem lời giải hoặc kết thúc; mở lại phiên tiếp tục đúng chỗ. Ghi thời gian chờ và model calls trong cùng luồng.
5. Chạy kiểm tra hành vi và một vòng tích hợp/black-box đi qua UI/API thực tế, gồm cả lỗi công cụ, trợ giúp và đường không sửa source repo. Kiểm tra các chức năng Coding bị ảnh hưởng bởi adapter; không làm lại những audit ngoài phạm vi đã xác minh.

**Hoàn thành khi:** đi từ mở code đến trả lời, xin gợi ý, thử bài mới và xem bằng chứng nhận xét trong UI; lưu/mở lại phiên không lẫn dữ liệu giữa người học/repo; đường chỉ đọc không sửa code. Người dùng luôn có thể xem lời giải hoặc kết thúc, thay vì bị giữ trong chuỗi câu hỏi.

### M2 — Ôn đơn giản và kiểm tra giá trị với người thật

Thêm bài kiểm tra lại ở phiên sau, lịch ôn bằng luật dễ hiểu và quyền bỏ qua. Chạy pilot nhỏ để tìm lỗi rubric, mức gợi ý, nội dung khó hiểu và thời gian chờ. Pilot ban đầu đánh giá khả năng sử dụng; không dùng ít người để tuyên bố hiệu quả giáo dục đã được chứng minh.

**Hoàn thành khi:** quan sát được bài chuyển giao và bài kiểm tra lại; phân biệt lỗi nội dung, lỗi đánh giá và lỗi công cụ; có số liệu thời gian người học, thời gian chờ, số lần gọi model và tỷ lệ hoàn thành. Chốt mục tiêu chính và thiết kế đánh giá tiếp theo trước khi xem tập kết quả xác nhận.

### M3 — Thử một mô hình dự đoán ngoài luồng quyết định

Chỉ bắt đầu khi dữ liệu thật có đủ người học, chuỗi bài và độ đa dạng cho câu hỏi đánh giá đã chọn. So baseline đơn giản với logistic dùng lịch sử thành công/thất bại, trợ giúp và thời gian. Không cần triển khai trọn bộ LKT; đây là một ứng viên dựa trên lịch sử bài làm. LKT là một hướng regression có thể diễn giải để tham khảo, không phải bằng chứng nó sẽ thắng trên dữ liệu này. [LKT, EDM 2024](https://www.educationaldatamining.org/edm2024/proceedings/2024.EDM-tutorials.127/).

Mô hình chạy thử âm thầm: ghi dự đoán nhưng chưa quyết định bài học hay nhãn hiển thị. Dữ liệu synthetic chỉ kiểm tra pipeline, không chứng minh khả năng hiểu người thật. Kiểm tra compatibility thư viện với môi trường Python thực tế trước khi thêm dependency; chưa xác nhận pyBKT hoạt động trong môi trường hiện tại.

**Hoàn thành khi:** một mục tiêu chính được cải thiện với mức bất định được báo cáo, không làm tăng đánh giá quá cao năng lực ngoài giới hạn đã chọn, và chi phí/latency phù hợp. Nếu không đạt, giữ luật đơn giản; M1–M2 vẫn là sản phẩm hữu ích độc lập.

### M4 — Mở rộng theo nút thắt đã thấy

Chọn từng hạng mục: BKT nếu logistic thiếu khả năng theo dõi chuỗi kỹ năng; đánh giá giải thích bằng LLM nếu rubric hiện tại không đủ; lịch ôn thích nghi nếu lịch đơn giản gây lãng phí; graph UI nếu người học thực sự khó định hướng codebase.

Dream có thể chuẩn bị bài tập, phát hiện nội dung lỗi và tạo đề xuất cải thiện vào ban đêm. Đầu ra phải qua kiểm tra trước khi thành bài đang dùng. Dream không tạo bài làm giả, không tự nâng năng lực người học và không thay thế buổi học tương tác. Hoãn phần này cho đến khi vòng học ban ngày ổn định.

Không khóa lịch sáu sprint/12 tuần từ báo cáo vào cam kết. Ước lượng thời gian sau M0 và bản thử M1, khi dependency, runtime và công soạn bài đã rõ hơn.

## 7. Đánh giá để tránh tự đánh lừa

**Hai câu hỏi độc lập:** mô hình có dự đoán được lần làm sau không; cách dạy có giúp người học làm tốt hơn không. Mô hình dự đoán tốt có thể đi cùng cách dạy kém, đặc biệt nếu hệ thống chỉ chọn bài dễ.

| Câu hỏi | Phép đo/thiết kế đề xuất |
| --- | --- |
| Dự đoán có hữu ích và đáng tin? | Brier cùng biểu đồ calibration, số quan sát và khoảng bất định; thêm AUC khi dữ liệu có đủ hai lớp. Báo tỷ lệ đánh giá quá cao trong nhóm được cho chuyển tiếp, kèm độ phủ, số lần chưa kết luận và độ khó bài. |
| Người học có học tốt hơn? | Bài vận dụng mới và kiểm tra trì hoãn chung, thời gian học tương đương; so với chuỗi dạy cố định đơn giản. Khi đủ điều kiện, phân nhóm ngẫu nhiên; nếu dùng cùng người qua hai cách dạy, xử lý thứ tự và hiệu ứng luyện tập. |
| Sản phẩm có đáng chờ? | p50/p95 từ thao tác đến phản hồi hữu ích đầu tiên, tổng thời gian hoàn thành, số lần gián đoạn. Tách latency của retrieval/rules, model và compile/test; báo API cost, CPU/RAM riêng. |
| Nhận xét có đáng tin? | Bộ câu trả lời được người kiểm tra gán rubric trước; so lỗi phản hồi và trường hợp bỏ sót hiểu nhầm. Có đường sửa nhận xét và truy về code/bằng chứng. |

Brier đo cả những thành phần khác ngoài calibration; giảm Brier chưa tự chứng minh xác suất đã hiệu chỉnh tốt. Dữ liệu dùng hiệu chỉnh phải tách khỏi dữ liệu huấn luyện và tập đánh giá cuối. [Tài liệu calibration của scikit-learn](https://scikit-learn.org/stable/modules/calibration.html).

Mọi feature phải có trước mốc dự đoán. Không đưa mức gợi ý/kết quả của chính lượt cần dự đoán vào đầu vào. Độ khó bài phải được xác định từ dữ liệu được phép trong train. Chia theo thời gian và theo người học/họ bài tùy mục tiêu tổng quát hóa; đổi tên biến trong cùng mẫu không tạo một bài kiểm tra chuyển giao độc lập.

Không bê nguyên các ngưỡng “AUC +0,03” hoặc “Brier giảm 10%” thành chuẩn khoa học. Chọn một mục tiêu chính, ngưỡng tổn hại và yêu cầu về chi phí trước thử nghiệm xác nhận; báo cả kết quả âm. Không gộp mọi thứ thành một chỉ số duy nhất che mất thời gian người học hoặc chất lượng dạy.

## 8. Các kiểm tra hành vi cần có khi triển khai

Đây là kế hoạch test tương lai, chưa phải test đã chạy:

1. Một câu trả lời đúng sau khi xem gợi ý không bị ghi là sai, cũng không thành bằng chứng làm độc lập.
2. Lượt sai trước trợ giúp, lượt sửa sau trợ giúp và bài mới làm độc lập được phân biệt đúng.
3. Timeout/compiler thiếu môi trường/hủy bài không làm giảm trạng thái người học.
4. Code hoặc rubric đổi phiên bản khiến bằng chứng cũ được nhận diện là khác phạm vi; nguồn không tồn tại không được trình bày như đã kiểm chứng.
5. Nhận xét LLM thiếu nguồn hoặc trái kết quả kiểm tra không tự nâng trạng thái; đánh giá chưa chắc có thể trả về chưa đủ bằng chứng.
6. Replay giữ đúng thứ tự nhận định–kết quả, tránh ghi trùng khi retry; xuất/xóa bao phủ dữ liệu của người học mà không ảnh hưởng người khác.
7. Chế độ giải thích/hướng dẫn giữ repo chỉ đọc; “làm giúp” không biến thành thành tích của người học; luật dạy không cấp thêm quyền thực thi.
8. Đường LLM lỗi vẫn cho xem nội dung soạn sẵn và tiếp tục/dừng phiên rõ ràng; số liệu latency không bỏ qua các lần lỗi hoặc hủy.

Chạy kiểm tra theo phần thực sự đổi và một vòng tích hợp/black-box tương ứng; chỉ mở rộng khi có dependency hoặc lỗi mới. Giữ test hành vi hiện tại tách khỏi fixture xác nhận lịch sử, không tái tạo cấu trúc phase cũ trong bộ test học tập mới.

## 9. Điều kiện giữ dự án gọn

Trong nhánh Teacher, ưu tiên **M0 → M1 → M2**, phối hợp với lộ trình ba chế độ ở tài liệu liên kết. Chỉ mở M3/M4 khi có câu hỏi chưa được cách đơn giản giải quyết. Không thêm model, graph, event type, agent hay màn hình nếu chưa chỉ ra người dùng cần quyết định gì và thành phần đó giúp ra sao.

Mốc gần nhất đáng làm là một trải nghiệm: **mở code → thử giải thích → nhận gợi ý có nguồn → làm bài khác → xem mình đã làm được gì**. Đây là phần cần chứng minh trước khi đầu tư thêm vào một hệ thống tự đánh giá phức tạp.
