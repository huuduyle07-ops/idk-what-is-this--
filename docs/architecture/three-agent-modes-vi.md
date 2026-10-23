# C.A.T.T.U.S: ba chế độ agent trên nền tảng chung

Ngày: 2026-10-22. Trạng thái: **thiết kế đề xuất, chưa triển khai router hoặc workflow mới**.

Tài liệu này bổ sung định hướng ba chế độ do người dùng đề xuất sau [kế hoạch tutor](tutor-learning-plan-vi.md). Các chế độ có mục tiêu, đầu ra và trạng thái riêng; dùng chung khả năng đọc code, model adapter, lưu bằng chứng, kiểm chứng và thực thi. Đề xuất giữ một repository và một ứng dụng trong giai đoạn đầu; tách repository chỉ khi có nhu cầu phát hành, dependency hoặc cách vận hành độc lập đã rõ.

## 1. Ba chế độ và giá trị riêng

| Chế độ | Câu hỏi người dùng muốn giải quyết | Đầu ra chính | Thước đo phù hợp |
| --- | --- | --- | --- |
| **Coding agent** | “Hãy giúp tôi sửa hoặc xây chức năng này.” | Thay đổi code có phạm vi, kết quả kiểm tra, phần chưa xác minh | Đáp ứng yêu cầu, regression, thời gian đến kết quả, chi phí |
| **Teacher agent** | “Hãy giúp tôi hiểu và tự làm được.” | Giải thích có nguồn, gợi ý, bài vận dụng, nhận xét dựa trên bài làm | Khả năng làm độc lập/chuyển giao/nhớ lại, thời gian học, chất lượng phản hồi |
| **Self-evaluating / Decision-making agent** | “Nhận định này đáng tin đến đâu, nên chọn gì hoặc kiểm tra thêm gì?” | Phương án, bằng chứng/điểm chưa biết, đề xuất bước tiếp theo, điều kiện đổi quyết định | Sai lầm quyết định, khả năng nhận ra thiếu bằng chứng, giá trị của kiểm tra bổ sung so với thời gian/chi phí |

Teacher vẫn là hướng khác biệt đã xác định trước; coding có chế độ sử dụng hoàn chỉnh riêng. Decision có thể chạy độc lập, không bị thu hẹp thành một màn hình thống kê của hai chế độ kia. Ba chế độ không mặc định là ba model, ba tiến trình hoặc ba lượt gọi nối tiếp cho mọi yêu cầu.

**Ưu tiên triển khai đã chốt với người dùng: Teacher trước.** Giữ kiến trúc ba chế độ, nhưng mốc sản phẩm đầu tiên là một vòng học hoàn chỉnh. Tận dụng Coding hiện có cho ngữ cảnh và kiểm chứng; phần đánh giá/chọn bước tiếp theo phục vụ Teacher trước. Workflow và UI Decision độc lập được triển khai sau khi vòng học đầu tiên đạt tiêu chí nghiệm thu. Teacher không phải chờ cả ba chế độ hoàn thiện.

**Phạm vi khởi đầu đã chốt với người dùng:** quyết định về code và việc học; mở rộng sang lĩnh vực khác sau. Bản đầu tập trung vào đánh giá bản sửa, so sánh phương án kỹ thuật, chọn kiểm tra tiếp theo và chọn bước học dựa trên bằng chứng. Quyết định về người học sử dụng rubric và lịch sử bài làm riêng.

Kiến trúc cho phép thêm adapter lĩnh vực khác. Tiêu chí mở rộng đề xuất: có nhu cầu cụ thể, nguồn bằng chứng và cách quan sát kết quả; có baseline để so chất lượng quyết định, thời gian và chi phí; đường code/việc học đã qua các kiểm tra hành vi tương ứng. Mở từng lĩnh vực với bộ đánh giá riêng, không suy rộng độ tin cậy từ kết quả coding sang mọi loại quyết định.

## 2. Chế độ thứ ba có hai cách sử dụng

**Chạy độc lập:** người dùng đưa mục tiêu, phương án hoặc một nhận định cần xem lại. Workflow xác định điều cần đánh giá, thu thập bằng chứng trong phạm vi, so phương án và cân nhắc có đáng kiểm tra thêm không. Kết quả có thể là chọn một phương án, giữ nguyên, cần thêm quan sát, cần làm rõ mục tiêu hoặc chưa đủ căn cứ kết luận. Sau khi có kết quả thực tế, hệ thống đối chiếu lại nhận định cũ.

Ví dụ: “Nên refactor lớp này hay chỉ sửa lỗi hiện tại?”, “Kết quả test này đã đủ để tin bản vá chưa?”, “Người học nên thử bài khác hay cần một gợi ý nữa?”. Ví dụ cuối dùng bộ đánh giá dành cho người học; không tái sử dụng trực tiếp điểm chất lượng patch.

**Cung cấp khả năng đánh giá cho hai chế độ khác:** Coding gọi bộ kiểm tra patch; Teacher gọi bộ đánh giá bài làm. Chúng có thể dùng chung contract bằng chứng và ghi nhận nhận định–kết quả. Không cần khởi động toàn bộ workflow Decision cho mỗi lần kiểm tra, cũng không dùng một rubric chung cho patch, năng lực người học và lựa chọn kiến trúc.

Tách hai trách nhiệm bên trong:

- **Evaluation:** bằng chứng nào ủng hộ hoặc phản bác phát biểu, phạm vi đã kiểm tra, điều gì chưa biết, kết quả nào còn mâu thuẫn.
- **Decision:** với những điều đó cùng mục tiêu, ưu tiên và ngân sách, bước tiếp theo nào phù hợp.

Ưu tiên “nhanh hơn” có thể khiến hệ thống chọn ít kiểm tra hơn và báo phần còn chưa xác minh. Nó không được tự làm tăng độ tin cậy của cùng một nhận định trên cùng bằng chứng. Nếu thay đổi mục tiêu hoặc phạm vi cần chứng minh, phải ghi rõ đối tượng đánh giá đã đổi.

## 3. Luồng chạy của từng chế độ

| Chế độ | Luồng tối thiểu |
| --- | --- |
| Coding | Yêu cầu → đọc ngữ cảnh cần thiết → đề xuất/thực hiện thay đổi trong quyền hiện có → kiểm tra → kết quả và giới hạn |
| Teacher | Mục tiêu học → code liên quan → giải thích hoặc câu hỏi → bài làm/gợi ý → đánh giá có phạm vi → bài vận dụng khác/ôn lại |
| Decision | Mục tiêu và phương án → bằng chứng → đánh giá → cân nhắc kiểm tra bổ sung → khuyến nghị/bước tiếp theo → đối chiếu với kết quả khi có |

Mỗi vòng có giới hạn thời gian, số lần kiểm tra và model calls do runtime thực sự áp dụng. Khi hết ngân sách, trả lời với phạm vi đã kiểm tra; không tự kéo dài vòng “nghĩ lại”. Báo cáo budget preview hiện có không tự đáp ứng yêu cầu enforcement này.

Self-evaluation sử dụng kết quả công cụ, nguồn được tham chiếu, rubric và kết quả thực tế khi có. Việc model đồng ý với câu trả lời trước của nó chỉ là một nhận xét bổ sung. Không mặc định coi nhiều lượt tự phê bình là nhiều nguồn bằng chứng độc lập. Giai đoạn đầu chưa bao gồm tự huấn luyện model hoặc tự sửa chính sách đang chạy.

## 4. Ranh giới quyền và dữ liệu

**Chọn chế độ xác định cách phục vụ yêu cầu. Quyền thực thi được kiểm tra riêng tại runtime.**

- Coding không tự có quyền sửa mọi file chỉ vì người dùng chọn tab Coding. Duy trì phạm vi và quyền đã được cấp cho yêu cầu hiện tại.
- Teacher đọc repo để dạy; chạy bài trong môi trường bài tập khi được phép. “Làm giúp tôi” chuyển thành yêu cầu Coding với phạm vi rõ. Tận dụng quyền người dùng đã cấp, không thêm một vòng xin phép khi quyền đó đã đủ.
- Decision có thể đề xuất hoặc yêu cầu kiểm tra trong phạm vi được phép. Nhãn “đủ bằng chứng” không phải giấy phép apply patch, triển khai hoặc mở rộng phạm vi.
- Đổi chế độ không tự tái sử dụng quyền của phiên khác. Handoff mang theo mục tiêu, nguồn và phần đã xác minh; không sao chép quyền thực thi một cách mù quáng.

Chia sẻ schema/provenance không đồng nghĩa chia sẻ mọi dữ liệu. Tách bài làm người học, tri thức sửa lỗi của agent, artifact coding và lịch sử quyết định theo owner, namespace và chính sách truy cập/lưu/xóa. Không ghi lời giải do Coding tạo thành thành tích làm độc lập của người học.

Code/evidence gắn với revision hoặc content hash và phiên bản bộ đánh giá. Không dùng kết quả của snapshot trước như bằng chứng hiện tại khi code đã đổi. Việc ghi nhận bài học từ thất bại phải giữ nguồn và phạm vi; không tự biến một suy đoán trong hội thoại thành tri thức đã kiểm chứng.

## 5. Cấu trúc và contract đề xuất

Giữ các ranh giới theo [kế hoạch tổ chức repository](repository-organization.md). Cấu trúc sau là đích thiết kế, không phải danh sách package đã tồn tại hoặc yêu cầu tạo tất cả ngay:

```text
core/
  workflows/       điều phối riêng coding, teacher, decision; adapter entrypoint
  context/         đọc và tìm nguồn, code graph
  coding/          patch và kiểm chứng code
  learning/        phiên học, bài làm, rubric, learner state
  evaluation/      contract bằng chứng/đánh giá; chưa cần mô hình học máy
  runtime/         thực thi, quyền và budget
  governance/      báo cáo và bằng chứng lịch sử
tests/
  <nhóm tương ứng với trách nhiệm trên>
  integration/     routing, handoff, giới hạn quyền, tách dữ liệu
```

Ưu tiên adapter và owner nhỏ ở ranh giới thật. Không sao chép pipeline cho ba mode, không biến `evaluation/` thành nơi chứa mọi logic, và không chuyển cả họ file cùng lúc với việc thêm hành vi mới.

Đề xuất contract logic tối thiểu: yêu cầu có chế độ/mục tiêu/phạm vi/ngân sách; đánh giá có đối tượng/phiên bản/bằng chứng/kết quả/giới hạn; quyết định có phương án được chọn hoặc chưa chọn/lý do/kiểm tra tiếp theo. Trạng thái quyền vẫn do owner runtime hiện có quản lý. Chỉ chuẩn hóa phần được ít nhất hai workflow thực sự dùng; chưa cần thêm nhiều lớp hay schema tổng quát.

## 6. Điểm cần lưu ý trong mã hiện tại

Đọc có chọn lọc cho thấy [`AgentState`](../../core/agent_state.py) đang có `interface`, `mode`, `live_route` và `harness_mode`. Các trường này mang trách nhiệm khác nhau; không gộp chúng thành một enum ba giá trị.

- [`prompter.build_prompt`](../../core/prompter.py) dùng `human + tutor/explainer` và `agent + reviewer/planner`. Đây là vai trò/prompt hiện tại, chưa phải ba chế độ sản phẩm mới.
- [`web.runner.run_agent_web`](../../web/runner.py) đang đổi `agent_mode` ngoài `reviewer/planner` thành `reviewer`. Chỉ thêm lựa chọn Teacher/Decision trên UI sẽ không tạo routing đúng.
- [`live_task_routing`](../../core/live_task_routing.py) xác định workflow trước bước đọc/indexing/CONTROL và tách route khỏi quyền apply. Duy trì thứ tự này để câu hỏi giải thích/so sánh không đi qua đường sửa patch không cần thiết.
- [`main.py`](../../main.py) đã tránh chạy planner execution khi route chỉ đọc. Không phá ranh giới này khi thêm chế độ sản phẩm.

Đề xuất thêm lớp lựa chọn `product_mode = coding | teacher | decision` và adapter tương thích ở entrypoint. Chưa thay giá trị `mode` trong artifact cũ; mapping cũ phải có phiên bản và kiểm tra tương thích. Request mới có mode không hợp lệ phải báo rõ, không âm thầm rơi về Coding. UI, CLI và API cần dùng cùng contract routing; legacy payload đi qua adapter riêng.

## 7. UI và thứ tự triển khai

UI đích có ba lựa chọn **Code — Học — Đánh giá & quyết định**, cho phép đổi mục tiêu có chủ đích và thấy chế độ đang hoạt động. Bản đầu ưu tiên lối vào Học rõ ràng và giữ đường Code hiện có. Chỉ đưa Decision vào lựa chọn sử dụng khi có workflow độc lập hoạt động; không cần một tab chưa có chức năng để đáp ứng sơ đồ ba chế độ. Đừng đưa mọi setting của ba workflow vào một màn hình chung.

Trong Teacher, “Giải thích ngay” và “Hướng dẫn tôi” là hai cách tương tác. “Làm giúp” là điểm chuyển sang Coding. Decision hiển thị phương án, căn cứ, phần chưa biết và bước tiếp theo; không mở đầu bằng một dashboard đầy điểm confidence thiếu căn cứ.

1. **Chuẩn bị đúng phần Teacher cần.** Chốt entrypoint, mapping cũ/mới, phạm vi chỉ đọc, owner phiên học và cách lưu bài làm. Xử lý dependency/test lịch sử liên quan đến các file thực sự đổi. Chỉ tái cấu trúc phần đang cản trở đường học; không chờ hoàn tất việc di chuyển toàn bộ core/test hoặc một framework điều phối tổng quát.
2. **Làm vòng Teacher hoàn chỉnh, gồm UI.** Chọn code → giải thích hoặc hướng dẫn → bài làm/gợi ý → phản hồi có bằng chứng → bài vận dụng khác → lưu/mở lại phiên. Dùng luật/rubric cho đánh giá và chọn bước tiếp theo; không cần khởi động một agent Decision riêng cho mỗi lượt. Giữ đường Coding và hành vi cũ tương thích.
3. **Nghiệm thu và thử dùng Teacher.** Kiểm tra chỉ đọc, tách dữ liệu, mức trợ giúp, lỗi công cụ và nguồn phản hồi; đo thời gian chờ và model calls. Tiếp tục M2 của kế hoạch tutor để kiểm tra vận dụng/nhớ lại với người thật. Dùng các lỗi quan sát được để ưu tiên sửa trải nghiệm.
4. **Bổ sung Decision độc lập và handoff.** Sau khi vòng Teacher đầu tiên đạt nghiệm thu, dùng các nhu cầu đã quan sát để chốt contract đánh giá dùng chung, rồi thêm so phương án/nhận định–kết quả và UI Decision. Đo riêng từng đường và phần chuyển chế độ; phát triển Coding thêm khi có nhu cầu cụ thể. Không bắt mọi request đi qua một lượt agent đánh giá mới.
5. **Thử mô hình học và mở rộng lĩnh vực theo bằng chứng.** Learner model, calibration và chính sách chọn kiểm tra mới được thử ngoài luồng quyết định trước. Các bước này không chặn Teacher hoặc Decision dựa trên luật. Lĩnh vực ngoài code/việc học tiếp tục nằm sau phạm vi ban đầu đã chốt.

Dream là cách lên lịch công việc nền cho workflow phù hợp, không phải chế độ sản phẩm thứ tư. Có thể chuẩn bị bài học hoặc báo cáo đánh giá; hành động thực thi vẫn theo quyền và kiểm tra của mode tương ứng. Không dùng hoạt động ban đêm để giả lập thành tích học của người dùng.

## 8. Kiểm tra hành vi bắt buộc khi triển khai

- Cùng một yêu cầu có thể tạo đầu ra khác theo mode, nhưng không âm thầm đổi mục tiêu hoặc mở rộng quyền.
- Mode mới không bị ép thành `reviewer`; legacy CLI/web payload vẫn đúng hành vi đã công bố. Một quyết định chỉ đọc không kích hoạt patch pipeline chỉ vì role nội bộ là planner.
- Teacher/Decision không ghi vào source repo ngoài một yêu cầu thay đổi đã được cấp quyền; tool/check được phép vẫn phải đi qua runtime boundary.
- Đổi ưu tiên tốc độ/rủi ro với cùng câu hỏi và bằng chứng có thể đổi hành động được đề xuất, không đổi sự thật hoặc mức hỗ trợ của bằng chứng.
- Cùng model tự nhận xét lại không được ghi thành nguồn kiểm chứng độc lập; thiếu bằng chứng có thể kết thúc ở chưa kết luận.
- Handoff không lẫn learner state, artifact hoặc quyền giữa phiên/repo; kết quả Coding không thành bài làm độc lập.
- Giới hạn thời gian/model calls có hiệu lực khi chạy thật; lỗi checker được phân biệt với ứng viên sai; kết quả cũ bị nhận diện khi snapshot đổi.

Các kiểm tra trên là yêu cầu cho bước triển khai tiếp theo, chưa được báo cáo là đã pass. Lượt lập kế hoạch này chỉ bổ sung tài liệu và liên kết tới mã đã đọc.
