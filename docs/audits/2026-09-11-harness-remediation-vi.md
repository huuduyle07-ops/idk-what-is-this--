**C.A.T.T.U.S — khắc phục các phát hiện black-box, hoàn tất ngày 11/09/2026**

Đợt này tập trung sửa **10 hợp đồng chưa đạt trong audit ngày 10/09**, cùng các lỗi liên quan phát hiện khi review bản sửa. Bộ kiểm tra tích hợp chạy chung bốn workflow đạt **55/55 ca**, sau đó thêm **3/3 ca HTTP Apply nhiều file** đạt ở lần chạy riêng: tổng cộng **58 ca black-box đạt, không skip/xfail**, so với 18 pass / 10 fail trước đó. Cả 28 ca gốc đều đạt; có thêm 30 ca kiểm tra quyền, lỗi provider và trạng thái workflow.

Đây là tiến bộ về hành vi của harness, chưa phải bằng chứng model sửa đúng một codebase bất kỳ. Các phát hiện cũ của audit 09/09 không được mặc nhiên coi là đã khắc phục.

| Vấn đề đã tái hiện | Hành vi sau sửa | Bằng chứng chính |
|---|---|---|
| CLI planner ghi file dù tắt auto-patch | Kiểm tra cờ mutation và route ngay trước Executor; giữ candidate để xem, báo blocked và dừng bước phụ thuộc | Source giữ nguyên, không chạy bước kế tiếp; trường hợp bật auto-patch vẫn áp dụng và chạy test thành công |
| CLI crash khi tắt DB | Khởi tạo session local có chủ đích khi DB bị tắt | Gọi CLI thật, bỏ adapter giả tạo session; giữ hợp đồng API database để web tiếp tục cấp session riêng |
| Câu “Change app.py…” bị nhận thành không yêu cầu sửa | Nhận diện thêm các động từ sửa ở vị trí chỉ thị, gồm cách diễn đạt tiếng Việt; xét phủ định | HTTP đi vào vòng review → Apply; tập routing có cả câu hỏi, danh từ và yêu cầu phủ định |
| Apply báo “validation failed” khi bị chặn vì risk | Trả phase, validation outcome và nguyên nhân thực tế từ Executor | Phân biệt test fail, risk refusal và validation inconclusive trong response |
| F-string hợp lệ bị coi tiền tố `f` là identifier mới | Dùng AST của Python để lấy identifier; vẫn kiểm tra biểu thức bên trong f-string | Candidate f-string đúng được verify; không thêm whitelist riêng cho chữ `f` |
| Suite pytest đang fail không vào revision | Bỏ điều kiện phải timeout; vẫn cần đúng defect route, target và phép tái hiện độc lập | Suite đang fail thực sự đi tới một lần revision và verify; không cần tạo timeout giả |
| Targeted tests đỏ → xanh vẫn bị đánh inconclusive | Chỉ công nhận khi có lỗi tái hiện độc lập, cùng tập test cụ thể, không đổi test/config, baseline fail do assertion và candidate đều pass | Có ca dương và ca chống skip, bớt test, sửa oracle, lỗi runtime của baseline |
| Dream coi chuỗi lỗi provider là kế hoạch hoàn thành | Từ chối `AGENT_ERROR`, phản hồi rỗng/sai kiểu và plan thiếu dữ liệu bắt buộc | Báo error, giữ bằng chứng lỗi; mục tiếp theo trong queue vẫn được xử lý |
| Dream bỏ qua `plan_only` của item | Quyền hiệu lực bị giới hạn bởi cả run lẫn item; item không được nâng quyền run | Global patch mode không làm item plan/report chuyển sang sinh patch |
| Dream coi chuỗi `"false"` là cho phép patch | Giá trị safety phải là boolean; chỉ `True` mới mở nhánh | Chuỗi, số và kiểu sai không kích hoạt sinh patch |

Planner bị chặn nay cũng được lưu là `blocked`, thay vì kết thúc với trạng thái thành công. Lỗi ở một lần thử trước vẫn có thể được phục hồi bằng replan thành công; trạng thái cuối dựa trên bước khiến kế hoạch kết thúc. Đây là sửa tính trung thực của kết quả cho người dùng và cho hệ thống theo dõi run.

Các thay đổi chính nằm ở [CLI startup](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/cli/interactive.py), [planner và candidate lifecycle](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/pipeline.py), [run status](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/main.py), [routing](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/live_task_shape.py), [Apply response](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/web/routes/patch_routes.py), [identifier gate](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/patching/patch_gates.py), [defect probe](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/defect_probe.py), [targeted validation](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/targeted_repository_validation.py) và [Dream](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/core/sleeping_consultant.py). Working tree vốn có nhiều thay đổi của tác giả; toàn bộ diff Git không phải phạm vi công việc của đợt này.

**Bằng chứng chạy thử**

| Nhóm | Kết quả đã xác minh |
|---|---|
| Tích hợp chung CLI + HTTP + revision + Dream | 55 pass, 284,54 giây; lần lượt 7 + 13 + 8 + 27 ca |
| Đối chiếu lại 28 ca gốc | 28 pass; cả 10 ca từng fail đã đạt |
| Dream và các hợp đồng liên quan | 27 black-box pass; thêm 164 ca hồi quy pass |
| HTTP/routing và quyền thực thi | 107 ca pass; 66 ca quyền/telemetry pass; ba ca response cuối pass |
| Revision qua entrypoint | 8/8 pass; riêng suite fail thông thường đã pass trong 15,63 giây ở lần chạy riêng |
| HTTP Apply nhiều file bổ sung sau review | 3/3 pass, 11,45 giây: operation conflict, không có test, assertion fail; rollback đúng byte |
| Targeted validation và identifier novelty, mã cuối | 113 pass, 77,55 giây |
| Các contract cần cập nhật và phép tái tạo snapshot lịch sử | 10 pass, 2,61 giây; chạy riêng các ca liên quan |
| Tương thích authoring contract LIVE.2 của tác giả | 44 ca có bằng chứng pass qua hai lượt; chi tiết dưới đây |

Các nhóm trong bảng có giao nhau; không cộng chúng để quảng bá tổng số ca độc lập. Bằng chứng chi tiết và các lần chạy bổ sung sau review nằm trong [kết quả sau khắc phục](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-11-harness-remediation-results.json). [Kết quả trước sửa](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/docs/audits/2026-09-10-harness-blackbox-results.json) được giữ nguyên để đối chiếu.

Review độc lập còn phát hiện bộ selector không tăng vị trí khi bỏ qua đường dẫn sai/không tồn tại, có thể lặp vô hạn. Vị trí nay luôn được tăng trước khi xét bỏ qua; có test bằng subprocess với deadline. Bộ identifier AST cũng được bổ sung tên module của `from ... import ...` để không cho đổi module mà tránh được kiểm tra novelty. Đây là các kiểm tra bổ sung sau mốc tích hợp 55 ca, không phải lý do chạy lại năm timeout có chủ đích.

Một số test cũ khóa hash source theo từng phase nên cần cập nhật cách đối chiếu khi hành vi sản phẩm được sửa. Các fixture lịch sử được giữ nguyên; [receipt bảo trì](C:/Users/Admin/Documents/Code/J.A.R.V.I.S/districts/C.A.T.T.U.S/tests/fixtures/2026-09-10-harness-remediation-reversal.json) và helper chỉ dùng trong test đảo các thay đổi đã ghi nhận rồi kiểm tra lại hash lịch sử. Receipt phân biệt snapshot audit với snapshot có thay đổi đồng thời của LIVE.2. Đây là bảo trì bằng chứng có chủ đích, không có nghĩa mã runtime hiện tại vẫn giống byte với phase cũ.

Riêng LIVE.2, lượt đầy đủ đầu tiên có 42 pass và hai lỗi so hash lịch sử. Sau khi cập nhật rõ chuỗi đối chiếu, lượt chọn lọc gồm ba ca LIVE.2 và năm ca snapshot đều pass (8 ca, 4,35 giây); cả hai ca từng lỗi có trong lượt này. Không sửa code sản phẩm sau lượt 113 ca. Fixture LIVE.2 được giữ nguyên; các test ghi rõ không tái tạo snapshot trung gian có thay đổi đồng thời, mà đảo maintenance rồi ba hunk authoring để chứng minh lại mốc LIVE.1 và đối chiếu preimage audit. Vì thế, “44 ca đạt” là bằng chứng gộp qua hai lượt, không phải một lần chạy lại cả suite.

Provider được điều khiển ở SDK/adapter, còn routing, gate, filesystem, validation subprocess và entrypoint chạy thật trên các repository Python nhỏ. DB và embedding ngoài máy được tắt. Năm ca revision giữ timeout preflight thật 30 giây theo thiết kế ca gốc. **284,54 giây là thời gian bộ test**, không phải thời gian chờ của một khách hàng; 15,63 giây ở ca suite fail cũng không phải SLA vì provider giả trả lời ngay.

**Đánh giá sản phẩm thay đổi đến đâu**

Độ nhất quán đã tốt hơn: CLI tuân theo cờ tắt ghi; Dream tôn trọng quyền từng mục và không biến lỗi provider thành kết quả thành công; vòng coding có thể dùng suite đang fail làm điểm xuất phát. Đây là những cải thiện trực tiếp vào niềm tin của khách hàng black-box. Lõi đáng giữ vẫn là bằng chứng → candidate → kiểm chứng → review/Apply, với quyền ghi được kiểm soát riêng.

Tôi vẫn chưa có cơ sở để đổi sang khuyến nghị giao toàn bộ codebase quan trọng hoặc chạy night-shift tự chủ. Revision đang ở profile và họ bài toán hẹp: hook được thử trong chế độ tắt auto-patch, matrix xoay quanh `indentation_style`. Targeted checks xanh không chứng minh toàn repository xanh. Dream chưa được chứng minh có hàng đợi bền vững qua crash, phục hồi run và kiểm chứng hành vi đủ rộng. Đợt này cũng chưa đo model thật, chi phí hay p50/p95 trên công việc khách hàng.

Ưu tiên tiếp theo là **tính toàn vẹn file và quyền truy cập**: xử lý các phát hiện CRLF/backup, đường self-correction cũ và HTTP history đã ghi nhận trước đó; sau đó đến session concurrency và vòng đời process con. Chúng cần có ca hồi quy riêng khi sửa, không được đóng bằng kết quả 55 ca của đợt này. Tiếp theo mới xây benchmark model thật trên nhiều loại bug/codebase, rồi quyết định phạm vi night-shift và mức tiện ích đáng duy trì.

Không thể suy ra “an toàn tuyệt đối” từ các test này. Đợt sửa chưa bổ sung sandbox ở mức hệ điều hành, kiểm soát egress, cách ly secret hay chính sách dữ liệu doanh nghiệp. Về quyết định sử dụng, bản hiện tại tiến gần hơn đến một công cụ kiểm chứng có người giám sát; bằng chứng hiện có vẫn chưa đủ để coi nó là dịch vụ coding tự chủ có thể bán với cam kết chất lượng và thời gian.
