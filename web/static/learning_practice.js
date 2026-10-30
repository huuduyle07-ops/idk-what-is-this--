/* Source-scoped practice. Creating a set is the only model operation. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const text = (id, value) => { byId(id).textContent = value; };
    const show = (id, value) => { byId(id).hidden = !value; };
    const make = (tag, value, className) => { const el = document.createElement(tag); if (value != null) el.textContent = value; if (className) el.className = className; return el; };
    const API = "/learn/api/practice";
    const state = { model: null, collections: [], collection: null, practice: null, history: [],
        busy: false, sourceLoading: false, sourceRequest: 0, navigation: 0, selected: new Set(),
        pendingCreate: null, pendingAction: null, conflict: false, drafts: new Map(), orphanDrafts: new Map(), historyRequest: 0 };
    const address = () => API + "/" + encodeURIComponent(state.practice.id);
    const currentQuestion = () => state.practice?.questions?.[state.practice.current_index || 0];
    const key = (question = currentQuestion()) => state.practice?.id + ":" + question?.id;
    const draft = () => state.drafts.get(key()) || { option: "", reflection: "" };
    const hasDraft = () => !!(draft().option || draft().reflection.trim());
    const statusNames = { generating: "Đang tạo", draft: "Xem trước", active: "Đang thực hành", completed: "Đã hoàn thành", failed: "Chưa tạo được" };
    function notice(message) { text("practiceNoticeText", message); show("practiceNotice", !!message); controls(); }
    function citation(unit) { return ({ page: "Page", slide: "Slide", paragraph: "Paragraph", table: "Table", image: "Image" }[unit.locator?.kind] || "Unit") + " " + (unit.locator?.index || ""); }
    function button(label, action, className = "text-button") { const el = make("button", label, className); el.type = "button"; el.addEventListener("click", action); return el; }
    function guard() {
        if (state.busy) { notice("Đang xử lý yêu cầu. Hãy đợi kết quả."); return false; }
        if (state.pendingCreate || state.pendingAction || state.conflict) { notice("Kết quả yêu cầu trước chưa rõ. Kiểm tra đúng yêu cầu hoặc đọc bản đã lưu trước khi chuyển bộ."); return false; }
        if (hasDraft() || state.orphanDrafts.size) { notice("Bạn còn lựa chọn hoặc lời giải thích chưa gửi. Hãy gửi hoặc Bỏ bản nháp trước khi chuyển bộ."); return false; }
        return true;
    }
    function controls() {
        const locked = state.busy || !!state.pendingCreate || !!state.pendingAction || state.conflict;
        byId("practiceCollection").disabled = locked || state.sourceLoading || !state.collections.length;
        byId("practiceCount").disabled = locked;
        byId("generatePracticeButton").disabled = locked || state.sourceLoading || !state.model?.available || !state.collection || !state.selected.size || state.selected.size > 8;
        byId("practiceUnits").querySelectorAll("input").forEach((input) => { input.disabled = locked || state.sourceLoading || (!input.checked && state.selected.size >= 8); });
        byId("newPracticeButton").disabled = state.busy;
        byId("reloadPracticeHistory").disabled = state.busy;
        byId("practiceHistory").querySelectorAll("button").forEach((el) => { el.disabled = state.busy; });
        byId("deletePracticeButton").disabled = locked || state.practice?.status === "generating";
        byId("confirmPracticeDelete").disabled = locked;
        byId("cancelPracticeDelete").disabled = state.busy;
        byId("practiceContent").querySelectorAll("button,input,textarea").forEach((el) => { el.disabled = locked || el.dataset.disabled === "true"; });
        show("retryPracticeRequest", !!state.pendingCreate || (!!state.pendingAction && !state.conflict));
        byId("retryPracticeRequest").disabled = state.busy;
        show("reloadPracticeButton", !!state.practice);
        byId("reloadPracticeButton").disabled = state.busy;
        byId("practiceGenerateForm").setAttribute("aria-busy", String(state.busy && !!state.pendingCreate));
        byId("practiceSession").setAttribute("aria-busy", String(state.busy));
    }
    async function api(url, options, timeoutMs = 20000) {
        const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetch(url, Object.assign({ credentials: "same-origin", cache: "no-store", signal: controller.signal }, options));
            let data;
            try { data = await response.json(); } catch (_) { const error = new Error("Chưa đọc được xác nhận từ máy chủ."); error.ambiguous = true; throw error; }
            if (!response.ok || data.ok === false) { const error = new Error(data.error || "Chưa thực hiện được yêu cầu."); error.status = response.status; error.ambiguous = response.status >= 500; throw error; }
            return data;
        } catch (error) { if (!error.status) error.ambiguous = true; throw error; }
        finally { clearTimeout(timeout); }
    }
    function json(method, body) { return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }; }
    function checked(value) {
        if (!value || typeof value.id !== "string" || !Number.isInteger(value.revision) || !statusNames[value.status]) { const error = new Error("Phản hồi bộ thực hành chưa hợp lệ."); error.ambiguous = true; throw error; }
        return value;
    }
    function renderHistory() {
        byId("practiceHistory").replaceChildren(...state.history.map((item) => {
            const row = make("li"), open = button(item.title || "Practice", () => openPractice(item.id));
            open.dataset.practiceId = item.id; open.setAttribute("aria-current", String(state.practice?.id === item.id));
            open.append(make("small", (statusNames[item.status] || item.status) + " · " + (item.total_items || 0) + " questions")); row.append(open); return row;
        }));
        text("practiceHistoryStatus", state.history.length ? "Bộ câu hỏi được lưu với trình duyệt này." : "Chưa có bộ câu hỏi. Chọn nguồn để bắt đầu."); controls();
    }
    async function history() {
        const request = ++state.historyRequest;
        try { const result = await api(API); if (request !== state.historyRequest) return; state.history = result.practices || []; renderHistory(); }
        catch (_) { if (request === state.historyRequest) text("practiceHistoryStatus", "Chưa đọc được lịch sử. Chọn Đọc lại để thử tiếp."); }
    }
    function sourceText(unit) {
        const source = state.collection?.sources?.find((item) => item.source_id === unit.source_id);
        const note = source?.image ? source.description?.text || "" : null;
        return { text: String(note === null ? unit.text || "" : note).trimStart().slice(0, 1000), origin: note === null ? "extracted" : "user_note", name: source?.original_names?.join(" · ") || unit.source_id };
    }
    function renderUnits() {
        byId("practiceUnits").replaceChildren();
        const units = state.collection?.units || [];
        let readable = 0;
        units.forEach((unit) => {
            const source = sourceText(unit);
            if (!source.text.trim()) return;
            readable += 1;
            const card = make("div", null, "practice-unit"), label = make("label"), input = document.createElement("input");
            input.type = "checkbox"; input.value = unit.unit_id; input.checked = state.selected.has(unit.unit_id);
            input.addEventListener("change", () => { if (input.checked) state.selected.add(unit.unit_id); else state.selected.delete(unit.unit_id); updateUnitCount(readable); controls(); });
            label.append(input, make("span", source.name + " · " + citation(unit)));
            const details = make("details"); details.append(make("summary", "Xem đoạn sẽ gửi · " + (source.origin === "user_note" ? "ghi chú của bạn" : "chữ trích xuất")), make("pre", source.text));
            card.append(label, details); byId("practiceUnits").append(card);
        });
        updateUnitCount(readable); controls();
    }
    function updateUnitCount(readable) { text("practiceUnitStatus", readable ? state.selected.size + " / 8 phần đã chọn · " + readable + " phần có chữ. Chọn các đoạn đủ để trả lời câu hỏi." : "Chưa có chữ dùng được trong bộ này. Hãy thêm ghi chú ảnh hoặc chọn bộ khác."); }
    async function selectCollection(id, targetUnit) {
        const request = ++state.sourceRequest;
        state.sourceLoading = true; state.collection = null; state.selected.clear(); byId("practiceUnits").replaceChildren(); controls();
        if (!id) { state.sourceLoading = false; text("practiceUnitStatus", "Chưa chọn bộ bài giảng."); controls(); return; }
        text("practiceUnitStatus", "Đang đọc các phần nguồn…");
        try {
            const result = await api("/learn/api/materials/" + encodeURIComponent(id));
            if (request !== state.sourceRequest) return;
            state.collection = result.collection;
            if (targetUnit && state.collection.units?.some((unit) => unit.unit_id === targetUnit && sourceText(unit).text.trim())) state.selected.add(targetUnit);
            else if (targetUnit) notice("Phần nguồn trong liên kết không có chữ dùng được. Hãy chọn phần khác.");
            renderUnits();
        } catch (error) { if (request === state.sourceRequest) text("practiceUnitStatus", error.message); }
        finally { if (request === state.sourceRequest) { state.sourceLoading = false; controls(); } }
    }
    function renderAnswer(question) {
        const answer = question.answer;
        if (!answer) return null;
        const box = make("section", null, "practice-answer"); box.dataset.itemId = question.id;
        box.append(make("h4", "Model answer · cần đối chiếu"));
        const chosen = question.options?.find((option) => option.id === answer.correct_option);
        box.append(make("p", (chosen ? chosen.id + ". " + chosen.text : answer.correct_option) || ""), make("p", answer.explanation || ""));
        for (const source of answer.evidence || []) {
            const details = make("details", null, "practice-answer-source");
            details.append(make("summary", (source.source_name || "Source") + " · " + citation(source)), make("p", source.origin === "user_note" ? "Your saved image note — not OCR or verified image interpretation." : "Pinned extracted excerpt — compare with the original.", "practice-help"), make("blockquote", source.text || ""));
            if (state.practice.scope?.collection_id && source.unit_id) {
                const link = make("a", "Mở phần nguồn trong tab mới ↗");
                link.href = "/learn/materials?collection=" + encodeURIComponent(state.practice.scope.collection_id) + "&unit=" + encodeURIComponent(source.unit_id); link.target = "_blank"; link.rel = "noopener"; details.append(link);
            }
            box.append(details);
        }
        return box;
    }
    function questionHeading(question, index) {
        const box = make("section", null, "practice-question"); box.dataset.itemId = question.id;
        box.append(make("p", "Question " + (index + 1) + " · " + (question.objective || ""), "practice-objective"));
        const title = make("h3", question.question); title.tabIndex = -1; box.append(title); return box;
    }
    function renderDraft() {
        const content = byId("practiceContent");
        content.append(make("p", "Xem câu hỏi trước khi bắt đầu. Review answer sẽ mở đáp án và nguồn, đồng thời ghi nhận bạn đã xem đáp án trước khi làm.", "practice-help"));
        (state.practice.questions || []).forEach((question, index) => {
            const box = questionHeading(question, index), options = make("ul", null, "practice-options");
            (question.options || []).forEach((option) => options.append(make("li", option.id + ". " + option.text)));
            box.append(options);
            const answer = renderAnswer(question);
            if (answer) box.append(answer, make("p", "Đã xem đáp án trước khi bắt đầu; lượt làm sẽ ghi nhận hỗ trợ này.", "practice-help"));
            else box.append(button("Review answer & source", () => act("review_answer", { item_id: question.id })));
            content.append(box);
        });
        const actions = make("div", null, "practice-actions"); actions.append(button("Start practice", () => act("start", {}), "button button-primary")); content.append(actions);
    }
    function saveDraft() {
        const form = byId("practiceAnswerForm"); if (!form) return;
        state.drafts.set(key(), { option: form.querySelector("input:checked")?.value || "", reflection: byId("practiceReflection").value });
        const submit = byId("submitPracticeAnswer"); submit.dataset.disabled = String(!draft().option); controls();
    }
    function renderActive() {
        const question = currentQuestion(); if (!question) return;
        const content = byId("practiceContent"), box = questionHeading(question, state.practice.current_index || 0), saved = draft();
        content.append(make("p", "Question " + ((state.practice.current_index || 0) + 1) + " / " + state.practice.total_items + " · " + question.hint_count + " hints used" + (question.answer_reviewed ? " · answer reviewed before start" : ""), "practice-progress"));
        const form = make("form", null, "practice-answer-form"); form.id = "practiceAnswerForm";
        const fieldset = make("fieldset"); fieldset.append(make("legend", "Choose an answer, then explain your reasoning if you wish."));
        const options = make("div", null, "practice-options");
        (question.options || []).forEach((option) => {
            const label = make("label", null, "practice-option"), radio = document.createElement("input"); radio.type = "radio"; radio.name = "practice-option"; radio.value = option.id; radio.checked = saved.option === option.id;
            radio.addEventListener("change", saveDraft); label.append(radio, make("span", option.id + ". " + option.text)); options.append(label);
        });
        fieldset.append(options); form.append(fieldset);
        const reflectionLabel = make("label", "Your reasoning (optional)", "practice-reflection-label"); reflectionLabel.htmlFor = "practiceReflection";
        const reflection = make("textarea", null, "practice-reflection"); reflection.id = "practiceReflection"; reflection.rows = 3; reflection.maxLength = 1600; reflection.value = saved.reflection; reflection.placeholder = "Why did you choose this answer?"; reflection.addEventListener("input", saveDraft);
        form.append(reflectionLabel, reflection);
        const actions = make("div", null, "practice-actions"), submit = make("button", "Submit answer", "button button-primary"); submit.type = "submit"; submit.id = "submitPracticeAnswer"; submit.dataset.disabled = String(!saved.option);
        actions.append(submit, button("Bỏ bản nháp", () => { state.drafts.delete(key()); render(); })); form.append(actions);
        form.addEventListener("submit", (event) => { event.preventDefault(); saveDraft(); if (draft().option) act("answer", { item_id: question.id, option_id: draft().option, reflection: draft().reflection }); }); box.append(form);
        if (question.feedback) {
            box.append(make("p", question.feedback.message || (question.feedback.correct ? "This matches the model answer." : "Try again, or request a hint."), "practice-feedback"));
            box.append(make("p", "Last submitted answer: " + question.selected_option + " · Attempts: " + question.attempts + (question.reflection ? " · Your reasoning: " + question.reflection : ""), "practice-help"));
        }
        for (const hint of question.hints || []) box.append(make("p", typeof hint === "string" ? hint : hint.text || "", "practice-hint"));
        const help = make("div", null, "practice-actions"), hint = button("Hint (" + question.hint_count + "/" + question.total_hints + ")", () => act("hint", { item_id: question.id }));
        hint.dataset.disabled = String(question.hint_count >= question.total_hints); help.append(hint);
        if (!question.answer) help.append(button("Show solution & source", () => act("solution", { item_id: question.id })));
        box.append(help); const answer = renderAnswer(question); if (answer) box.append(answer);
        if (question.feedback?.correct || question.solution_viewed) {
            const next = make("div", null, "practice-actions"); next.append(button((state.practice.current_index + 1 >= state.practice.total_items) ? "Finish practice" : "Next question →", () => { if (hasDraft()) { notice("Bạn còn bản nháp cho câu này. Hãy gửi hoặc Bỏ bản nháp trước khi tiếp tục."); return; } act("next", {}); }, "button button-primary")); box.append(next);
        }
        content.append(box);
    }
    function renderCompleted() {
        const content = byId("practiceContent"), summary = state.practice.summary || {}, list = make("ul", null, "practice-summary");
        [[summary.answered_count, "Questions answered"], [summary.first_try_correct, "Correct on first answer"], [summary.correct_after_help, "Correct after help"]].forEach(([value, label]) => { const item = make("li", null); item.append(make("strong", value ?? 0), document.createTextNode(label)); list.append(item); });
        content.append(list, make("p", summary.message || "Kết quả cho bộ câu hỏi này, không phải chứng nhận đã thành thạo.", "practice-help"), make("p", "Answers reviewed before start: " + (summary.answers_reviewed_before_start || 0), "practice-help"));
        const review = make("div", null, "practice-actions"), flashcards = make("a", "Create flashcards from this practice ↗", "button button-secondary");
        flashcards.id = "createPracticeFlashcards"; flashcards.href = "/learn/flashcards?practice=" + encodeURIComponent(state.practice.id); flashcards.target = "_blank"; flashcards.rel = "noopener";
        review.append(flashcards); content.append(review);
        (state.practice.questions || []).forEach((question, index) => { const box = questionHeading(question, index); box.append(make("p", "First answer correct: " + (question.first_try_correct === null ? "not answered" : String(question.first_try_correct)) + " · Hints: " + question.hint_count + " · Solution viewed: " + Boolean(question.solution_viewed), "practice-help")); const answer = renderAnswer(question); if (answer) box.append(answer); content.append(box); });
    }
    function render() {
        const practice = state.practice; show("practiceCreate", !practice); show("practiceSession", !!practice); byId("practiceContent").replaceChildren();
        if (!practice) { controls(); return; }
        state.orphanDrafts.forEach((kept, previousKey) => {
            const itemId = previousKey.split(":").pop();
            const saved = make("section", null, "practice-answer"); saved.dataset.draftItemId = itemId;
            saved.append(make("h4", "Bản nháp được giữ · " + itemId), make("p", "Option: " + kept.option + "\n" + kept.reflection), button("Bỏ bản nháp của " + itemId, () => { state.orphanDrafts.delete(previousKey); state.drafts.delete(previousKey); render(); }));
            byId("practiceContent").append(saved);
        });
        text("practiceSessionTitle", practice.title || "Practice"); text("practiceSessionState", statusNames[practice.status]);
        text("practiceScope", (practice.scope?.collection_title || state.collection?.title || "Selected source units") + " · " + (practice.provider || "") + " · " + (practice.model || "") + " · " + practice.total_items + " questions");
        if (practice.status === "draft") renderDraft();
        else if (practice.status === "active") renderActive();
        else if (practice.status === "completed") renderCompleted();
        else if (practice.status === "generating") { byId("practiceContent").append(make("p", "Yêu cầu đang được xử lý. Đọc bản đã lưu để kiểm tra; mở lại bộ này không tạo thêm lượt AI.", "practice-help"), button("Đọc bản đã lưu", reload)); }
        else byId("practiceContent").append(make("p", practice.error?.message || "Chưa tạo được câu hỏi. Bạn có thể xem lại nguồn rồi chủ động tạo bộ mới.", "practice-help"));
        renderHistory(); controls();
    }
    function adopt(value, focus = true) { state.practice = checked(value); render(); if (focus) (byId("practiceContent").querySelector("h3") || byId("practiceSessionTitle")).focus({ preventScroll: true }); }
    function preserveMovedDraft(previousKey, kept) {
        if (!(kept.option || kept.reflection) || previousKey === key()) return false;
        state.orphanDrafts.set(previousKey, kept); render();
        notice("Bộ đã tiến sang câu khác ở nơi khác. Bản nháp cũ không được áp dụng vào câu hiện tại.");
        return true;
    }
    async function generate() {
        if (state.busy) return;
        if (!state.pendingCreate) { if (!state.collection || !state.selected.size || state.selected.size > 8 || !state.model?.available) return; state.pendingCreate = { request_id: crypto.randomUUID(), collection_id: state.collection.id, unit_ids: Array.from(state.selected), count: Number(byId("practiceCount").value) }; }
        state.busy = true; notice(""); controls(); text("practiceStatus", "Đang tạo câu hỏi từ các đoạn đã chọn… Có thể mất khoảng một phút. Giữ trang này mở.");
        try { const result = await api(API, json("POST", state.pendingCreate), 75000); const value = checked(result.practice); state.pendingCreate = null; adopt(value); text("practiceStatus", value.status === "failed" ? "Yêu cầu đã kết thúc nhưng chưa tạo được câu hỏi. Không tự gọi lại model." : "Bộ câu hỏi đã được lưu. Bạn chọn khi nào bắt đầu."); history(); }
        catch (error) { if (!error.ambiguous) state.pendingCreate = null; notice(error.message + (state.pendingCreate ? " Chọn Kiểm tra lại đúng yêu cầu để tìm kết quả đã lưu; không tạo yêu cầu AI mới." : " Hãy xem lại phạm vi và thử khi sẵn sàng.")); }
        finally { state.busy = false; controls(); }
    }
    async function act(action, payload) {
        if (state.busy || !state.practice || state.conflict) return;
        if (!state.pendingAction) state.pendingAction = { action, payload, expected_revision: state.practice.revision, request_id: crypto.randomUUID() };
        const pending = state.pendingAction, id = state.practice.id, draftKey = key(), kept = draft();
        state.busy = true; notice(""); controls();
        try {
            const result = await api(address() + "/actions", json("POST", pending));
            if (state.practice.id !== id) return;
            checked(result.practice); state.pendingAction = null;
            const submittedDraft = pending.action === "answer" || pending.action === "next";
            if (submittedDraft) state.drafts.delete(draftKey);
            adopt(result.practice);
            if (!submittedDraft) preserveMovedDraft(draftKey, kept);
            text("practiceStatus", "Đã lưu thao tác của bạn."); history();
        } catch (error) {
            if (error.status === 409) { state.conflict = true; notice(error.message + " Bản nháp vẫn được giữ. Đọc bản đã lưu trước khi gửi tiếp."); }
            else { if (!error.ambiguous) state.pendingAction = null; notice(error.message + (state.pendingAction ? " Chưa rõ kết quả; kiểm tra lại đúng yêu cầu hoặc đọc bản đã lưu." : " Bản nháp vẫn được giữ.")); }
        } finally { state.busy = false; controls(); }
    }
    async function openPractice(id) {
        if (!guard()) return;
        const request = ++state.navigation; state.busy = true; notice(""); controls();
        try { const result = await api(API + "/" + encodeURIComponent(id)); if (request === state.navigation) { adopt(result.practice); text("practiceStatus", "Đã mở bộ thực hành đã lưu; không gọi model."); } }
        catch (error) { notice(error.message); } finally { state.busy = false; controls(); }
    }
    async function reload() {
        if (state.busy || !state.practice) return;
        state.busy = true; controls(); const before = key(), kept = draft();
        try { const result = await api(address()); const value = checked(result.practice); state.pendingAction = null; state.conflict = false; adopt(value, false); if (!preserveMovedDraft(before, kept)) notice(""); text("practiceStatus", "Đã đọc bản mới. Bản nháp của cùng câu vẫn được giữ; đọc kết quả trước khi gửi lại."); }
        catch (error) { notice(error.message + " Bản nháp vẫn được giữ."); } finally { state.busy = false; controls(); }
    }
    function newPractice() { if (!guard()) return; state.practice = null; show("practiceDeleteConfirm", false); notice(""); render(); byId("practiceCreateHeading").scrollIntoView({ block: "start" }); }
    async function remove() {
        if (state.busy || !state.practice || state.pendingAction || state.conflict) return;
        state.busy = true; controls();
        try { await api(address(), { method: "DELETE" }); state.drafts.delete(key()); state.practice = null; show("practiceDeleteConfirm", false); notice(""); render(); text("practiceStatus", "Đã xóa bộ thực hành."); history(); }
        catch (error) { notice(error.message + " Đọc lịch sử để kiểm tra bộ còn tồn tại trước khi thử tiếp."); }
        finally { state.busy = false; controls(); }
    }
    byId("practiceGenerateForm").addEventListener("submit", (event) => { event.preventDefault(); generate(); });
    byId("practiceCollection").addEventListener("change", () => selectCollection(byId("practiceCollection").value));
    byId("reloadPracticeHistory").addEventListener("click", history);
    byId("newPracticeButton").addEventListener("click", newPractice);
    byId("retryPracticeRequest").addEventListener("click", () => { if (state.pendingCreate) generate(); else if (state.pendingAction) act(); });
    byId("reloadPracticeButton").addEventListener("click", reload);
    byId("deletePracticeButton").addEventListener("click", () => { if (guard()) { show("practiceDeleteConfirm", true); byId("confirmPracticeDelete").focus(); } });
    byId("confirmPracticeDelete").addEventListener("click", remove);
    byId("cancelPracticeDelete").addEventListener("click", () => show("practiceDeleteConfirm", false));
    window.addEventListener("beforeunload", (event) => { if (state.busy || state.pendingCreate || state.pendingAction || state.conflict || hasDraft() || state.orphanDrafts.size) { event.preventDefault(); event.returnValue = ""; } });
    async function boot() {
        controls();
        const results = await Promise.allSettled([api(API + "/config"), api("/learn/api/materials"), history()]);
        if (results[0].status === "fulfilled") { state.model = results[0].value.model; text("practiceModel", state.model?.available ? state.model.provider + " · " + state.model.model + ". " + (state.model.provider === "gemini" ? "Các đoạn đã chọn được gửi tới dịch vụ Gemini cloud." : "Các đoạn đã chọn được gửi tới endpoint Ollama đã cấu hình, thường trên máy của bạn.") + " Không tự chuyển nhà cung cấp." : state.model?.reason || "Chưa có model được cấu hình để tạo câu hỏi."); }
        else text("practiceModel", "Chưa đọc được cấu hình AI. Tải lại trang để kiểm tra; lịch sử vẫn có thể mở.");
        if (results[1].status === "fulfilled") {
            state.collections = results[1].value.collections || [];
            state.collections.forEach((item) => { const option = make("option", item.title); option.value = item.id; byId("practiceCollection").append(option); });
            const params = new URLSearchParams(location.search), cid = params.get("collection"), uid = params.get("unit");
            if (cid && state.collections.some((item) => item.id === cid)) { byId("practiceCollection").value = cid; await selectCollection(cid, uid); }
            else if (cid || uid) notice("Liên kết nguồn không có trong kho của trình duyệt này. Hãy chọn bộ bài giảng.");
            if (!state.collections.length) text("practiceUnitStatus", "Kho chưa có tài liệu. Nhập bài giảng ở Tài liệu của tôi trước.");
        } else text("practiceUnitStatus", "Chưa đọc được kho bài giảng. Tải lại trang để thử tiếp.");
        controls();
    }
    boot();
})();
