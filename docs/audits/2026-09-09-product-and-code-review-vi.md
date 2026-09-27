**Đánh giá C.A.T.T.U.S dưới góc độ sản phẩm, khách hàng và kỹ thuật — 09/09/2026**

**Khắc phục 11/09/2026:** Mười hợp đồng từng fail trong đợt black-box đã được sửa; 55 ca tích hợp chung và 3 ca HTTP bổ sung đều pass. Xem [báo cáo khắc phục](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-11-harness-remediation-vi.md) và [dữ liệu sau sửa](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-11-harness-remediation-results.json). Các kết luận và số liệu bên dưới được giữ làm mốc lịch sử trước sửa; các phát hiện audit cũ ngoài phạm vi này chưa được đóng.

**Cập nhật 10/09/2026:** Đã bổ sung 28 ca black-box qua HTTP, CLI, coding revision và Dream: **18 pass / 10 fail**. Revision một lần và vòng HTTP review→Apply có bằng chứng hoạt động thật, với model giả lập. Tuy nhiên, CLI planner đã sửa source khi `AUTO_PATCH_ENABLED=false`; ba giới hạn coding và ba lỗi Dream còn làm giảm độ tin cậy. Kết luận chưa mua để giao codebase quan trọng/night-shift tự chủ giữ nguyên. Xem [báo cáo cập nhật đầy đủ](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-10-harness-blackbox-update-vi.md) và [kết quả từng ca](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-10-harness-blackbox-results.json). Nội dung dưới đây là mốc audit 09/09; các kiểm tra cũ không chạy lại và chưa được coi là đã sửa.

**Kết luận:** C.A.T.T.U.S có một lõi kỹ thuật đáng giữ: tìm bằng chứng trong repository, kiểm chứng bản sửa, phân biệt kiểm chứng với quyền thực thi, và lưu lại kết quả để review. Tuy nhiên, hiện nó phù hợp hơn với một công cụ nghiên cứu/điều hành có người giám sát hơn là sản phẩm coding agent phổ thông có thể bán ngay. Phần cần gọt mạnh nhất là hệ thống báo cáo, checkpoint, kế hoạch và giao diện cho các khả năng còn thử nghiệm.

Tôi sẽ chưa mua bản hiện tại làm công cụ coding hằng ngày. Tôi có thể cân nhắc một pilot có hỗ trợ cho bài toán kiểm chứng bản sửa, sau khi xử lý các lỗi trực tiếp ảnh hưởng quyền sửa và tính toàn vẹn file. Nhận định này không có nghĩa repository không có giá trị: giá trị nghiên cứu, kiến thức kỹ thuật và tài sản kiểm chứng hiện rõ hơn giá trị thương mại đã được chứng minh.

**Phạm vi và mức chắc chắn**

Đọc cấu trúc, luồng chạy chính, patch/validation, web/session, benchmark, cấu hình và một số tài liệu mới nhất; kết hợp phân tích AST với ba nhánh review độc lập. Đánh giá working tree hiện tại, gồm các file chưa commit, không chỉ HEAD. Trước khi viết báo cáo, trạng thái Git có 49 file modified và 206 đường dẫn untracked.

Không sửa code sản phẩm, không gọi model trả phí, không chạy benchmark tác giả bản sửa bằng LLM, không kiểm tra giao diện bằng trình duyệt, không chạy lại toàn bộ test suite. Các tái hiện lỗi chỉ dùng file tạm, dữ liệu giả và model/validation giả tại ranh giới thích hợp. Các kết luận về khả năng sửa thực tế của model vì thế được giữ ở mức chưa xác nhận.

**Quy mô đo được**

| Khu vực | Quy mô |
|---|---:|
| core | 323 file Python; 221.808 dòng |
| scripts | 161 file Python; 27.895 dòng |
| tests | 434 file Python; 205.445 dòng |
| web/app.py | 4.157 dòng |
| web/templates/index.html | 11.081 dòng |
| web/static/style.css | 6.724 dòng |
| README.md | 2.228 dòng |
| Registry roadmap | 169 phase: 165 complete, 3 proposed, 1 active |

Đây là dòng vật lý, gồm comment, docstring, dữ liệu và khoảng trắng; không phải số dòng logic thực thi. Đếm bằng AST không thấy lỗi cú pháp trong 1.027 file Python thuộc phạm vi quét.

Có 150 module core không xuất hiện trong closure import tĩnh bắt đầu từ main, CLI, web và hai MCP entrypoint. Đây chỉ là danh sách điều tra để phân tách runtime/tooling: script độc lập, import động và cách import tương đối có thể khiến phân tích bỏ sót. Không được dùng con số này làm “150 file chết” hay danh sách xóa tự động. [Dữ liệu đo](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/.tmp/repository-audit-metrics-20260909.json).

**Giá trị riêng đáng giữ**

1. **Bản sửa phải gắn với bằng chứng và mục đích cụ thể.** Các module patch_basis, execution_eligibility_policy, human_apply_authorization và candidate_verification đi xa hơn việc tin confidence do LLM tự khai. Điều này có thể trở thành lớp kiểm soát bổ sung cho agent khác.
2. **Kiểm chứng cả sửa đúng lỗi lẫn giữ nguyên hành vi cần giữ.** Có kiểm thử production branch cho bản sửa “hết lỗi chính nhưng gây regression” bị từ chối và bản sửa đúng được xác minh, trong khi repository thật không đổi. [Hai trường hợp kiểm thử](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/tests/test_candidate_verification.py:1171), [ma trận kết quả](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/designs/2026-09-08-read-only-candidate-verification-before-human-review.md:230). Các candidate được cung cấp có chủ đích; đây không phải bằng chứng model tự sinh được bản sửa đúng.
3. **Ghi nhận kết quả trung thực.** Phân biệt pass/fail/inconclusive, thiếu toolchain và timeout giúp tránh đánh đồng “chưa kiểm được” với “đã sửa đúng”. Replay, diff, thời gian và receipt giúp người review lần lại quyết định.
4. **Bảo vệ test/oracle và đường dẫn.** Các gate chặn sửa test hay oracle benchmark để đạt điểm giả là hợp lý trong chế độ sửa lỗi có kiểm soát. [patch_safety.py](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/patch_safety.py:1). Với yêu cầu thêm tính năng tổng quát, cần một workflow riêng cho phép thêm/sửa test có quyền rõ ràng; không nên quảng bá mọi workflow hiện tại như một agent phát triển phần mềm toàn diện.
5. **Memory có nguồn gốc và phạm vi.** Lesson chất lượng, được duyệt và áp dụng đúng repository có thể giảm lỗi lặp lại. [lesson_quality.py](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/lesson_quality.py:40), [lesson_retrieval.py](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/lesson_retrieval.py:98). Đây là giả thuyết giá trị cần đo bằng đối chứng bật/tắt. Code mặc định tắt retrieval, còn .env.example bật nó; auto-activation và nhiều thử nghiệm memory vẫn tắt. Không thể mặc định kết luận hệ thống tự học hiệu quả.
6. **Benchmark và quan sát chi phí là tài sản tái sử dụng.** Runner gọi production pipeline trên repository tạm, xác thực độc lập và theo dõi token/fallback/chi phí. Nên giữ bộ khung này khi thu gọn sản phẩm.

Graph, nhiều model, MCP hay một dashboard nhiều tab tự thân chưa phải lợi thế khó sao chép. Sự kết hợp bằng chứng, kiểm chứng hành vi và dữ liệu lỗi đã được review mới có cơ hội tạo khác biệt. Hiện chưa tìm thấy bằng chứng trong phần đã kiểm tra cho thấy tổ hợp này thắng phương án đơn giản hơn trên tác vụ khách hàng.

**Các vấn đề kỹ thuật ưu tiên**

| Ưu tiên | Phát hiện và ảnh hưởng | Hướng xử lý |
|---|---|---|
| P1 | Retry có thể nhận candidate khác file, needs_escalation=true và basis insufficient_evidence nhưng vẫn đi vào Executor. Callback chọn confidence cao nhất và chuyển tiếp payload mà không chạy lại đủ bước grounding/eligibility. | Mỗi candidate mới phải trở lại một điểm kiểm chứng và cấp quyền chung, gắn fingerprint của candidate, phạm vi file và bằng chứng hiện hành. |
| P1 | Single-file patch với CRLF có thể biến xuống dòng thành CRCRLF, gồm cả dòng không được sửa. | Dùng primitive ghi theo byte chung cho single-file và multi-file; kiểm tra chỉ byte trong vùng sửa thay đổi. |
| P1 | Backup dùng cố định tên file.bak: có thể ghi đè backup người dùng rồi xóa nó khi cleanup, kể cả lúc bản sửa bị chặn sau apply. | Backup thuộc riêng run, tên duy nhất và ownership rõ ràng; restore/cleanup chỉ chạm bản sao của run đó. |
| P1 khi đưa lên mạng | WEB_AUTH_TOKEN bảo vệ mutation; GET đi qua mà không xác thực, trong khi history endpoint trả session. | Localhost là profile mặc định. Trước khi cung cấp team/server, bảo vệ cả đọc lẫn ghi và phân quyền repository/session. |
| P2 | Session store read-modify-write nguyên một file JSON, không transaction; hai thao tác cùng đọc snapshot có thể ghi đè kết quả nhau. | SQLite transaction hoặc cơ chế lưu có kiểm soát concurrency; atomic write đơn thuần chưa giải quyết lost update. |
| P2 | Benchmark ghi unexpected mutations nhưng không dùng chúng trong pass/fail. | Sửa ngoài phạm vi source được phép phải fail; tách artifact hợp lệ khỏi source ngoài phạm vi. |
| P2 | Web indexing yêu cầu graph mới nên bỏ fast path khi repository không đổi. | Cache graph và parser results theo version nội dung/parser/policy, với kiểm tra freshness; đo thời gian cold/warm trước và sau. |

Dẫn chứng:

- Retry: [pipeline.py:2585](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/pipeline.py:2585), [self_correct_loop.py:75](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/self_correct_loop.py:75), [self_correct_loop.py:144](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/self_correct_loop.py:144). Các gate đường dẫn/risk của Executor vẫn tồn tại; lỗi là không tái xét đầy đủ basis/scope/approval cho candidate mới, không phải mất mọi bảo vệ.
- CRLF: [patch_engine.py:283](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_engine.py:283) đọc byte giữ CRLF, sau đó [patch_engine.py:309](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_engine.py:309) ghi text với newline CRLF, gây dịch newline thêm một lần. Bộ test byte-fidelity hiện có tập trung multi-file: [test_patch_write_byte_fidelity.py:1](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/tests/test_patch_write_byte_fidelity.py:1).
- Backup: [patch_engine.py:63](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_engine.py:63).
- Web read: [auth_gate.py:80](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/auth_gate.py:80), [history_routes.py:32](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/routes/history_routes.py:32), [app.py:176](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:176).
- Session: [session_store.py:10](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/session_store.py:10), [session_store.py:19](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/session_store.py:19).
- Benchmark scoring: [run_benchmarks.py:773](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/benchmarks/run_benchmarks.py:773).
- Index: [web/runner.py:565](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/runner.py:565), [indexer.py:163](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/indexer.py:163).

Một giới hạn triển khai cần nói đúng: bản sao repository trong thư mục tạm bảo vệ workspace gốc khỏi thao tác patch có kiểm soát; nó không tự cách ly process khỏi máy chủ. Candidate validation gọi apply/validation trong bản sao, vẫn có đường chạy command trên host. [candidate_sandbox_validation.py:617](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/candidate_sandbox_validation.py:617), [validator.py:310](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/validator.py:310). Có backend Docker ở nơi khác trong code, nhưng điều đó không chứng minh nhánh candidate này dùng Docker. Nếu nhận repository không tin cậy, cần nối nhánh đó với môi trường cách ly OS thực sự. Không suy diễn đây là một khai thác từ xa đã được chứng minh.

**Gọt bớt từ chức năng đến file**

Nguyên tắc: trước tiên bỏ khỏi luồng mặc định hoặc chuyển vị trí; chỉ xóa sau khi kiểm tra caller, CLI công khai, artifact schema và kiểm thử. Không gộp các khái niệm evidence, verification và authorization thành một boolean “safe”.

| File hoặc nhóm cụ thể | Quyết định |
|---|---|
| core/candidate_verification.py, paired_defect_probe.py, patch_basis.py, human_apply_authorization.py, execution_eligibility_policy.py | Giữ và làm thành lõi kiểm chứng/cấp quyền rõ ràng. |
| core/validation_outcome.py, validation_execution.py, validation_bytecode_cache.py, replay_recorder.py | Giữ; thống nhất đường gọi và semantics giữa CLI, web, retry và queue. |
| core/lesson_quality.py, lesson_store.py, lesson_retrieval.py | Giữ tối giản; đo mức giảm lỗi lặp lại trước khi mở rộng thuật toán memory. |
| core/control_engine.py; core/pipeline.py; core/indexer.py | Giữ nhưng tách theo stage/coordinator. pipeline 2.656 dòng; maybe_run_auto_patch dài 599 dòng; index_repository dài 1.016 dòng. Tách quanh trách nhiệm và invariant, không theo mục tiêu số dòng tùy ý. |
| web/app.py | Tiếp tục tách Flask blueprints cho Dream, intake, benchmarks, lessons/workers; đưa tác vụ nghiệp vụ ra khỏi route. Không cần đổi framework. |
| web/templates/index.html; web/static/style.css | Tách partial và JS/CSS theo workflow. Một màn hình chính: repository → yêu cầu → bằng chứng/diff → kiểm chứng → áp dụng → kết quả. |
| core/model_role_planning_checkpoint.py; core/run_progress_visibility_branch_checkpoint.py; core/dual_graph_lifecycle.py | Chuyển sang tooling/governance hoặc research. Chúng tạo/check báo cáo, không trực tiếp route model hay xây graph. Không gọi chúng là code chết. |
| core/commander_run_contract.py; driver_model_routing.py; model_role_registry.py | Giữ sau experimental/operator profile. Hợp đồng lập kế hoạch không tương đương orchestration đã chạy; đừng tính hai loại như nhau trong trang tính năng. |
| core/n8n_orchestration_dry_run.py; telegram_evidence_contract.py; github_pr_safety_contract.py | Chuyển sang examples/experimental cho đến khi có nhu cầu tích hợp thực. Những file này chưa chứng minh đã gửi thông báo hay vận hành dịch vụ liên quan. |
| core/mirror_tunnel_*; memory_temperature_*; reverse_dream_planner.py | Hoãn mở rộng; chỉ giữ công cụ được dùng và có tiêu chí thắng thua. Chúng có thể hữu ích cho nghiên cứu, chưa có dữ liệu đủ để bắt người dùng thường học chúng. |
| core/sleeping_consultant.py | Giữ queue/điều tra có kiểm chứng nếu đó là workflow được sử dụng. Thu hẹp lời hứa Dream thành điều tra và đề xuất bản sửa, đo chi phí/tỷ lệ hữu ích. |
| core/sandbox_self_evolution_runner.py và các review/evidence-pack liên quan | Profile thử nghiệm. Runner chạy validation trong sandbox thực; không đồng nghĩa tự gọi model và tự sinh cải tiến. |
| graph/project_map.py; core/repository_inventory.py | Giữ làm nền context. Obsidian export và graph debug là tùy chọn. |
| graph/attraction.py | Explain-only; tách khỏi phần giới thiệu khả năng tìm code trừ khi có số đo giúp người dùng. |
| core/project_map_v2.py | Hợp nhất policy scan/ignore với inventory dùng chung; giữ schema đầu ra nếu cần. |
| core/repo_inventory.py | Không xóa vì tên giống repository_inventory: đây là compatibility facade có chủ đích. |
| scripts/create_*checkpoint*.py, create_*plan*.py, create_*report*.py | Gom cách parse args/IO/render vào một CLI audit nhỏ; báo cáo phase đã kết thúc có thể lưu thành dữ liệu tĩnh. Không xây thêm một workflow engine lớn để giải quyết script sprawl. |
| tests/test_phase_registry.py và test roadmap lịch sử | Giữ kiểm tra schema/invariant, chuyển kỳ vọng “phase tiếp theo phải là X” sang fixture. Tests không nên cần trạng thái lịch sử từ .agent bị ignore. |
| Các test đóng băng SHA toàn file | Dùng khi thật sự cần phạm vi thử nghiệm bất biến; tránh biến chúng thành gate sản phẩm vĩnh viễn khiến đổi comment cũng bị coi là regression. |
| package.json; package-lock.json | Ứng viên xóa: chỉ có dependency motion, không tìm thấy import trong web/package hoặc build script sử dụng. Kiểm tra asset/browser trước khi xóa. |
| README.md; SETUP.md; .env.example | Viết lại quickstart ngắn, nhất quán một Python được hỗ trợ và profile tùy chọn DB/embedding. Đưa lịch sử phase sang docs. |
| agents/deepseek_client.py | Đổi abstraction thành reviewer/provider đúng nghĩa. Hiện gọi Ollama rồi fallback Google, không dùng DeepSeek API như tên và setup dễ khiến người đọc nghĩ. |
| database/memory_consolidator.py::consolidate | Legacy: deprecate/migrate theo caller; nếu giữ, thay thế memory phải transaction. Không xóa toàn bộ module vì consolidate_all còn được web gọi. |

Những tên như Commander, Mayor, Dream, Mirror Tunnel có thể giữ như thương hiệu, nhưng người dùng không nên phải hiểu chúng để sửa một lỗi. Giao diện có thể hiện tên hành động cụ thể và đặt thuật ngữ nội bộ ở phần nâng cao.

**Bằng chứng chất lượng hiện tại nói được gì?**

- 54 benchmark case trên 8 ngôn ngữ. Trung vị 2 source file và 43 dòng source/case; khoảng 1–6 file, 18–173 dòng.
- 51 case kỳ vọng sửa một file, 3 case không sửa, 0 case yêu cầu sửa nhiều file. “Multi-file root cause” không đồng nghĩa benchmark sửa nhiều file.
- 50/54 prompt nói rõ target_snippet. Bộ này mạnh ở regression nhỏ và bẫy cụ thể, yếu ở việc chứng minh tiếp nhận yêu cầu mơ hồ trên repository lớn.
- held_out_v1 hiện có 15 case, README còn nói 7. Một số case đã trở thành regression development, nên không còn là bằng chứng “chưa từng nhìn thấy” thuyết phục. [manifest](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/benchmarks/suites/held_out_v1.json:5), [regression](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/tests/test_benchmark_failure_regressions.py:6).
- Chưa tìm được raw report đủ để tái dựng các claim lịch sử 7/7, 31/31 và cải thiện tốc độ trong checkout này. Điều đó có nghĩa chưa xác minh được, không khẳng định các claim sai.
- Tài liệu ngày 07/09 ghi broad suite 9.637 pass, 85 fail, 15 skip; 36 lỗi được clear bằng batch liên quan, còn 49 lỗi baseline. Tài liệu cũng nói chưa có broad run sạch. Đây là kết quả lịch sử do repository ghi nhận, không phải một lần full-suite tôi vừa chạy. [nguồn](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/designs/2026-09-07-entry-anchored-hypothesis-relevance.md:202).

**Nếu là khách hàng, tôi trả bao nhiêu và có tự làm không?**

Những mức dưới đây là ngưỡng sẵn lòng trả giả định của tôi theo tình huống, không phải định giá doanh nghiệp hay khảo sát thị trường. Giá tính USD; phí model/API riêng nếu ghi BYOK.

| Tình huống | Quyết định |
|---|---|
| Developer cá nhân mua coding assistant phổ thông, bản hiện tại | Chưa trả subscription; mức hiện tại của tôi là 0 USD/tháng cho mục đích này. Lý do: setup và review tốn công, chất lượng tác vụ thực chưa được chứng minh, còn lỗi ở đường sửa. |
| Nhóm nhỏ muốn đánh giá riêng khả năng kiểm chứng bản sửa | Sau khi khắc phục lỗi P1, cân nhắc pilot có hỗ trợ 100–300 USD một lần, trong phạm vi repo/tác vụ/tiêu chí cụ thể. Đây là tiền hỗ trợ và thử nghiệm, không phải bằng chứng sẵn sàng mua license đại trà. |
| Bản gọn, cài ổn, đo được tiết kiệm thời gian hoặc chặn regression | Cân nhắc 10–20 USD/người/tháng BYOK; hoặc 50–150 USD/nhóm nhỏ/tháng nếu có policy dùng chung, lưu trữ đáng tin cậy và hỗ trợ. Đây là giả thuyết giá cần kiểm tra. |
| Công ty lớn, yêu cầu triển khai team/server nghiêm túc | Chưa mua ở trạng thái hiện tại; repository chưa chứng minh đầy đủ phân quyền, isolation và vận hành cho tình huống này. |

Đối chiếu mặt bằng cạnh tranh ngày đánh giá: GitHub Copilot Pro niêm yết 10 USD/người/tháng; Cursor Pro 20 USD/tháng, Teams Standard 40 USD/người/tháng, với điều kiện usage riêng. Vì C.A.T.T.U.S còn có thể yêu cầu người dùng tự trả API, giá trị cộng thêm phải cụ thể. [GitHub Copilot](https://github.com/features/copilot/plans), [Cursor](https://cursor.com/pricing).

Nếu chỉ cần trợ lý viết code, tôi chọn công cụ sẵn có, không tự xây lại toàn bộ C.A.T.T.U.S. Nếu tổ chức cần chính sách kiểm chứng riêng mà chưa có sản phẩm phù hợp, tôi sẽ làm một lớp nhỏ quanh agent/model đang dùng: nhận diff → kiểm tra phạm vi → chạy test cách ly → ghi bằng chứng → người duyệt. Tôi chỉ mua C.A.T.T.U.S nếu nó giảm chi phí xây và bảo trì lớp đó. Điểm khó sao chép đáng đầu tư là tập bằng chứng thất bại thực, kiểm chứng đáng tin cậy và trải nghiệm review thuận tiện.

Không thể suy ra giá bán toàn bộ repository từ 200.000 dòng core, số phase hay số test. Thiếu doanh thu, retention, khách hàng, quyền phân phối và benchmark so sánh nên chưa có cơ sở định giá tài sản thương mại.

**Nó cần gì tiếp theo?**

Thứ tự sau là thứ tự hoàn thành, không phải cam kết lịch cố định:

1. **Chốt lời hứa:** “Kiểm chứng bản sửa của AI trên repository của bạn, cho thấy bằng chứng và yêu cầu duyệt đúng lúc.” Tập trung một phân khúc nhóm nhỏ cần review thay đổi; giáo dục và tự tiến hóa là mục tiêu riêng để sau.
2. **Khép đường sửa:** dùng cùng pipeline kiểm chứng/cấp quyền cho candidate đầu, retry, manual apply và queue; chung primitive ghi/rollback; xử lý CRLF và backup ownership. Nếu chưa hoàn tất, tắt đường tự áp dụng đang bị ảnh hưởng.
3. **Có một bản cài tái lập được:** thống nhất Python/requirements lock; smoke từ môi trường sạch; core test gate xanh trên Windows và Linux; tách integration/experimental/governance. Không cần PostgreSQL/embedding cho lần chạy tối thiểu nếu workflow không cần.
4. **Thu gọn runtime và UI:** tách tooling/governance/experimental, giữ một task/run/result format dễ đọc. Không thêm quyền hạn mới trong lúc tách module. README cho phép người mới chạy một ví dụ trong khoảng 10–15 phút.
5. **Đo trên tác vụ chưa thấy:** 3–5 developer, khoảng 20 tác vụ từ vài repo thật, gồm sửa nhiều file, lỗi giả, test nền đã đỏ, yêu cầu mơ hồ và regression. So agent/model hiện có với cùng model + C.A.T.T.U.S, cùng budget, lặp vài lần. Bộ dùng làm acceptance không dùng để tuning.
6. **Đo tiền và thời gian đúng đơn vị:** chi phí trên một bản sửa được chấp nhận, thời gian review của người, end-to-end latency p50/p95, false approval và false rejection, phần trăm cài đặt thành công. Giữ raw reports đã bỏ dữ liệu nhạy cảm, revision/model/config và kết quả lần đầu tách retry.
7. **Chỉ tối ưu thứ đo được:** ưu tiên graph/index cache cho lần chạy không đổi; thời gian tạo sandbox/validation; review model chỉ gọi khi có bằng chứng cần thêm. Bộ nhớ và graph phải chứng minh uplift bằng thí nghiệm bật/tắt. Không tăng số vòng tranh luận chỉ vì có thêm model.

Một ngưỡng quyết định pilot có thể dùng: đa số người thử tự cài được; không có mutation ngoài quyền trong bộ safety acceptance; thời gian review giảm khoảng 25% trên các tác vụ mục tiêu hoặc chặn được lỗi đáng kể mà baseline bỏ lọt; tổng chi phí phù hợp mức khách hàng định trả. Đây là mục tiêu đề xuất, chưa phải kết quả đạt được.

Đáng cắt nhất là chi phí hiểu và bảo trì hệ thống quản lý thử nghiệm. Đáng đầu tư nhất là một đường hoàn chỉnh từ yêu cầu đến bản sửa có bằng chứng, vận hành được và được khách hàng dùng lại.

**Bổ sung theo yêu cầu tiếp tục: workflow, tốc độ, độ tin cậy và Dream**

Phần này kế thừa toàn bộ kết quả đã xác minh ở trên. Không chạy lại probe hay benchmark. Chỉ lần tiếp các nhánh workflow chưa được phân tích đủ. Những phát hiện từ đọc code được ghi rõ, không gộp thành lỗi đã tái hiện.

**Bản đồ workflow thực tế**

Các nút/mode trên UI không tương ứng một-một với một pipeline thống nhất. Có bốn task route chính (analysis, clarification, defect repair, explicit change), nhiều web mode legacy (retrieve, deep, control, full), và một số workflow artifact/queue độc lập.

| Workflow | Trình tự thực tế | Đầu ra, thời gian chờ và giới hạn |
|---|---|---|
| Goal Brief | Người dùng nhập mục tiêu → chuẩn hóa schema → gợi ý phần thiếu → người dùng bổ sung bằng chứng → final prompt/assignment. Có interviewer tùy caller; autocomplete riêng là deterministic. | Thu thập yêu cầu, không tự chạy command lấy bằng chứng. Thời gian của người dùng có thể lớn hơn thời gian máy. Chỉ nên dùng khi phần thiếu làm thay đổi quyết định. |
| Full: analysis/clarification | Derive task shape và route → đọc bằng chứng giới hạn → Gemini draft → bỏ review/patch loop → ground tên/path trong câu trả lời → lưu kết quả. | Hợp lý cho hỏi đáp có giới hạn. Tối đa 12 file, 6.000 ký tự/file, 60.000 ký tự tổng, dùng chung nếu so hai repo. Không phải đã đọc trọn codebase. |
| Full: sửa lỗi | Inventory/index/graph → preflight → CONTROL localization và bằng chứng lỗi → Scout nếu cần → candidate từ Gemini → gate/verification theo nhánh → tự áp dụng nếu có quyền hoặc chờ người → validation/rollback → receipts. | Nhiều stage nối tiếp; candidate bị từ chối hoặc thiếu evidence có thể là kết quả đúng nhưng không phải tác vụ đã giải quyết. Retry còn lỗ hổng đã tái hiện. |
| Full: thay đổi theo yêu cầu | Route explicit change → lấy source → tạo candidate/patch plan → kiểm tra phạm vi và safety → sandbox/evidence/eligibility thích hợp → human review gắn candidate → áp dụng và validate. | Không cần giả vờ tìm thấy defect để làm yêu cầu hợp lệ. Khả năng nhiều file còn phụ thuộc patch style; safe_minimal không cho tạo file hay thay đổi nhiều file. |
| Direct file/tutor | Đọc/phân tích file → xây prompt dạy/giải thích hoặc patch → model → review/refine tùy mode/complexity → hiển thị, và có thể chuyển sang đường patch. | File đầu vào có thể được upload qua Gemini File API. Cần phân biệt truyền file với chỉ đọc local, không coi tutor là local-only. |
| Web retrieve | Retrieve context → route quyết định lấy analysis evidence hay deep/control → Gemini giải thích. | Đường chat nhẹ hơn full patch nhưng vẫn có retrieval và có thể mạng/embedding tùy cấu hình. Không thể lấy latency của full làm latency mọi câu hỏi. |
| Web deep/control | deep phân tích graph; control lấy structured CONTROL và phần giải thích. | Công cụ xem cấu trúc/localization, không bảo đảm ra bản sửa. Các chế độ legacy làm người dùng khó biết thực tế đã làm đến đâu. |
| CLI planner | Sinh subtasks → thực hiện từng subtask → action edit có candidate gọi Executor trực tiếp → ghi result → replan tối đa một lần khi lỗi. | Web nhận tên planner nhưng không gọi cùng run_planner_pipeline. Nhánh CLI gọi Executor trước maybe_run_auto_patch; đọc code chưa thấy nó đi qua gate cấp quyền của luồng chính. Cần hợp nhất trước khi cam kết mọi mode cùng mức an toàn. |
| Manual Test/Apply | Lấy candidate/session → kiểm tra candidate và phạm vi → test/apply theo route → validate/rollback → lưu diff/result. | Chất lượng validation vẫn quyết định độ tin cậy; một nút Apply không thay thế evidence. Dream Apply là đường riêng, có cả commit Git. |
| Dream | Snapshot queue → xử lý tuần tự theo global dream_mode → lưu artifact từng item → refinement → morning report → người chọn Apply/lesson. | Batch chuẩn bị công việc; mặc định plan_only. Chi tiết rủi ro và năng lực ở dưới. |
| Memory/lessons | Kết quả hoặc worker proposal → kiểm tra chất lượng/provenance → candidate/active tùy phê duyệt → retrieval lesson liên quan nếu bật. | Trí nhớ vận hành hữu ích nếu lesson đúng và người review thấy ít lỗi lặp lại. Chưa có đo lường để quy thành năng lực tự học tăng đều. |
| Worker handoff/MCP | Tạo assignment/handoff → người hoặc script riêng chạy worker → nhập output như proposal chưa tin cậy → validation/review → promote theo quyền. | MCP read-only đọc artifact; artifact-write cho một allowlist hẹp, gồm tạo handoff, import worker proposal, validate trong clone. Không phải API cho mọi mutation. |
| Project Evolution | Inventory/map → migration plan → approval → draft/candidate/text package → executable-draft/review contracts. | Phần lớn là chuỗi hồ sơ cần người điều phối. Đặc biệt builder mang tên sandbox_validation hiện trả apply not-applicable/validation not-run vì text draft không có executable diff. Không nên tính tên module này như bằng chứng đã chạy thử migration. |
| Benchmarks/replay/health | Chạy fixture qua production hoặc đọc artifact/toolchain → thống kê/so sánh/truy vết. | Công cụ hỗ trợ vận hành; giá trị gián tiếp, không cần chiếm ngang workflow giải quyết việc. |

Nguồn chính: [live_task_routing.py:1](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/live_task_routing.py:1), [analysis_evidence.py:106](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/analysis_evidence.py:106), [web/app.py:378](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:378), [run_planner_pipeline](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/pipeline.py:569), [main.py:94](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/main.py:94), [Project Evolution chưa chạy validation](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/project_evolution_sandbox_validation.py:462), [MCP artifact-write allowlist](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/mcp_server/artifact_write.py:36).

Nhận xét kiến trúc quan trọng: có nhiều workflow chia sẻ tên và một số primitive, nhưng chưa chia sẻ trọn bộ invariant. Bằng chứng kiểm chứng tốt của một nhánh không tự áp dụng được cho Dream, planner hay mọi đường Apply.

**Một sản phẩm là harness có đáng không?**

Có. Harness có thể là sản phẩm chính: nó chọn đúng context, giới hạn quyền, chạy tool, đo kết quả, lưu trạng thái và giúp xử lý lỗi. Người mua trả cho hiệu quả của chuỗi đó, không đòi nhà cung cấp tự huấn luyện model.

Nhưng cần vượt một baseline đơn giản: cùng model, cùng ngân sách, cùng tác vụ, một agent cộng Git/test thông thường. Nếu thêm C.A.T.T.U.S làm việc chậm hơn và buộc người dùng đọc thêm nhiều hồ sơ mà không giảm lỗi hay công review, nó không tạo đủ giá trị.

Một cách định nghĩa giá trị thực tế:

Giá trị ròng = thời gian lao động tránh được + tổn thất giảm được nhờ chặn sai sót − thời gian setup/chờ phải giám sát/review/làm lại − phí chạy và phí sản phẩm.

Không coi toàn bộ thời gian máy chạy qua đêm là thời gian con người tiết kiệm. Người dùng có thể làm việc khác khi job chạy; ngược lại, một job thất bại dù chạy nhanh vẫn tốn thời gian đổi ngữ cảnh và sửa lại.

Với C.A.T.T.U.S, lớp kiểm chứng có tiềm năng được bán như CLI/service nhỏ hoặc tích hợp CI/agent hiện có. Dashboard, memory research và governance nên là tùy chọn. Đây là định vị hợp lý hơn việc yêu cầu người dùng chuyển toàn bộ workflow sang một hệ điều hành agent mới.

**Khách black-box có đủ kiên nhẫn chờ không?**

Hiện chưa đủ bằng chứng để hứa “nhanh”. Không có latency p50/p95 từ tác vụ thực đủ đại diện; các số đo benchmark lịch sử nhỏ không thể dùng làm SLA.

Đọc code cho thấy các yếu tố làm chờ lâu:

- POST chính chạy _run_mode đồng bộ rồi mới render kết quả; chưa thấy token streaming ở luồng đó. Snapshot polling là một cơ chế riêng, mặc định tắt, không tương đương phản hồi nội dung tức thời.
- Full patch có index/graph, preflight, model, kiểm chứng, có thể reviewer/refinement/retry; fallback model có thể thử nối tiếp.
- Web no-change indexing vẫn phải dựng graph mới như đã nêu ở phần trước.
- Client Gemini không truyền timeout/deadline cấu hình riêng ở chỗ gọi; điều này không khẳng định SDK không có timeout mặc định, nhưng budget toàn run chưa được truyền xuyên suốt.
- Có đoạn reset started_at trước kiểm tra budget, và timeout validation không dừng chắc cả process tree. Không thể suy ra budget 180 giây là cam kết hoàn tất trong 180 giây.

[Nguồn request đồng bộ](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:514), [polling mặc định](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:116), [Gemini generation](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/agents/gemini_client.py:98), [budget/reset](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/pipeline.py:2401). Probe process con sống sau timeout đã có trong kết quả xác minh trước, không chạy lại.

Nếu tôi là người mua, các ngưỡng chấp nhận đề xuất là: UI xác nhận tác vụ trong khoảng 1 giây; câu hỏi hẹp có câu trả lời hữu ích khoảng 10–30 giây trên repo đã sẵn sàng; bản sửa nhỏ với test ngắn khoảng 1–3 phút; việc dài chuyển thành job nền với tiến độ đúng và quyền dừng. Đây là yêu cầu sản phẩm của người mua giả định, không phải số đo hiện tại và không áp cho suite vốn chạy hàng chục phút.

Tôi sẵn lòng chờ 5 phút nếu thực sự nhận được bản sửa tốt và chỉ cần review 2 phút. Tôi không muốn chờ 1 phút để rồi phải dành 20 phút tìm xem agent đã sửa đúng hay chưa.

**Developer có thể tin để giao cả codebase không?**

Phải tách ba mức tin cậy:

- Cho đọc để hỗ trợ định hướng: có thể thử trên repository được phép gửi tới provider đã chọn, luôn xem coverage/source nó thực đọc.
- Cho đề xuất diff trên checkout/worktree riêng, có test và người review: phù hợp nhất với hiện trạng sau khi xử lý lỗi ghi/backup đã biết.
- Cho tự sửa, tự chấp nhận và tự commit mọi loại thay đổi trên codebase quan trọng: tôi chưa tin ở trạng thái hiện tại.

12 file bằng chứng ở analysis không đủ cho lời hứa review toàn diện một monorepo; bounded retrieval là một lựa chọn tốc độ hợp lý nếu câu trả lời công khai khoảng trống. Graph symbol/call không bảo đảm hiểu mọi hành vi động. Passed tests chỉ bao phủ những hành vi đã kiểm, không chứng minh tất cả requirement và security.

Độ tin cậy cần tăng bằng một primitive cấp quyền/ghi chung cho mọi workflow, coverage hiển thị được, kiểm chứng hai chiều pre/post, rollback theo byte, môi trường cách ly và đánh giá trên tác vụ thực chưa thấy. Tăng số guardrail test hay dòng contract mà bỏ qua các đường thực thi khác không giải quyết khoảng cách này.

**Doanh nghiệp: không train chưa có nghĩa an toàn**

Không phải mọi API đều dùng dữ liệu để train. Theo điều khoản Gemini hiện hành, cách xử lý dữ liệu khác giữa Unpaid và Paid Services, có ngoại lệ theo khu vực. Paid Services không dùng prompt/response để cải thiện sản phẩm, nhưng có thể giữ log giới hạn cho chống lạm dụng; điều kiện zero-retention và dữ liệu upload cần xem riêng. [Điều khoản Gemini](https://ai.google.dev/gemini-api/terms), [Gemini ZDR](https://ai.google.dev/gemini-api/docs/zdr).

Không có cơ sở hứa an toàn tuyệt đối. Ngay cả model chạy local, phần mềm vẫn có thể làm sai quyền, mất dữ liệu, lộ log hoặc chạy test có side effect. Doanh nghiệp cần mô hình đe dọa, quyền hạn và mức bảo đảm kiểm chứng được.

| Yêu cầu doanh nghiệp | Đánh giá hiện trạng |
|---|---|
| Quyết định dữ liệu nào được rời máy | Primary draft gọi Google; critic Ollama có fallback Google. Chưa thấy policy local-only bắt buộc xuyên mọi workflow. |
| Ngăn người không có quyền đọc dữ liệu | Mutation token không bảo vệ GET history như probe đã xác minh; chưa đủ cho server chung. |
| Cách ly mã và test của repository | Temp clone không cách ly host; một số đường dùng runner host. Backend Docker riêng không tự bảo vệ mọi route. |
| Hủy job và đóng mọi side effect | Timeout process cha chưa dừng chắc process con; Dream chỉ stop giữa item. |
| Retention và phạm vi lưu dữ liệu | Replay/session có prompt, raw response, diff; cần policy retention/delete/ACL phù hợp. Dữ liệu lưu local không tự mang tính bí mật. |
| Khả năng truy vết và giới hạn scope | Đây là điểm có nền tảng tốt: receipt, fingerprint, diff, đường dẫn và source evidence. Cần thống nhất giữa các route. |
| Vận hành nhiều người và nhiều job | JSON session và daemon state không đủ làm nền tin cậy cho team service. |
| Chuỗi cung ứng và bản cài | Cần khóa dependency, release tái lập, cập nhật và core CI sạch trước khi hứa vận hành doanh nghiệp. |

[Fallback critic ra Google](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/agents/deepseek_client.py:57), [upload file](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/agents/gemini_client.py:85), [các loại replay artifact](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/replay_recorder.py:17).

Gói doanh nghiệp không chỉ là thêm auth và bật Docker. Trước mắt nên bán/định vị công cụ local cho một operator, trên repository tin cậy, với provider policy minh bạch. Sau đó mới thêm service profile với per-user/per-repo authorization, sandbox bắt buộc, network allowlist, secret injection tối thiểu, retention và durable jobs.

**Dream làm night-shift có đáng không?**

Luồng mặc định:

Queue có title/hint → plan_only tạo kế hoạch → refinement mặc định một vòng nếu còn budget → lưu morning report → người đọc và quyết định làm gì tiếp.

Điểm mới đáng quan tâm: _generate_plan_analysis dùng query từ kind/title/hint; truyền repo_path vào client không làm client tự đọc repository. Nếu file_paths rỗng và prompt không chứa code, bước này không nhận source code của repository. Vì vậy, chất lượng kế hoạch mặc định phụ thuộc rất mạnh vào context người dùng đã đưa vào hint. [Nguồn query](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:182), [planner](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:254), [client xử lý file_paths](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/agents/gemini_client.py:145).

| Dream mode | Công việc thực | Đánh giá khách hàng |
|---|---|---|
| plan_only mặc định | Lập kế hoạch từ đầu vào, có thể refine; không patch. | Có ích khi đầu vào đã đủ thông tin. Với “xem repo rồi tự tìm việc đáng làm”, hiện dễ tạo thêm kế hoạch phải đọc. |
| research | Kế hoạch rồi proposal; không tự chứng minh đã tìm kiếm web hay đọc code. | Có ích cho tổng hợp ý tưởng từ context đã cung cấp; không nên gọi là nghiên cứu có nguồn chỉ vì tên mode. |
| case_idea_research | Đọc reference notes được cung cấp → gợi ý benchmark case/lesson note. | Đầu ra ứng viên để người review; chưa tự tạo benchmark hoàn chỉnh. |
| patch_if_safe | Planner cho phép thử → CONTROL + Scout → model tạo patch → copy repo → apply và validation nhẹ → candidate/artifact → có thể retry/revalidate. | Có giá trị trên bug nhỏ, rõ ràng, kiểm được. Hiện chưa dùng cùng candidate_verification mới như ban ngày. |
| Morning Apply | Người chọn item ready → đọc plan → path safety → apply trên repo thật và validate lại → git add các file liên quan → git commit. | Đây là hành động có mutation và commit; cần review rõ và kiểm tra trạng thái Git. Không phải chỉ mở một preview. |

Một lần gọi planner/Scout/patch là một lần gọi nghiệp vụ; client có thể thử model fallback bên trong. plan_only thường có một gọi ban đầu và một refinement mặc định; research có thể hai gọi ban đầu rồi refinement; patch_if_safe thêm planner, Scout và patch, rồi lặp Scout/patch nếu retry. Đây là đường gọi suy từ code, không phải số đo latency hoặc hóa đơn chạy đêm.

Các điểm làm tôi chưa giao việc qua đêm trên code quan trọng:

1. **Oracle nhẹ:** Rust cargo check, Go go build, Python compileall, các trường hợp khác có thể không có command. Một patch đúng cú pháp nhưng sai hành vi vẫn có thể đi đến ready_to_apply. [sleeping_consultant.py:171](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:171), [gán trạng thái ready](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:696).
2. **Mâu thuẫn ở patch prompt:** nhánh Dream yêu cầu patch_plan trong khi CONTROL ở nhánh đó mặc định safe_minimal có thể cấm patch_plan; code tự ghi nhận giới hạn này. Kết quả hợp lệ có thể chỉ dừng ở planned_no_patch. [ghi chú tại _run_patch_item](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:594).
3. **Chưa phải job bền vững:** web khởi chạy daemon thread trong Flask, state trong memory; chết/reload process thì run chết. Có artifact từng item nhưng list/report tổng được ghi cuối; chưa có resume từ checkpoint và cơ chế consume queue bền vững. [start_overnight_async](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:1535).
4. **Budget mềm:** 6 giờ mặc định là kiểm tra giữa các item; Stop cho item đang chạy hoàn tất, không hủy model call ngay. [request_stop](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:97), [budget](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:1330).
5. **Trạng thái hoàn tất chưa đủ tin cậy:** planning có thể ghi planned_no_patch dù JSON parse thất bại; research có thể ghi research_note_created cho chuỗi AGENT_ERROR không rỗng. Cần model result kiểu success/error và tiêu chí “có đầu ra hữu ích”. [plan_only](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:754), [research](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py:783).
6. **Workflow scope chưa đồng nhất:** queue có action_level theo item, còn runtime quyết định theo global dream_mode và kind. Nhãn plan_only của item chưa chắc hạn chế được việc thử patch trong sandbox. Các vòng refinement sau còn đọc lại bản gốc thay vì luôn dùng bản refine trước. Đây là phát hiện từ code, chưa đo tần suất tác động.
7. **Morning Apply có commit:** route dùng git add file đã chạm rồi git commit. Cần worktree/branch riêng và bảo vệ staged changes đã có; chỉ giới hạn git add không bảo đảm một git commit không chứa các file vốn staged từ trước. [Dream Apply](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/app.py:1057).

Dream không cần một người ngồi nhìn suốt đêm để có giá trị. Mô hình hợp lý là người chuẩn bị backlog đủ rõ vào cuối ngày, job xử lý độc lập trong môi trường cách ly, sáng review những candidate đã kiểm chứng tốt. Những tác vụ đang mơ hồ, cần quyết định kiến trúc/sản phẩm hoặc liên tục thiếu context thường hiệu quả hơn khi có người cùng làm.

Ví dụ về cách đánh giá, không phải số liệu đo: 30 phút chuẩn bị + 20 phút review sáng hôm sau để nhận ba bản sửa hữu ích có thể đáng hơn hai giờ làm tay. Chạy sáu giờ sinh 40 trang kế hoạch rồi mất hai giờ đọc mà chưa sửa được gì thì không đáng.

Chỉ số Dream nên là số tác vụ được chấp nhận trên mỗi phút công sức con người và mỗi USD, cộng tỷ lệ run phục hồi được sau sự cố. Không nên là số item chạy, số trang báo cáo hay số giờ máy hoạt động.

Để đáng dùng thật, Dream cần trước tiên: lấy evidence repository cho planning, kiểm chứng như luồng ban ngày, state/job bền vững, resume/de-duplicate, ngân sách USD và deadline cứng, trạng thái error trung thực, morning digest ngắn xếp theo giá trị cùng diff/test/bằng chứng. Chưa cần tăng vòng tự phản biện.

**Với tư cách người sử dụng và người cộng tác kỹ thuật, tôi có cần nó không?**

Tôi không cần toàn bộ C.A.T.T.U.S hiện tại cho đa số việc lập trình. Nhiều phần quản trị khiến phải học và bảo trì thêm mà lợi ích chưa được đo.

Tôi muốn giữ bộ phận trả lời được: bản sửa nào được phép chạy, dựa vào bằng chứng nào, giữ nguyên hành vi nào, đã chạy kiểm tra gì và có thể phục hồi ra sao. Nếu phần đó chạy độc lập, tích hợp dễ với công cụ đang dùng và chứng minh giảm lỗi/công review, tôi thấy nó cần thiết cho một số nhóm.

Tôi sẽ chưa dùng Dream hiện tại như một nhân viên ca đêm tự chủ. Tôi có thể dùng nó như trợ lý chuẩn bị có giám sát, với backlog nhỏ và repo thử nghiệm. Từ góc độ sản phẩm, chọn ít workflow nhưng dùng chung nền thực thi đáng tin cậy sẽ có giá trị hơn tiếp tục mở rộng danh sách mode.

**Kết quả kiểm tra đã hoàn thành, không chạy lại**

- 97 test benchmark/minimality/artifact-ledger/validation safety: pass.
- Hai test production branch candidate verification (candidate sai bị chặn, candidate đúng được verify mà không có quyền ghi): pass.
- Hai test governance được chọn: fail; một phụ thuộc hồ sơ lịch sử, một kỳ vọng phase tiếp theo đã cũ.
- Benchmark --check: 54 case, 0 lỗi cấu trúc; không phải 54 lần sửa lỗi thành công.
- Bốn probe runtime: xác minh CRLF bị đổi, backup có trước bị mất, retry đổi scope/basis vẫn chạy, process con còn sống sau timeout.
- Hai probe web/session với dữ liệu giả: GET không xác thực đọc được history, và lost update khi hai thao tác xen kẽ.
- Một batch safety bổ sung đang chạy khi cuộc hội thoại chuyển tiếp; không lấy được terminal completion, nên không tính vào số pass và không chạy lại theo yêu cầu.

[Probe runtime](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/.tmp/runtime_review_repro_output.json), [mã tái hiện runtime](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/.tmp/runtime_review_repro.py), [probe web/session](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/.tmp/customer-review-web-repro-20260909.json), [mã tái hiện web/session](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/.tmp/customer-review-web-repro-20260909.py).

Các file source trong workspace có thể tiếp tục được cập nhật bởi công việc khác trong thời gian audit; tham chiếu dòng tương ứng thời điểm đọc. Các kết luận động ở trên có output tái hiện lưu riêng. Báo cáo này không thay thế acceptance run trên một revision đã đóng băng.
