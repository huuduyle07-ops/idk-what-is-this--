/* File labels are reviewed metadata, separate from extracted text and concepts. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const make = (tag, value, className) => { const item = document.createElement(tag); if (value != null) item.textContent = value; if (className) item.className = className; return item; };
    const emptyLabels = () => ({ subject: "", topics: [], role: "unknown", language: "unknown" });
    const same = (a, b) => a.subject === b.subject && a.role === b.role && a.language === b.language && JSON.stringify(a.topics) === JSON.stringify(b.topics);
    function create({ api, onChange, onRecords, notice }) {
        let collection = null, source = null, records = new Map(), model = null, current = null;
        let sequence = 0, loading = false, busy = false, externalBlocked = false, uncertain = false, latest = null;
        const fields = ["fileLabelSubject", "fileLabelTopics", "fileLabelRole", "fileLabelLanguage"];
        function formLabels() { return { subject: byId(fields[0]).value.trim(), topics: byId(fields[1]).value.split(/[\n,]/).map((value) => value.trim()).filter(Boolean), role: byId(fields[2]).value, language: byId(fields[3]).value }; }
        function fill(labels) { byId(fields[0]).value = labels.subject || ""; byId(fields[1]).value = (labels.topics || []).join("\n"); byId(fields[2]).value = labels.role || "unknown"; byId(fields[3]).value = labels.language || "unknown"; }
        function dirty() { return !!current && !same(formLabels(), current.labels); }
        function status(message) { byId("fileLabelsStatus").textContent = message; }
        function address() { return "/learn/api/materials/" + encodeURIComponent(collection.id) + "/sources/" + encodeURIComponent(source.source_id.replace(/^sha256:/, "")) + "/labels"; }
        function checked(value) {
            if (!value || value.source_id !== source?.source_id || !Number.isInteger(value.revision) || !value.labels || typeof value.labels.subject !== "string" || !Array.isArray(value.labels.topics)) { const error = new Error("Phản hồi nhãn chưa hợp lệ."); error.ambiguous = true; throw error; }
            return value;
        }
        function controls() {
            const locked = externalBlocked || busy || loading || !current;
            fields.forEach((id) => { byId(id).disabled = locked; });
            byId("confirmFileLabels").disabled = locked || uncertain || !!latest || (!dirty() && current?.status === "confirmed" && !current?.suggestion);
            byId("suggestFileLabels").disabled = locked || uncertain || !!latest || dirty() || !model?.available;
            byId("reloadFileLabels").disabled = externalBlocked || busy || loading || !collection;
            byId("discardFileLabels").disabled = externalBlocked || busy || loading || (!dirty() && !uncertain && !latest);
            byId("useFileLabelSuggestion").disabled = locked || uncertain || !!latest || dirty() || !current?.suggestion || !!current.suggestion_stale;
            byId("useSavedFileLabels").disabled = locked || !latest;
            byId("keepDraftFileLabels").disabled = locked || !latest;
            byId("fileLabelsForm").setAttribute("aria-busy", String(busy));
            byId("fileLabelsBadge").textContent = dirty() ? "Draft · chưa lưu" : current?.status === "confirmed" ? "Confirmed · bạn đã xác nhận" : "Unclassified";
        }
        function renderSuggestion() {
            const suggestion = current?.suggestion;
            byId("fileLabelSuggestion").hidden = !suggestion;
            byId("fileLabelEvidence").replaceChildren();
            if (!suggestion) return;
            const labels = suggestion.labels || emptyLabels();
            byId("fileLabelSuggestedValues").textContent = "Subject: " + labels.subject + "\nTopics: " + (labels.topics || []).join(", ") + "\nRole: " + labels.role + "\nLanguage: " + labels.language;
            byId("fileLabelSuggestionInfo").textContent = (suggestion.provider || "") + " · " + (suggestion.model || "") + " · Sampled " + suggestion.sampled_units + " / " + suggestion.total_units + " units. Gợi ý chỉ dựa trên mẫu được gửi, chưa được xác nhận.";
            byId("fileLabelStale").hidden = !current.suggestion_stale;
            const names = { page: "Page", slide: "Slide", paragraph: "Paragraph", table: "Table", image: "Image" };
            for (const evidence of suggestion.evidence || []) {
                const card = make("details", null, "file-label-evidence");
                card.append(make("summary", evidence.field + " · " + (names[evidence.locator?.kind] || "Unit") + " " + (evidence.locator?.index || "")));
                card.append(make("p", evidence.origin === "user_note" ? "Your image note — not OCR or image recognition." : "Extracted text — review against the original.", "material-help"));
                card.append(make("blockquote", evidence.text)); byId("fileLabelEvidence").append(card);
            }
        }
        function renderConcepts() {
            byId("fileConceptSummary").replaceChildren();
            const concepts = current?.concepts || [];
            if (!concepts.length) byId("fileConceptSummary").append(make("span", "Chưa có khái niệm được gắn vào phần nguồn trong file này."));
            concepts.forEach((item) => byId("fileConceptSummary").append(make("span", item.label + " · " + item.unit_count + " units", "file-concept-chip")));
        }
        function adopt(record, keepDraft = false) {
            current = checked(record); records.set(current.source_id, current);
            if (!keepDraft) fill(current.labels);
            latest = null; uncertain = false; byId("fileLabelsConflict").hidden = true;
            renderSuggestion(); renderConcepts(); controls(); onRecords(records); onChange();
        }
        function renderSource() {
            current = source ? records.get(source.source_id) || null : null;
            fill(current?.labels || emptyLabels()); latest = null; uncertain = false;
            byId("fileLabelsConflict").hidden = true;
            renderSuggestion(); renderConcepts(); controls();
            status(current ? "Nhãn tổ chức file; không xác nhận nội dung học là đúng. Bạn có thể sửa rồi Confirm labels." : "Chưa đọc được nhãn file. Có thể tiếp tục xem tài liệu và thử Reload labels.");
        }
        async function load(preserveDraft = true) {
            if (!collection || busy || loading) return;
            const id = collection.id, currentSource = source?.source_id, request = ++sequence;
            const hadDraft = preserveDraft && (dirty() || uncertain || latest);
            loading = true; controls(); status("Đang đọc nhãn đã lưu…");
            try {
                const result = await api("/learn/api/materials/" + encodeURIComponent(id) + "/labels");
                if (request !== sequence || collection?.id !== id) return;
                if (!Array.isArray(result.files)) throw new Error("Nhãn chưa hợp lệ.");
                records = new Map(result.files.map((record) => [record.source_id, record])); model = result.model || null;
                byId("fileLabelModel").textContent = model?.available ? model.provider + " · " + model.model + ". " + (model.provider === "gemini" ? "Gemini gửi các đoạn mẫu tới dịch vụ cloud. " : model.provider === "ollama" ? "Ollama xử lý tại endpoint đã cấu hình (thường trên máy của bạn). " : "") + "Chỉ Suggest labels mới gửi mẫu tới model này." : (model?.reason || "Chưa có model gợi ý; vẫn có thể nhập và xác nhận nhãn bằng tay.");
                const record = records.get(source?.source_id);
                if (hadDraft && currentSource === source?.source_id && record) {
                    latest = checked(record); uncertain = false;
                    current.concepts = record.concepts; current.suggestion_stale = record.suggestion_stale;
                    renderConcepts(); renderSuggestion();
                    byId("fileLabelsConflict").hidden = false;
                    byId("fileLabelsSavedValues").textContent = JSON.stringify(latest.labels, null, 2);
                    status("Đã đọc bản mới. Bản đang viết được giữ; chọn dùng nhãn đã lưu hoặc tiếp tục sửa bản nháp dựa trên phiên bản mới.");
                } else { renderSource(); }
                onRecords(records);
            } catch (error) { if (request === sequence) status(error.message || "Chưa tải được nhãn. Nhấn Reload labels để thử lại; tài liệu vẫn xem được."); }
            finally { if (request === sequence) { loading = false; controls(); onChange(); } }
        }
        async function mutate(kind) {
            if (!current || busy || loading || externalBlocked || uncertain || latest) return;
            if (kind === "suggest" && (dirty() || !model?.available)) return;
            const selected = source.source_id, id = collection.id;
            const labels = formLabels(), revision = current.revision;
            busy = true; controls(); onChange(); status(kind === "suggest" ? "AI đang đọc mẫu và gợi ý nhãn… Có thể mất khoảng một phút. Nhãn đã xác nhận chưa thay đổi." : "Đang lưu nhãn bạn xác nhận…");
            try {
                const result = await api(address() + (kind === "suggest" ? "/suggest" : ""), {
                    method: kind === "suggest" ? "POST" : "PUT", headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(kind === "suggest" ? { expected_revision: revision } : { labels, expected_revision: revision }),
                });
                if (collection?.id !== id || source?.source_id !== selected) return;
                adopt(result.file);
                status(kind === "suggest" ? "Đã có Suggested labels. Mở các đoạn căn cứ, chọn Use suggestion để điền vào form, rồi Confirm labels khi bạn đồng ý." : "Đã lưu Confirmed labels. Nhãn file không tự tạo khái niệm hoặc xác nhận nội dung bài giảng.");
            } catch (error) {
                if (collection?.id !== id || source?.source_id !== selected) return;
                if (error.ambiguous || error.status === 409) uncertain = true;
                status((error.message || "Chưa thực hiện được thao tác.") + (uncertain ? " Chọn Reload labels để kiểm tra kết quả trước khi thao tác tiếp; không tự gọi lại model. Bản nháp vẫn được giữ." : " Bản nháp vẫn được giữ."));
            } finally { busy = false; controls(); onChange(); }
        }
        fields.forEach((id) => byId(id).addEventListener("input", () => { controls(); onChange(); }));
        byId("fileLabelsForm").addEventListener("submit", (event) => { event.preventDefault(); mutate("confirm"); });
        byId("suggestFileLabels").addEventListener("click", () => mutate("suggest"));
        byId("reloadFileLabels").addEventListener("click", () => load(true));
        byId("discardFileLabels").addEventListener("click", () => { if (busy || loading) return; if (uncertain || latest) load(false); else { fill(current?.labels || emptyLabels()); controls(); onChange(); status("Đã bỏ thay đổi nhãn chưa lưu."); } });
        byId("useSavedFileLabels").addEventListener("click", () => { if (latest) { adopt(latest); status("Đang dùng nhãn đã lưu. Không ghi thay đổi mới."); } });
        byId("keepDraftFileLabels").addEventListener("click", () => { if (latest) { adopt(latest, true); status("Đã giữ bản nháp theo phiên bản mới. Nhấn Confirm labels khi muốn lưu."); } });
        byId("useFileLabelSuggestion").addEventListener("click", () => {
            if (!current?.suggestion || current.suggestion_stale || busy || loading || externalBlocked || uncertain || latest || dirty()) return;
            fill(current.suggestion.labels); controls(); onChange(); status("Đã điền gợi ý vào bản nháp. Chưa lưu; hãy xem lại rồi Confirm labels.");
        });
        return {
            setSource(nextCollection, nextSource) {
                if (collection?.id === nextCollection?.id && source?.source_id === nextSource?.source_id) return;
                const changed = collection?.id !== nextCollection?.id;
                collection = nextCollection; source = nextSource;
                if (changed) { sequence += 1; loading = false; records = new Map(); model = null; byId("fileLabelModel").textContent = "Đang đọc cấu hình gợi ý…"; }
                renderSource(); if (changed) load(false);
            },
            setBlocked(value) { externalBlocked = !!value; controls(); },
            refresh: () => load(true),
            isDirty: () => dirty() || uncertain || !!latest,
            isBusy: () => busy,
            guard() {
                if (busy) { notice("Đang xử lý nhãn file. Hãy đợi thao tác hoàn tất."); return false; }
                if (dirty() || uncertain || latest) { notice("Nhãn file còn bản nháp hoặc kết quả chưa xác nhận. Hãy Confirm labels, Reload labels hoặc Bỏ thay đổi trước khi chuyển file."); byId("fileLabelsPanel").open = true; byId("fileLabelSubject").focus(); return false; }
                return true;
            },
            confirmedText(sourceId) { const record = records.get(sourceId); return record?.status === "confirmed" ? [record.labels.subject, ...(record.labels.topics || []), record.labels.role, record.labels.language].join(" ") : ""; },
        };
    }
    window.LearningFileLabels = Object.freeze({ create });
})();
