/* The first Teacher lesson is authored content. All learner actions use the
 * server's versioned session; this view never grades or infers mastery. */
(function () {
    "use strict";

    const byId = (id) => document.getElementById(id);
    const state = { session: null, busy: false, loaded: false, pending: null, retry: null, draft: null };
    const preview = JSON.parse(byId("lessonPreview").textContent);
    const previewCode = preview.code;
    const assistanceText = {
        none: "Câu trả lời này được gửi trước khi xem trợ giúp.",
        hint: "Bạn đã dùng gợi ý. Kết quả này được ghi nhận là có trợ giúp.",
        solution: "Bạn đã xem lời giải. Kết quả này không được tính là một lần làm độc lập.",
        feedback: "Bạn đã xem phản hồi trước đó. Lần thử lại được ghi nhận là có trợ giúp."
    };

    function text(id, value) { byId(id).textContent = value == null ? "" : String(value); }
    function show(id, visible) { byId(id).hidden = !visible; }
    function announce(message) { text("announcement", message); }
    function focusHeading(id) { byId(id).focus(); }

    function requestId() {
        if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
        const bytes = new Uint8Array(16);
        globalThis.crypto.getRandomValues(bytes);
        return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
    }

    function notice(message, retry, info) {
        state.retry = retry || null;
        text("noticeText", message);
        byId("notice").classList.toggle("info", !!info);
        show("notice", true);
        show("retryButton", !!retry);
        updateControls();
    }

    function clearNotice() { state.retry = null; show("notice", false); show("retryButton", false); }

    function updateControls() {
        const session = state.session;
        const item = session && session.item;
        const blocked = state.busy || !!state.pending;
        const completed = session && session.status === "completed";
        const correct = item && item.feedback && item.feedback.correct === true;
        byId("workspace").setAttribute("aria-busy", String(state.busy || !state.loaded));
        byId("startButton").disabled = blocked || !state.loaded;
        byId("restartButton").disabled = blocked;
        byId("exportButton").disabled = blocked || !session;
        byId("deleteButton").disabled = blocked || !session;
        byId("retryButton").disabled = state.busy;
        byId("optionsFieldset").disabled = blocked || completed || correct;
        byId("reflectionInput").disabled = blocked || completed || correct;
        byId("answerButton").disabled = blocked || completed || correct || !state.draft || !state.draft.selected;
        byId("hintButton").disabled = blocked || completed || correct || !item || item.hint_count >= item.total_hints;
        byId("solutionButton").disabled = blocked || completed || !item || !!item.solution;
        byId("nextButton").disabled = blocked || completed || !item || !(item.answered || item.solution);
        if (session) text("saveStatus", state.busy ? "Đang lưu…" : state.pending ? "Chưa xác nhận đã lưu" : "Đã lưu phiên");
    }

    function busy(value) { state.busy = value; updateControls(); }

    async function api(url, options) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);
        try {
            const response = await fetch(url, Object.assign({ credentials: "same-origin", cache: "no-store", signal: controller.signal }, options));
            let data;
            try { data = await response.json(); } catch (_) {
                const error = new Error("Không đọc được phản hồi từ máy chủ.");
                error.status = response.status;
                error.ambiguous = true;
                throw error;
            }
            if (!response.ok || data.ok === false) {
                const error = new Error(data.error || "Yêu cầu chưa được xử lý.");
                error.status = response.status;
                error.code = data.error_code || "";
                error.ambiguous = response.status >= 500;
                throw error;
            }
            return data;
        } catch (error) {
            if (!error.status) error.ambiguous = true;
            throw error;
        } finally { clearTimeout(timeout); }
    }

    function errorMessage(error) {
        if (error.status === 401 || error.status === 403) return "Phiên truy cập cần được xác thực lại. Dùng phần đăng nhập trên trang, rồi thử lại; câu trả lời của bạn vẫn còn ở đây.";
        if (error.status === 404) return "Không tìm thấy phiên học này. Có thể phiên đã được xóa ở một cửa sổ khác.";
        if (error.code === "invalid_option") return "Lựa chọn này không còn thuộc câu hỏi hiện tại. Hãy tải lại phiên học.";
        if (error.status === 429) return "Có quá nhiều yêu cầu cùng lúc. Hãy đợi một chút rồi thử lại.";
        return "Chưa kết nối được với phiên học. Câu trả lời đang nhập vẫn được giữ trên trang này.";
    }

    function appendSyntax(line, source) {
        const tokens = /(\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:class|extends|public|private|protected|static|void|return|new|super|this|final|int|boolean|String)\b)/g;
        let index = 0;
        for (const match of source.matchAll(tokens)) {
            line.append(document.createTextNode(source.slice(index, match.index)));
            const token = document.createElement("span");
            token.className = match[0].startsWith("//") ? "token-comment" : /^["']/.test(match[0]) ? "token-string" : "token-keyword";
            token.textContent = match[0];
            line.append(token);
            index = match.index + match[0].length;
        }
        line.append(document.createTextNode(source.slice(index) || (source.length ? "" : " ")));
    }

    function renderCode(code, evidence) {
        const marked = new Set(Array.isArray(evidence) ? evidence : []);
        const fragment = document.createDocumentFragment();
        String(code || "").replace(/\r\n/g, "\n").split("\n").forEach((source, index) => {
            const line = document.createElement("span");
            line.className = "code-line";
            line.dataset.line = String(index + 1);
            if (marked.has(index + 1)) {
                line.classList.add("evidence");
                line.title = "Dòng " + (index + 1) + " — bằng chứng trong phản hồi";
            }
            appendSyntax(line, source);
            fragment.append(line);
        });
        byId("lessonCode").replaceChildren(fragment);
        text("codeCaption", marked.size ? "Các dòng được tô sáng là bằng chứng trong lời giải thích" : "Chỉ đọc · Hãy thử chạy đoạn code trong đầu");
    }

    function captureDraft() {
        if (!state.draft) return;
        const selected = document.querySelector('input[name="answerOption"]:checked');
        state.draft.selected = selected ? selected.value : null;
        state.draft.reflection = byId("reflectionInput").value;
        state.draft.open = byId("reflectionDetails").open;
    }

    function renderOptions(item) {
        const fragment = document.createDocumentFragment();
        (item.options || []).forEach((option, index) => {
            const label = document.createElement("label");
            label.className = "answer-option";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "answerOption";
            input.value = option.id;
            input.checked = state.draft.selected === option.id;
            const caption = document.createElement("span");
            caption.className = "option-label";
            caption.textContent = option.label;
            const letter = document.createElement("span");
            letter.className = "option-letter";
            letter.setAttribute("aria-hidden", "true");
            letter.textContent = String.fromCharCode(65 + index);
            label.append(input, caption, letter);
            fragment.append(label);
        });
        byId("optionsList").replaceChildren(fragment);
        byId("reflectionInput").value = state.draft.reflection;
        byId("reflectionDetails").open = state.draft.open;
    }

    function renderSteps(session) {
        const fragment = document.createDocumentFragment();
        (session.items || []).forEach((item, index) => {
            const li = document.createElement("li");
            const current = index === session.current_index && session.status !== "completed";
            const done = index < session.current_index || session.status === "completed";
            li.className = current ? "current" : done ? "done" : "";
            if (current) li.setAttribute("aria-current", "step");
            const marker = document.createElement("span");
            marker.className = "step-marker";
            marker.setAttribute("aria-hidden", "true");
            marker.textContent = done ? "✓" : String(index + 1);
            const label = document.createElement("span");
            label.textContent = item.title;
            if (item.solution_viewed) label.append(document.createTextNode(" · Đã xem lời giải"));
            li.append(marker, label);
            fragment.append(li);
        });
        byId("lessonSteps").replaceChildren(fragment);
        text("progressText", session.status === "completed" ? "Đã đi qua " + session.total_items + " tình huống." : "Tình huống " + (session.current_index + 1) + " / " + session.total_items + " · Theo nhịp của bạn.");
    }

    function renderSession(session) {
        const previousKey = state.draft && state.draft.key;
        state.session = session;
        state.loaded = true;
        show("sessionTools", !!session);
        show("welcomeCard", !session);
        show("questionCard", !!session && session.status !== "completed");
        show("summaryCard", !!session && session.status === "completed");
        if (!session) {
            state.draft = null;
            text("lessonTitle", "Đọc code. Hiểu điều xảy ra.");
            text("lessonSubtitle", "Một đoạn code nhỏ, một ý tưởng để tự khám phá.");
            text("lessonBadge", "Bài thử đầu tiên");
            text("filename", preview.filename);
            byId("startButton").firstElementChild.textContent = "Bắt đầu bài học";
            ["hintsCard", "feedbackCard", "solutionCard", "nextButton"].forEach((id) => show(id, false));
            renderCode(previewCode, []);
            text("progressText", "Đi từng bước, theo nhịp của bạn.");
            byId("lessonSteps").replaceChildren();
            ["Quan sát code", "Tự đưa ra dự đoán", "Thử một tình huống mới"].forEach((label, index) => {
                const li = document.createElement("li");
                const marker = document.createElement("span");
                marker.className = "step-marker";
                marker.textContent = String(index + 1);
                const caption = document.createElement("span");
                caption.textContent = label;
                li.append(marker, caption);
                byId("lessonSteps").append(li);
            });
            updateControls();
            return;
        }
        const item = session.item;
        const key = session.id + ":" + item.id;
        if (previousKey !== key) state.draft = { key, selected: item.selected_option || null, reflection: item.reflection || "", open: !!item.reflection };
        text("lessonTitle", session.lesson.title);
        text("lessonSubtitle", session.lesson.subtitle);
        text("lessonBadge", session.status === "completed" ? "Bài học đã hoàn tất" : "Tình huống " + (session.current_index + 1) + " / " + session.total_items);
        text("filename", item.filename);
        text("itemPosition", String(session.current_index + 1).padStart(2, "0") + " / " + item.title.replace(/^\d+\.\s*/, "").toLocaleUpperCase("vi"));
        text("questionTitle", item.question);
        renderOptions(item);
        renderSteps(session);
        const evidence = item.solution ? item.solution.evidence_lines : item.feedback ? item.feedback.evidence_lines : [];
        renderCode(item.code, evidence);
        show("hintsCard", !!item.hints && item.hints.length > 0);
        byId("hintsList").replaceChildren();
        (item.hints || []).forEach((hint) => {
            const paragraph = document.createElement("p");
            paragraph.textContent = hint;
            byId("hintsList").append(paragraph);
        });
        text("hintButton", item.hint_count >= item.total_hints ? "Đã xem hết gợi ý" : item.hint_count ? "Gợi ý tiếp theo (" + item.hint_count + "/" + item.total_hints + ")" : "Cho tôi một gợi ý");
        show("feedbackCard", !!item.feedback);
        if (item.feedback) {
            text("feedbackHeading", item.feedback.heading);
            text("feedbackBody", item.feedback.body);
            text("assistanceLabel", assistanceText[item.feedback.assistance] || "Kết quả được ghi lại cùng các trợ giúp bạn đã xem.");
            byId("feedbackCard").classList.toggle("needs-work", item.feedback.correct !== true);
        }
        show("solutionCard", !!item.solution);
        if (item.solution) text("solutionBody", item.solution.body);
        byId("answerButton").firstElementChild.textContent = item.feedback ? item.feedback.correct ? "Đã ghi nhận dự đoán" : "Kiểm tra lại" : "Kiểm tra dự đoán";
        show("nextButton", session.status !== "completed" && !!(item.answered || item.solution));
        byId("nextButton").firstElementChild.textContent = session.current_index + 1 >= session.total_items ? "Nhìn lại bài học" : "Thử tình huống tiếp theo";
        if (session.status === "completed") {
            const summary = session.summary;
            text("summaryMessage", "Bạn đã gửi câu trả lời cho " + summary.answered_count + "/" + session.total_items + " tình huống. Cùng nhìn lại những gì đã diễn ra trong phiên này.");
            text("independentSuccesses", summary.independent_successes);
            text("independentFailures", summary.independent_failures);
            text("assistedSuccesses", summary.assisted_successes);
        }
        updateControls();
    }

    async function loadLatest(message) {
        if (state.busy) return;
        captureDraft();
        busy(true);
        try {
            const data = await api("/learn/api/session");
            state.pending = null;
            clearNotice();
            renderSession(data.session);
            if (message) notice(message, null, true);
        } catch (error) { notice(errorMessage(error), () => loadLatest(message)); }
        finally { busy(false); }
    }

    async function startSession() {
        if (state.busy || state.pending) return;
        busy(true);
        clearNotice();
        try {
            const data = await api("/learn/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
            renderSession(data.session);
            focusHeading("questionTitle");
            announce("Bài học đã sẵn sàng. Hãy đọc code và chọn dự đoán của bạn.");
        } catch (error) {
            // Creating twice after an uncertain response would lose the latest
            // session pointer. Recover by reading before offering another start.
            state.loaded = false;
            state.pending = { kind: "start" };
            notice("Chưa xác nhận được bài học đã mở. Kiểm tra phiên đang lưu trước khi bắt đầu lại.", () => loadLatest("Đã kiểm tra phiên đang lưu. Bạn có thể tiếp tục từ đây."));
        } finally { busy(false); }
    }

    async function reloadCurrentAfterConflict() {
        try {
            const data = await api("/learn/api/sessions/" + encodeURIComponent(state.session.id));
            state.pending = null;
            renderSession(data.session);
            notice("Phiên học đã thay đổi ở cửa sổ khác. Đã mở bản mới nhất; kiểm tra câu hỏi trước khi gửi tiếp.", null, true);
        } catch (error) {
            state.pending = null;
            notice(errorMessage(error), () => loadLatest());
        }
    }

    async function sendPending() {
        if (!state.pending || state.busy) return;
        const pending = state.pending;
        busy(true);
        clearNotice();
        try {
            const data = await api(pending.url, { method: "POST", headers: { "Content-Type": "application/json" }, body: pending.body });
            state.pending = null;
            renderSession(data.session);
            const action = pending.action;
            if (data.session.status === "completed") focusHeading("summaryHeading");
            else if (action === "answer") focusHeading("feedbackHeading");
            else if (action === "hint") focusHeading("hintsHeading");
            else if (action === "solution") focusHeading("solutionHeading");
            else if (action === "next") focusHeading("questionTitle");
            announce(action === "answer" ? "Đã lưu câu trả lời và mở phản hồi." : action === "hint" ? "Đã mở gợi ý." : action === "solution" ? "Đã mở lời giải." : "Đã chuyển bước học.");
        } catch (error) {
            if (error.status === 409) await reloadCurrentAfterConflict();
            else if (error.ambiguous) notice("Chưa nhận được xác nhận. Bấm Thử lại để kiểm tra đúng thao tác vừa gửi; bài làm sẽ không bị ghi hai lần.", sendPending);
            else {
                state.pending = null;
                notice(errorMessage(error), error.status === 404 ? () => loadLatest() : null);
            }
        } finally { busy(false); }
    }

    function act(action, payload) {
        if (!state.session || state.busy || state.pending) return;
        captureDraft();
        state.pending = {
            action,
            url: "/learn/api/sessions/" + encodeURIComponent(state.session.id) + "/actions",
            body: JSON.stringify({ action, payload: payload || {}, expected_revision: state.session.revision, request_id: requestId() })
        };
        sendPending();
    }

    async function deleteSession() {
        if (!state.session || state.busy || state.pending) return;
        if (!globalThis.confirm("Xóa phiên học này cùng câu trả lời và các trợ giúp đã ghi nhận? Hãy tải bài làm trước nếu bạn cần giữ lại. Thao tác này không thể hoàn tác.")) return;
        busy(true);
        clearNotice();
        const sessionId = state.session.id;
        try {
            await api("/learn/api/sessions/" + encodeURIComponent(sessionId), { method: "DELETE" });
            renderSession(null);
            notice("Đã xóa phiên học này khỏi máy chủ.", null, true);
            focusHeading("lessonTitle");
        } catch (error) {
            state.pending = { kind: "delete" };
            notice("Chưa xác nhận được việc xóa phiên. Hãy kiểm tra bản đang lưu trước khi tiếp tục.", () => loadLatest());
        } finally { busy(false); }
    }

    async function exportSession() {
        if (!state.session || state.busy) return;
        const id = state.session.id;
        busy(true);
        clearNotice();
        try {
            const response = await fetch("/learn/api/sessions/" + encodeURIComponent(id) + "/export", { credentials: "same-origin", cache: "no-store" });
            if (!response.ok) throw new Error("export failed");
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "cattus-bai-hoc-" + id + ".json";
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            announce("Đã chuẩn bị tệp bài làm để tải xuống.");
        } catch (_) { notice("Chưa tải được dữ liệu bài làm. Phiên học vẫn được giữ nguyên.", exportSession); }
        finally { busy(false); }
    }

    byId("startButton").addEventListener("click", startSession);
    byId("restartButton").addEventListener("click", startSession);
    byId("hintButton").addEventListener("click", () => act("hint"));
    byId("solutionButton").addEventListener("click", () => act("solution"));
    byId("nextButton").addEventListener("click", () => act("next"));
    byId("deleteButton").addEventListener("click", deleteSession);
    byId("exportButton").addEventListener("click", exportSession);
    byId("retryButton").addEventListener("click", () => { if (state.retry) state.retry(); });
    byId("optionsList").addEventListener("change", () => { captureDraft(); updateControls(); });
    byId("reflectionInput").addEventListener("input", captureDraft);
    byId("reflectionDetails").addEventListener("toggle", captureDraft);
    byId("answerForm").addEventListener("submit", (event) => {
        event.preventDefault();
        captureDraft();
        if (state.draft && state.draft.selected) act("answer", { option_id: state.draft.selected, reflection: state.draft.reflection });
    });
    renderCode(previewCode, []);
    loadLatest();
})();
