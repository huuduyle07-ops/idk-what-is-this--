/* Flashcards reuse completed Practice snapshots; no model operation occurs here. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const text = (id, value) => { byId(id).textContent = value; };
    const show = (id, visible) => { byId(id).hidden = !visible; };
    const make = (tag, value, className) => { const el = document.createElement(tag); if (value != null) el.textContent = value; if (className) el.className = className; return el; };
    const API = "/learn/api/flashcards";
    const state = { practices: [], practice: null, selected: new Set(), deck: null, cardId: null, filter: "due",
        history: [], busy: false, loading: false, sequence: 0, historySequence: 0,
        pendingCreate: null, pendingAction: null, pendingDelete: false, conflict: false };
    const address = () => API + "/" + encodeURIComponent(state.deck.id);
    const queue = () => (state.deck?.cards || []).filter((card) => state.filter === "all" || (state.filter === "due" ? card.due : card.needs_review));
    const currentCard = () => queue().find((card) => card.id === state.cardId) || queue()[0] || null;
    function button(label, action, className = "text-button") { const item = make("button", label, className); item.type = "button"; item.addEventListener("click", action); return item; }
    function notice(message) { text("flashcardNoticeText", message); show("flashcardNotice", !!message); controls(); }
    function dateLabel(value) { const date = new Date(value); return Number.isFinite(date.getTime()) ? date.toLocaleString() : "—"; }
    function citation(value) { return ({ page: "Page", slide: "Slide", paragraph: "Paragraph", table: "Table", image: "Image" }[value.locator?.kind] || "Unit") + " " + (value.locator?.index || ""); }
    function guard() {
        if (state.busy || state.loading) { notice("Đang đọc hoặc lưu thẻ. Hãy đợi thao tác hoàn tất."); return false; }
        if (state.pendingCreate || state.pendingAction || state.pendingDelete || state.conflict) { notice("Kết quả yêu cầu trước chưa rõ. Kiểm tra đúng yêu cầu hoặc đọc bộ đã lưu trước khi chuyển."); return false; }
        return true;
    }
    function controls() {
        const locked = state.busy || state.loading || !!state.pendingCreate || !!state.pendingAction || state.pendingDelete || state.conflict;
        byId("flashcardPractice").disabled = locked || !state.practices.length;
        byId("createFlashcardsButton").disabled = locked || !state.practice || !state.selected.size;
        byId("flashcardQuestions").querySelectorAll("input").forEach((item) => { item.disabled = locked; });
        byId("flashcardFilter").disabled = locked;
        byId("newFlashcardDeck").disabled = state.busy || state.loading;
        byId("refreshFlashcardHistory").disabled = state.busy;
        byId("flashcardHistory").querySelectorAll("button").forEach((item) => { item.disabled = state.busy || state.loading; });
        byId("deleteFlashcardDeck").disabled = locked;
        byId("confirmFlashcardDelete").disabled = locked;
        byId("cancelFlashcardDelete").disabled = state.busy || state.pendingDelete;
        byId("refreshFlashcardDeck").disabled = state.busy || state.loading;
        byId("flashcardContent").querySelectorAll("button").forEach((item) => { item.disabled = locked || item.dataset.disabled === "true"; });
        show("retryFlashcardRequest", !!state.pendingCreate || (!!state.pendingAction && !state.conflict));
        byId("retryFlashcardRequest").disabled = state.busy;
        show("reloadFlashcardDeck", !!state.deck);
        byId("reloadFlashcardDeck").disabled = state.busy || state.loading;
        byId("flashcardCreateForm").setAttribute("aria-busy", String(state.busy && !!state.pendingCreate));
        byId("flashcardDeck").setAttribute("aria-busy", String(state.busy));
    }
    async function api(url, options) {
        const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 20000);
        try {
            const response = await fetch(url, Object.assign({ credentials: "same-origin", cache: "no-store", signal: controller.signal }, options));
            let value;
            try { value = await response.json(); } catch (_) { const error = new Error("Chưa đọc được xác nhận từ máy chủ."); error.ambiguous = true; throw error; }
            if (!response.ok || value.ok === false) { const error = new Error(value.error || "Chưa thực hiện được yêu cầu."); error.status = response.status; error.ambiguous = response.status >= 500; throw error; }
            return value;
        } catch (error) { if (!error.status) error.ambiguous = true; throw error; }
        finally { clearTimeout(timeout); }
    }
    function json(method, body) { return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }; }
    function checked(deck) {
        if (!deck || typeof deck.id !== "string" || !Number.isSafeInteger(deck.revision) || !Array.isArray(deck.cards)) { const error = new Error("Phản hồi bộ thẻ chưa hợp lệ."); error.ambiguous = true; throw error; }
        return deck;
    }
    function renderHistory() {
        byId("flashcardHistory").replaceChildren(...state.history.map((deck) => {
            const row = make("li"), open = button(deck.title || "Flashcards", () => openDeck(deck.id));
            open.dataset.deckId = deck.id; open.setAttribute("aria-current", String(state.deck?.id === deck.id));
            open.append(make("small", (deck.counts?.total || 0) + " cards · " + (deck.counts?.due || 0) + " due")); row.append(open); return row;
        }));
        text("flashcardHistoryStatus", state.history.length ? "Lịch ôn được lưu với trình duyệt này." : "Chưa có bộ thẻ. Hoàn thành Practice để bắt đầu."); controls();
    }
    async function history() {
        const request = ++state.historySequence;
        try { const result = await api(API); if (request !== state.historySequence) return; state.history = result.decks || []; renderHistory(); }
        catch (_) { if (request === state.historySequence) text("flashcardHistoryStatus", "Chưa đọc được lịch sử. Chọn Đọc lại để thử tiếp."); }
    }
    function weak(question) { return question.first_try_correct === false || question.hint_count > 0 || question.solution_viewed || question.answer_reviewed; }
    function selectionStatus() { text("flashcardSelectionStatus", state.practice ? state.selected.size + " / " + state.practice.questions.length + " câu đã chọn. Giữ nguyên câu hỏi và nguồn đã lưu; không sinh nội dung mới." : "Chọn một bài Practice đã hoàn thành."); }
    function renderQuestions() {
        byId("flashcardQuestions").replaceChildren(...(state.practice?.questions || []).map((question, index) => {
            const label = make("label", null, "flash-question"), input = document.createElement("input"), body = make("span", "Question " + (index + 1) + " · " + question.question);
            input.type = "checkbox"; input.value = question.id; input.checked = state.selected.has(question.id);
            input.addEventListener("change", () => { if (input.checked) state.selected.add(question.id); else state.selected.delete(question.id); selectionStatus(); controls(); });
            body.append(make("small", question.objective + " · " + (weak(question) ? "Có trợ giúp hoặc cần ôn thêm ở bài trước" : "Đã khớp đáp án ở lần đầu"))); label.append(input, body); return label;
        }));
        selectionStatus(); controls();
    }
    async function selectPractice(id) {
        const request = ++state.sequence;
        state.loading = true; state.practice = null; state.selected.clear(); renderQuestions(); text("flashcardSelectionStatus", "Đang đọc bài đã hoàn thành…"); controls();
        if (!id) { state.loading = false; selectionStatus(); controls(); return; }
        try {
            const result = await api("/learn/api/practice/" + encodeURIComponent(id));
            if (request !== state.sequence) return;
            if (result.practice?.status !== "completed") throw new Error("Chỉ tạo thẻ sau khi hoàn thành bài Practice.");
            state.practice = result.practice;
            const selected = state.practice.questions.filter(weak);
            (selected.length ? selected : state.practice.questions).forEach((question) => state.selected.add(question.id));
            renderQuestions();
        } catch (error) { if (request === state.sequence) text("flashcardSelectionStatus", error.message); }
        finally { if (request === state.sequence) { state.loading = false; controls(); } }
    }
    function renderAnswer(card) {
        if (!card.answer) return null;
        const answer = make("section", null, "flash-answer"); answer.id = "flashcardAnswer";
        answer.append(make("h4", "ANSWER · TỪ PRACTICE"), make("p", card.answer.text, "flash-answer-text"), make("p", card.answer.explanation));
        (card.answer.evidence || []).forEach((source) => {
            const evidence = make("details", null, "flash-answer-source");
            evidence.append(make("summary", (source.source_name || "Source") + " · " + citation(source)), make("p", source.origin === "user_note" ? "Ghi chú ảnh của bạn tại lúc tạo bài, chưa phải OCR." : "Đoạn trích lưu tại lúc tạo bài; đối chiếu với file gốc khi cần.", "flash-help"), make("blockquote", source.text));
            if (state.deck.scope?.collection_id && source.unit_id) { const link = make("a", "Mở phần nguồn trong tab mới ↗"); link.href = "/learn/materials?collection=" + encodeURIComponent(state.deck.scope.collection_id) + "&unit=" + encodeURIComponent(source.unit_id); link.target = "_blank"; link.rel = "noopener"; evidence.append(link); }
            answer.append(evidence);
        });
        return answer;
    }
    function move(offset) {
        if (!guard()) return;
        const cards = queue(), index = cards.findIndex((card) => card.id === currentCard()?.id);
        if (!cards.length) return;
        state.cardId = cards[(index + offset + cards.length) % cards.length].id; renderCard(true);
    }
    function renderCard(focus = false) {
        const content = byId("flashcardContent"), cards = queue(), card = currentCard(); content.replaceChildren();
        const counts = state.deck?.counts || {};
        text("flashcardCounts", (counts.total || 0) + " cards · " + (counts.due || 0) + " due now · " + (counts.needs_review || 0) + " need review");
        if (!card) {
            const empty = make("div", null, "flash-empty"), heading = make("h3", state.filter === "due" ? "Chưa có thẻ đến hạn trong bộ này." : "Không có thẻ trong danh sách này.");
            heading.id = "flashcardEmptyTitle"; heading.tabIndex = -1; empty.append(heading);
            const upcoming = (state.deck?.cards || []).map((item) => new Date(item.due_at)).filter((date) => Number.isFinite(date.getTime())).sort((a, b) => a - b)[0];
            if (upcoming) empty.append(make("p", "Lịch gần nhất: " + dateLabel(upcoming), "flash-help"));
            empty.append(button("Xem tất cả thẻ", () => { if (!guard()) return; state.filter = "all"; byId("flashcardFilter").value = "all"; renderCard(true); }, "button button-secondary")); content.append(empty); controls(); if (focus) heading.focus({ preventScroll: true }); return;
        }
        state.cardId = card.id;
        const position = cards.findIndex((item) => item.id === card.id), box = make("article", null, "flash-review-card"); box.dataset.cardId = card.id;
        box.append(make("p", "Card " + (position + 1) + " / " + cards.length + " · " + card.review_count + " reviews", "flash-card-position"), make("p", card.objective || "", "flash-objective"));
        const front = make("h3", card.front, "flash-front"); front.id = "flashcardFront"; front.tabIndex = -1; box.append(front);
        if (card.choices) { const choices = make("ol", null, "flash-choices"); choices.type = "a"; card.choices.forEach((option) => choices.append(make("li", option.text))); box.append(choices, make("p", "Đã xem lựa chọn gợi ý của câu trắc nghiệm gốc.", "flash-help")); }
        const actions = make("div", null, "flash-actions");
        if (!card.choices && !card.revealed) actions.append(button("Show original choices", () => act("choices", { card_id: card.id })));
        actions.append(card.revealed ? button("Hide answer", () => act("hide", { card_id: card.id })) : button("Reveal answer", () => act("reveal", { card_id: card.id }), "button button-primary")); box.append(actions);
        const answer = renderAnswer(card); if (answer) box.append(answer);
        if (card.revealed && card.answer) {
            const ratings = make("section", null, "flash-ratings"), buttons = make("div", null, "flash-actions");
            ratings.append(make("p", "Bạn tự nhớ được đến đâu? Chỉ ghi nhận tự đánh giá này, không chấm câu trả lời."));
            buttons.append(button("Again · 10 min", () => act("rate", { card_id: card.id, rating: "again" }), "button button-secondary"), button("Got it · ôn sau", () => act("rate", { card_id: card.id, rating: "got_it" }), "button button-primary")); ratings.append(buttons); box.append(ratings);
        }
        box.append(make("p", "Next due: " + dateLabel(card.due_at) + (card.needs_review ? " · Needs review" : ""), "flash-help"));
        const navigation = make("div", null, "flash-navigation"), previous = button("← Previous card", () => move(-1)), next = button("Next card →", () => move(1)); previous.dataset.disabled = next.dataset.disabled = String(cards.length < 2); navigation.append(previous, next); box.append(navigation); content.append(box); controls();
        if (focus) front.focus({ preventScroll: true });
    }
    function render() {
        show("flashcardCreate", !state.deck); show("flashcardDeck", !!state.deck);
        if (state.deck) { text("flashcardDeckTitle", state.deck.title || "Flashcards"); text("flashcardScope", (state.deck.scope?.collection_title || "") + " · " + (state.deck.provider || "") + " · " + (state.deck.model || "") + " · Practice snapshot"); renderCard(); }
        renderHistory(); controls();
    }
    function adopt(deck, focus = false) { state.deck = checked(deck); render(); if (focus) (byId("flashcardFront") || byId("flashcardEmptyTitle") || byId("flashcardDeckTitle")).focus({ preventScroll: true }); }
    async function create() {
        if (state.busy || state.loading) return;
        if (!state.pendingCreate) { if (!state.practice || !state.selected.size) return; state.pendingCreate = { request_id: crypto.randomUUID(), practice_id: state.practice.id, question_ids: Array.from(state.selected) }; }
        state.busy = true; notice(""); controls(); text("flashcardStatus", "Đang lưu thẻ từ bài Practice… Không gọi AI.");
        try { const result = await api(API, json("POST", state.pendingCreate)); checked(result.deck); state.pendingCreate = null; state.filter = "due"; byId("flashcardFilter").value = "due"; state.cardId = null; adopt(result.deck, true); text("flashcardStatus", "Đã lưu bộ thẻ. Hãy thử tự trả lời trước khi Reveal answer."); history(); }
        catch (error) { if (!error.ambiguous) state.pendingCreate = null; notice(error.message + (state.pendingCreate ? " Kiểm tra lại đúng yêu cầu để mở kết quả đã lưu." : " Chọn lại bài hoặc thử khi sẵn sàng.")); }
        finally { state.busy = false; controls(); }
    }
    async function act(action, payload) {
        if (state.busy || state.loading || !state.deck || state.conflict || state.pendingDelete) return;
        if (!state.pendingAction) state.pendingAction = { action, payload, expected_revision: state.deck.revision, request_id: crypto.randomUUID() };
        const pending = state.pendingAction, oldId = state.deck.id, oldQueue = queue().map((card) => card.id), oldCard = pending.payload.card_id;
        state.busy = true; notice(""); controls();
        try {
            const result = await api(address() + "/actions", json("POST", pending));
            if (state.deck.id !== oldId) return;
            checked(result.deck); state.pendingAction = null;
            if (pending.action === "rate") { const index = oldQueue.indexOf(oldCard); state.cardId = oldQueue[(index + 1) % oldQueue.length] || null; }
            adopt(result.deck, true); text("flashcardStatus", pending.action === "rate" ? "Đã lưu tự đánh giá và lịch ôn. Không coi đây là mức thành thạo." : "Đã lưu thao tác của bạn."); history();
        } catch (error) {
            if (error.status === 409) { state.conflict = true; notice(error.message + " Chưa áp dụng thêm tự đánh giá. Đọc bộ đã lưu trước khi chọn tiếp."); }
            else { if (!error.ambiguous) state.pendingAction = null; notice(error.message + (state.pendingAction ? " Kết quả chưa rõ; kiểm tra lại đúng yêu cầu hoặc đọc bộ đã lưu." : " Bộ thẻ vẫn được giữ.")); }
        } finally { state.busy = false; controls(); }
    }
    async function openDeck(id) {
        if (!guard()) return;
        const request = ++state.sequence; state.busy = true; notice(""); controls();
        try { const result = await api(API + "/" + encodeURIComponent(id)); if (request === state.sequence) { state.cardId = null; adopt(result.deck, true); text("flashcardStatus", "Đã mở bộ thẻ đã lưu; không gọi AI."); } }
        catch (error) { notice(error.message); } finally { state.busy = false; controls(); }
    }
    async function reload() {
        if (state.busy || state.loading || !state.deck) return;
        state.busy = true; controls();
        try { const result = await api(address()); checked(result.deck); state.pendingAction = null; state.pendingDelete = false; state.conflict = false; adopt(result.deck); notice(""); text("flashcardStatus", "Đã đọc bản mới. Xem lại thẻ trước khi tự đánh giá tiếp."); history(); }
        catch (error) { if (error.status === 404 && state.pendingDelete) { state.deck = null; state.pendingDelete = false; show("flashcardDeleteConfirm", false); notice(""); render(); history(); text("flashcardStatus", "Bộ thẻ đã được xóa."); } else notice(error.message); }
        finally { state.busy = false; controls(); }
    }
    function newDeck() { if (!guard()) return; state.sequence += 1; state.deck = null; state.cardId = null; show("flashcardDeleteConfirm", false); notice(""); render(); byId("flashcardCreateTitle").scrollIntoView({ block: "start" }); }
    async function remove() {
        if (state.busy || !state.deck || state.pendingAction || state.conflict) return;
        state.busy = true; controls();
        try { await api(address(), { method: "DELETE" }); state.deck = null; state.cardId = null; state.pendingDelete = false; show("flashcardDeleteConfirm", false); notice(""); render(); history(); text("flashcardStatus", "Đã xóa bộ thẻ. Bài Practice và bài giảng vẫn được giữ."); }
        catch (error) { state.pendingDelete = !!error.ambiguous; notice(error.message + " Đọc bộ đã lưu để kiểm tra kết quả trước khi thao tác tiếp."); }
        finally { state.busy = false; controls(); }
    }
    byId("flashcardCreateForm").addEventListener("submit", (event) => { event.preventDefault(); create(); });
    byId("flashcardPractice").addEventListener("change", () => selectPractice(byId("flashcardPractice").value));
    byId("flashcardFilter").addEventListener("change", () => { if (!guard()) { byId("flashcardFilter").value = state.filter; return; } state.filter = byId("flashcardFilter").value; state.cardId = null; renderCard(true); });
    byId("newFlashcardDeck").addEventListener("click", newDeck);
    byId("refreshFlashcardHistory").addEventListener("click", history);
    byId("refreshFlashcardDeck").addEventListener("click", reload);
    byId("retryFlashcardRequest").addEventListener("click", () => { if (state.pendingCreate) create(); else if (state.pendingAction) act(); });
    byId("reloadFlashcardDeck").addEventListener("click", reload);
    byId("deleteFlashcardDeck").addEventListener("click", () => { if (guard()) { show("flashcardDeleteConfirm", true); byId("confirmFlashcardDelete").focus(); } });
    byId("confirmFlashcardDelete").addEventListener("click", remove);
    byId("cancelFlashcardDelete").addEventListener("click", () => show("flashcardDeleteConfirm", false));
    window.addEventListener("beforeunload", (event) => { if (state.busy || state.pendingCreate || state.pendingAction || state.pendingDelete || state.conflict) { event.preventDefault(); event.returnValue = ""; } });
    async function boot() {
        controls();
        const results = await Promise.allSettled([api("/learn/api/practice"), history()]);
        if (results[0].status === "fulfilled") {
            state.practices = (results[0].value.practices || []).filter((practice) => practice.status === "completed");
            state.practices.forEach((practice) => { const option = make("option", practice.title); option.value = practice.id; byId("flashcardPractice").append(option); });
            const pid = new URLSearchParams(location.search).get("practice");
            if (pid && state.practices.some((practice) => practice.id === pid)) { byId("flashcardPractice").value = pid; await selectPractice(pid); }
            else if (pid) notice("Bài trong liên kết chưa hoàn thành hoặc không thuộc trình duyệt này. Hãy chọn một bài đã hoàn thành.");
            if (!state.practices.length) text("flashcardSelectionStatus", "Chưa có bài Practice đã hoàn thành. Hoàn thành một bộ để tạo thẻ.");
            else if (!pid) selectionStatus();
        } else text("flashcardSelectionStatus", "Chưa đọc được bài Practice. Tải lại trang để thử tiếp; bộ thẻ cũ vẫn có thể mở.");
        controls();
    }
    boot();
})();
