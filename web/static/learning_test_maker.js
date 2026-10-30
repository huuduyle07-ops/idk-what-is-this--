/* Authored, seeded test templates. No model or lecture retrieval is used here. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const text = (id, value) => { byId(id).textContent = value; };
    const show = (id, visible) => { byId(id).hidden = !visible; };
    const make = (tag, value, className) => { const item = document.createElement(tag); if (value != null) item.textContent = String(value); if (className) item.className = className; return item; };
    const API = "/learn/api/test-maker";
    const clone = (value) => JSON.parse(JSON.stringify(value));
    const normalized = (value) => Array.isArray(value) ? value.map(normalized) : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map((key) => [key, normalized(value[key])])) : value;
    const equal = (a, b) => JSON.stringify(normalized(a)) === JSON.stringify(normalized(b));
    const state = { catalog: [], selected: new Set(), history: [], test: null, index: 0, answers: {}, busy: false,
        pendingCreate: null, pendingAction: null, pendingDelete: false, conflict: false, latest: null, historySequence: 0, navigation: 0 };
    const kindNames = { numeric: "Numeric", matrix: "Matrix", diagram: "Diagram", essay: "Essay" };
    const dirty = () => !!state.test && state.test.status === "active" && !equal(state.answers, state.test.answers || {});
    const address = () => API + "/" + encodeURIComponent(state.test.id);
    function button(label, action, className = "text-button") { const item = make("button", label, className); item.type = "button"; item.addEventListener("click", action); return item; }
    function notice(message) { text("testNoticeText", message); show("testNotice", !!message); controls(); }
    function meaningful(value) { if (typeof value === "string") return !!value.trim(); if (Array.isArray(value)) return value.some(meaningful); if (value && typeof value === "object") return Object.values(value).some(meaningful); return value !== undefined && value !== null; }
    function guard() {
        if (state.busy) { notice("Đang xử lý đề. Hãy đợi thao tác hoàn tất."); return false; }
        if (state.pendingCreate || state.pendingAction || state.pendingDelete || state.conflict || state.latest) { notice("Kết quả yêu cầu trước chưa rõ. Kiểm tra đúng yêu cầu hoặc đọc bản đã lưu trước khi chuyển đề."); return false; }
        if (dirty()) { notice("Bài đang viết chưa được lưu. Hãy Save draft hoặc Bỏ bản nháp trước khi chuyển đề."); return false; }
        return true;
    }
    function controls() {
        const locked = state.busy || !!state.pendingCreate || !!state.pendingAction || state.pendingDelete || state.conflict || !!state.latest;
        byId("testSeed").disabled = locked;
        ["randomizeTestSeed", "selectAllTestTopics", "clearTestTopics"].forEach((id) => { byId(id).disabled = locked; });
        byId("testTopics").querySelectorAll("input").forEach((input) => { input.disabled = locked; });
        const seed = Number(byId("testSeed").value);
        byId("createTestButton").disabled = locked || !state.selected.size || !Number.isInteger(seed) || seed < 0 || seed > 2147483647 || !byId("testSeed").value.trim();
        byId("newTestButton").disabled = state.busy;
        byId("refreshTestHistory").disabled = state.busy;
        byId("testHistory").querySelectorAll("button").forEach((item) => { item.disabled = state.busy; });
        byId("testQuestionNav").querySelectorAll("button").forEach((item) => { item.disabled = locked; });
        byId("testContent").querySelectorAll("input,textarea").forEach((input) => { input.disabled = locked || state.test?.status !== "active"; });
        byId("testContent").querySelectorAll("button").forEach((item) => { item.disabled = locked || item.dataset.disabled === "true"; });
        byId("saveTestDraft").disabled = locked || state.test?.status !== "active" || !dirty();
        byId("discardTestDraft").disabled = locked || !dirty();
        byId("reviewTestSubmit").disabled = locked || state.test?.status !== "active";
        byId("confirmTestSubmit").disabled = locked || state.test?.status !== "active";
        byId("cancelTestSubmit").disabled = state.busy;
        byId("deleteTestButton").disabled = locked;
        byId("confirmTestDelete").disabled = locked;
        byId("cancelTestDelete").disabled = state.busy || state.pendingDelete;
        byId("useSavedTest").disabled = state.busy || !state.latest;
        byId("keepDraftTest").disabled = state.busy || !state.latest || state.latest.status !== "active";
        show("retryTestRequest", !!state.pendingCreate || (!!state.pendingAction && !state.conflict));
        byId("retryTestRequest").disabled = state.busy;
        show("reloadTestButton", !!state.test); byId("reloadTestButton").disabled = state.busy;
        byId("testCreateForm").setAttribute("aria-busy", String(state.busy && !!state.pendingCreate));
        byId("testSession").setAttribute("aria-busy", String(state.busy));
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
    function checked(test) {
        if (!test || typeof test.id !== "string" || !Number.isSafeInteger(test.revision) || !["active", "submitted"].includes(test.status) || !Array.isArray(test.questions) || !test.answers || typeof test.answers !== "object") { const error = new Error("Phản hồi đề chưa hợp lệ."); error.ambiguous = true; throw error; }
        return test;
    }
    function renderHistory() {
        byId("testHistory").replaceChildren(...state.history.map((test) => {
            const row = make("li"), open = button(test.title || "Test", () => openTest(test.id)); open.dataset.testId = test.id; open.setAttribute("aria-current", String(state.test?.id === test.id));
            open.append(make("small", (test.status === "submitted" ? "Đã nộp" : "Đang làm") + " · seed " + test.seed)); row.append(open); return row;
        }));
        text("testHistoryStatus", state.history.length ? "Bài đã lưu có thể mở lại trong trình duyệt này." : "Chưa có đề. Chọn chủ đề để bắt đầu."); controls();
    }
    async function history() {
        const request = ++state.historySequence;
        try { const result = await api(API); if (request !== state.historySequence) return; state.history = result.tests || []; renderHistory(); }
        catch (_) { if (request === state.historySequence) text("testHistoryStatus", "Chưa đọc được lịch sử. Chọn Đọc lại để thử tiếp."); }
    }
    function renderCatalog() {
        const groups = new Map();
        state.catalog.forEach((topic) => { if (!groups.has(topic.subject)) groups.set(topic.subject, []); groups.get(topic.subject).push(topic); });
        byId("testTopics").replaceChildren(...Array.from(groups, ([subject, topics]) => {
            const group = make("fieldset", null, "tm-topic-group"); group.append(make("legend", subject));
            topics.forEach((topic) => {
                const label = make("label", null, "tm-topic"), input = document.createElement("input"), body = make("span", topic.title);
                input.type = "checkbox"; input.value = topic.id; input.checked = state.selected.has(topic.id);
                input.addEventListener("change", () => { if (input.checked) state.selected.add(topic.id); else state.selected.delete(topic.id); catalogStatus(); controls(); });
                body.append(make("small", (kindNames[topic.kind] || topic.kind) + " · " + topic.points + " points · " + topic.description)); label.append(input, body); group.append(label);
            });
            return group;
        })); catalogStatus(); controls();
    }
    function catalogStatus() { text("testCatalogStatus", state.selected.size + " / " + state.catalog.length + " chủ đề đã chọn. Cùng chủ đề và seed sẽ tái tạo cùng dữ liệu."); }
    function tableView(data) {
        const scroll = make("div", null, "tm-table-scroll"), table = make("table", null, "tm-table");
        if (data.title) table.append(make("caption", data.title));
        if (Array.isArray(data.headers) && data.headers.length) { const head = make("thead"), row = make("tr"); data.headers.forEach((value) => row.append(make("th", value))); head.append(row); table.append(head); }
        const body = make("tbody"); (data.rows || []).forEach((values) => { const row = make("tr"); (Array.isArray(values) ? values : [values]).forEach((value) => row.append(make("td", value))); body.append(row); }); table.append(body); scroll.append(table); return scroll;
    }
    function renderData(question, box) {
        (question.data?.tables || []).forEach((table) => box.append(tableView(table)));
        if (Array.isArray(question.data?.lines) && question.data.lines.length) box.append(make("p", question.data.lines.join("\n"), "tm-data-lines"));
    }
    function references(question, box) {
        if (!question.references?.length) return;
        const links = make("details", null, "tm-references"); links.append(make("summary", "Template references"));
        question.references.forEach((reference) => {
            const href = typeof reference === "string" ? reference : reference.url, title = typeof reference === "string" ? reference : reference.title || reference.label || reference.url;
            try { const url = new URL(href); if (!["https:", "http:"].includes(url.protocol)) return; const link = make("a", title); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; links.append(link); } catch (_) { /* No arbitrary source URL schemes. */ }
        }); box.append(links);
    }
    function answerChanged(questionId, answer) { state.answers[questionId] = answer; text("testStatus", dirty() ? "Bài đang viết chưa lưu. Save draft để giữ bài trên máy chủ." : "Đang dùng bài đã lưu."); renderQuestionNav(); controls(); }
    function numberInput(question, box) {
        const label = make("label", "Your answer", "tm-input-label"), input = document.createElement("input"); input.type = "text"; input.className = "tm-number-input"; input.id = "testAnswerInput"; input.maxLength = 100; input.inputMode = question.input?.format === "address" ? "text" : "decimal"; input.placeholder = question.input?.placeholder || "Enter your answer"; input.value = state.answers[question.id] || "";
        input.addEventListener("input", () => answerChanged(question.id, input.value)); label.append(input); box.append(label);
        if (question.input?.allow_percent) box.append(make("p", "A decimal or percentage is accepted.", "tm-help"));
    }
    function matrixInput(question, box) {
        const rows = question.input.rows, cols = question.input.cols, saved = state.answers[question.id] || [];
        const scroll = make("div", null, "tm-matrix-scroll"), table = make("table", null, "tm-matrix"), body = make("tbody"); table.setAttribute("aria-label", "Your answer matrix");
        const inputs = [];
        for (let rowIndex = 0; rowIndex < rows; rowIndex += 1) {
            const row = make("tr"); inputs[rowIndex] = [];
            for (let colIndex = 0; colIndex < cols; colIndex += 1) { const cell = make("td"), input = document.createElement("input"); input.type = "text"; input.inputMode = "decimal"; input.maxLength = 100; input.setAttribute("aria-label", "Row " + (rowIndex + 1) + ", column " + (colIndex + 1)); input.value = saved[rowIndex]?.[colIndex] || ""; input.dataset.row = rowIndex; input.dataset.col = colIndex; input.addEventListener("input", () => answerChanged(question.id, inputs.map((rowInputs) => rowInputs.map((item) => item.value)))); inputs[rowIndex][colIndex] = input; cell.append(input); row.append(cell); }
            body.append(row);
        }
        table.append(body); scroll.append(table); box.append(make("p", "Enter each cell of your result matrix.", "tm-help"), scroll);
    }
    function essayInput(question, box) {
        const label = make("label", "Your explanation", "tm-input-label"); label.htmlFor = "testEssayInput";
        const input = make("textarea", null, "tm-essay-input"), count = make("p", null, "tm-help"); input.id = "testEssayInput"; input.maxLength = question.input?.max_length || 4000; input.rows = 8; input.value = state.answers[question.id] || ""; input.placeholder = "State your reasoning and give a concrete example when useful.";
        count.textContent = input.value.length + " / " + input.maxLength + " characters · pending human review after submission";
        input.addEventListener("input", () => { answerChanged(question.id, input.value); count.textContent = input.value.length + " / " + input.maxLength + " characters · pending human review after submission"; }); box.append(label, input, count);
    }
    function diagramInput(question, box) {
        const diagram = question.data.diagram || question.data, width = Number(diagram.width) || 900, height = Number(diagram.height) || 400;
        const scroll = make("div", null, "tm-diagram-scroll"); scroll.tabIndex = 0; scroll.setAttribute("role", "region"); scroll.setAttribute("aria-label", "Editable diagram. Scroll horizontally to see all nodes.");
        const canvas = make("div", null, "tm-diagram-canvas"); canvas.style.width = width + "px"; canvas.style.height = height + "px";
        const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg"); svg.setAttribute("viewBox", "0 0 " + width + " " + height); svg.setAttribute("width", width); svg.setAttribute("height", height); svg.setAttribute("aria-hidden", "true");
        const defs = document.createElementNS(ns, "defs"), marker = document.createElementNS(ns, "marker"), arrow = document.createElementNS(ns, "path"); marker.id = "testDiagramArrow"; marker.setAttribute("viewBox", "0 0 10 10"); marker.setAttribute("refX", "9"); marker.setAttribute("refY", "5"); marker.setAttribute("markerWidth", "7"); marker.setAttribute("markerHeight", "7"); marker.setAttribute("orient", "auto-start-reverse"); arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z"); arrow.setAttribute("fill", "#52735c"); marker.append(arrow); defs.append(marker); svg.append(defs);
        const nodes = new Map(diagram.nodes.map((node) => [node.id, node]));
        diagram.edges.forEach((edge) => {
            const from = nodes.get(edge.from), to = nodes.get(edge.to); if (!from || !to) return;
            const a = { x: from.x + from.width / 2, y: from.y + from.height / 2 }, b = { x: to.x + to.width / 2, y: to.y + to.height / 2 };
            const horizontal = Math.abs(b.x - a.x) >= Math.abs(b.y - a.y);
            if (horizontal) { a.x += (b.x >= a.x ? 1 : -1) * from.width / 2; b.x -= (b.x >= a.x ? 1 : -1) * to.width / 2; } else { a.y += (b.y >= a.y ? 1 : -1) * from.height / 2; b.y -= (b.y >= a.y ? 1 : -1) * to.height / 2; }
            const line = document.createElementNS(ns, "line"); line.setAttribute("x1", a.x); line.setAttribute("y1", a.y); line.setAttribute("x2", b.x); line.setAttribute("y2", b.y); line.setAttribute("class", "tm-diagram-edge"); line.setAttribute("marker-end", "url(#testDiagramArrow)"); svg.append(line);
            if (edge.label) { const label = document.createElementNS(ns, "text"); label.setAttribute("x", (a.x + b.x) / 2); label.setAttribute("y", horizontal ? Math.min(from.y, to.y) - 10 : (a.y + b.y) / 2 - 9); label.setAttribute("text-anchor", "middle"); label.setAttribute("class", "tm-diagram-edge-label"); label.textContent = edge.label; svg.append(label); }
        });
        canvas.append(svg);
        const measure = document.createElement("canvas").getContext("2d"); measure.font = '14px "Segoe UI",Arial,sans-serif';
        diagram.nodes.forEach((node) => {
            const rect = document.createElementNS(ns, "rect"); ["x", "y", "width", "height"].forEach((key) => rect.setAttribute(key, node[key])); rect.setAttribute("rx", "9"); rect.setAttribute("class", "tm-diagram-node"); svg.append(rect);
            if (node.slot_id) {
                const slot = question.input.slots.find((item) => item.id === node.slot_id), input = document.createElement("input"); input.type = "text"; input.maxLength = 120; input.className = "tm-diagram-input"; input.dataset.slotId = node.slot_id; input.setAttribute("aria-label", slot?.label || "Blank " + node.slot_id); input.placeholder = slot?.label || node.slot_id; input.value = state.answers[question.id]?.[node.slot_id] || "";
                input.style.left = (node.x + 8) + "px"; input.style.top = (node.y + 8) + "px"; input.style.width = (node.width - 16) + "px"; input.style.height = (node.height - 16) + "px";
                input.addEventListener("input", () => { const answer = {}; canvas.querySelectorAll("input[data-slot-id]").forEach((item) => { answer[item.dataset.slotId] = item.value; }); answerChanged(question.id, answer); }); canvas.append(input);
            } else {
                const lines = [];
                String(node.text || "").split("\n").forEach((paragraph) => { let line = ""; paragraph.split(/\s+/).forEach((word) => { const candidate = line ? line + " " + word : word; if (line && measure.measureText(candidate).width > node.width - 18) { lines.push(line); line = word; } else line = candidate; }); lines.push(line); });
                const label = document.createElementNS(ns, "text"); label.setAttribute("text-anchor", "middle"); label.setAttribute("class", "tm-diagram-text");
                lines.forEach((line, index) => { const span = document.createElementNS(ns, "tspan"); span.setAttribute("x", node.x + node.width / 2); span.setAttribute("y", node.y + node.height / 2 + (index - (lines.length - 1) / 2) * 18 + 5); span.textContent = line; label.append(span); }); svg.append(label);
            }
        }); scroll.append(canvas); box.append(make("p", "Type labels directly into the blank nodes. On a small screen, scroll inside the diagram.", "tm-help"), scroll);
    }
    function renderQuestionNav() {
        byId("testQuestionNav").replaceChildren(...(state.test?.questions || []).map((question, index) => {
            const item = button(String(index + 1) + (meaningful(state.answers[question.id]) ? " · entered" : ""), () => { state.index = index; renderQuestion(true); }); item.dataset.questionId = question.id; item.setAttribute("aria-current", String(index === state.index)); item.setAttribute("aria-label", "Question " + (index + 1) + ": " + question.title); return item;
        }));
    }
    function renderQuestion(focus = false) {
        const content = byId("testContent"), questions = state.test.questions, question = questions[state.index]; content.replaceChildren();
        if (!question) return;
        const box = make("article", null, "tm-question"); box.dataset.questionId = question.id; box.dataset.topicId = question.topic_id; box.dataset.kind = question.kind;
        box.append(make("p", "Question " + (state.index + 1) + " / " + questions.length + " · " + question.subject + " · " + (kindNames[question.kind] || question.kind) + " · " + question.points + " points", "tm-question-position"));
        const title = make("h3", question.title); title.id = "testQuestionTitle"; title.tabIndex = -1; box.append(title, make("p", question.prompt, "tm-prompt")); renderData(question, box);
        if (question.kind === "numeric") numberInput(question, box);
        else if (question.kind === "matrix") matrixInput(question, box);
        else if (question.kind === "diagram") diagramInput(question, box);
        else if (question.kind === "essay") essayInput(question, box);
        references(question, box);
        const nav = make("div", null, "tm-navigation"), previous = button("← Previous question", () => { if (state.index > 0) { state.index -= 1; renderQuestion(true); } }), next = button("Next question →", () => { if (state.index < questions.length - 1) { state.index += 1; renderQuestion(true); } });
        previous.disabled = state.index === 0; next.disabled = state.index === questions.length - 1; previous.dataset.disabled = String(previous.disabled); next.dataset.disabled = String(next.disabled); nav.append(previous, next); box.append(nav); content.append(box); renderQuestionNav(); controls(); if (focus) title.focus({ preventScroll: true });
    }
    function resultValue(value) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }
    function renderResults() {
        const content = byId("testContent"), results = state.test.results || {}, auto = results.auto || {}, essay = results.essay || {};
        content.replaceChildren();
        const summary = make("div", null, "tm-score"), autoScore = make("div", "Auto-graded questions"), essays = make("div", "Essays pending review"); autoScore.prepend(make("strong", (auto.earned ?? 0) + " / " + (auto.possible ?? 0))); essays.prepend(make("strong", essay.pending ?? 0)); summary.append(autoScore, essays); content.append(summary, make("p", results.message || "Compare the automatic result with the template answer. Essays need human review.", "tm-help"));
        (results.items || []).forEach((result) => {
            const question = state.test.questions.find((item) => item.id === result.question_id), essayQuestion = question?.kind === "essay", box = make("section", null, "tm-result"); box.dataset.questionId = result.question_id; box.dataset.status = result.status === "graded" ? (result.correct ? "correct" : "incorrect") : result.status;
            const resultLabel = essayQuestion ? (result.status === "unanswered" ? "NO ANSWER SUBMITTED · no automatic essay grade" : "PENDING HUMAN REVIEW · no automatic essay grade") : result.correct === true ? "MATCHES THE ANSWER KEY" : "REVIEW THIS ANSWER";
            box.append(make("p", resultLabel, "tm-question-position"), make("h3", question?.title || result.question_id));
            if (!essayQuestion && result.earned !== null && result.earned !== undefined) box.append(make("p", result.earned + " / " + result.possible + " points", "tm-help"));
            box.append(make("p", result.feedback || ""), make("h4", "Your submitted answer"), make("pre", meaningful(state.test.answers[result.question_id]) ? resultValue(state.test.answers[result.question_id]) : "No answer submitted"), make("h4", essayQuestion ? "Model answer for human comparison" : "Expected answer"));
            if (Array.isArray(result.expected) && result.expected.every(Array.isArray)) box.append(tableView({ rows: result.expected })); else if (result.expected && typeof result.expected === "object") { const values = make("dl"); Object.entries(result.expected).forEach(([key, value]) => values.append(make("dt", key), make("dd", value))); box.append(values); } else box.append(make("pre", resultValue(result.expected ?? "")));
            if (result.explanation) box.append(make("h4", "Explanation"), make("p", result.explanation));
            if (Array.isArray(result.rubric) && result.rubric.length) { const rubric = make("ul", null, "tm-rubric"); result.rubric.forEach((item) => rubric.append(make("li", typeof item === "string" ? item : item.description + " (" + item.points + " points)"))); box.append(make("h4", essayQuestion ? "Review rubric · not automatically assessed" : "Scoring criteria"), rubric); }
            if (question) references(question, box); content.append(box);
        });
    }
    function render() {
        show("testCreate", !state.test); show("testSession", !!state.test); show("testConflict", !!state.latest);
        if (state.test) {
            text("testSessionTitle", state.test.title || "Test"); text("testSessionState", state.test.status === "submitted" ? "ĐÃ NỘP · ĐỐI CHIẾU" : "ĐANG LÀM · ĐÁP ÁN CHƯA MỞ"); text("testMeta", "Seed " + state.test.seed + " · Version " + state.test.version + " · " + state.test.questions.length + " questions");
            show("testQuestionNav", state.test.status === "active"); show("testDraftActions", state.test.status === "active");
            if (state.test.status === "submitted") renderResults(); else renderQuestion();
        }
        renderHistory(); controls();
    }
    function adopt(value, preserveDraft = false) { const previousId = state.test?.id; state.test = checked(value); if (!preserveDraft) state.answers = clone(state.test.answers || {}); if (previousId !== state.test.id) state.index = 0; state.latest = null; state.conflict = false; show("testConflict", false); render(); }
    async function create() {
        if (state.busy) return;
        if (!state.pendingCreate) { const seed = Number(byId("testSeed").value); if (!state.selected.size || !Number.isInteger(seed) || seed < 0 || seed > 2147483647) return; state.pendingCreate = { request_id: crypto.randomUUID(), topic_ids: Array.from(state.selected), seed }; }
        state.busy = true; notice(""); controls(); text("testStatus", "Đang tạo đề từ mẫu đã chọn… Không gọi AI.");
        try { const result = await api(API, json("POST", state.pendingCreate)); checked(result.test); state.pendingCreate = null; adopt(result.test); byId("testQuestionTitle")?.focus({ preventScroll: true }); text("testStatus", "Đề đã lưu. Bạn có thể làm từng câu rồi Save draft hoặc Submit khi sẵn sàng."); history(); }
        catch (error) { if (!error.ambiguous) state.pendingCreate = null; notice(error.message + (state.pendingCreate ? " Kiểm tra lại đúng yêu cầu để tìm đề đã lưu." : " Hãy kiểm tra lựa chọn rồi thử lại.")); }
        finally { state.busy = false; controls(); }
    }
    async function act(name) {
        if (state.busy || !state.test || state.conflict || state.latest || state.pendingDelete) return;
        if (!state.pendingAction) state.pendingAction = { action: name, payload: { answers: clone(state.answers) }, expected_revision: state.test.revision, request_id: crypto.randomUUID() };
        const pending = state.pendingAction; state.busy = true; notice(""); controls();
        try {
            const result = await api(address() + "/actions", json("POST", pending)), latest = checked(result.test); state.pendingAction = null; show("testSubmitConfirm", false);
            if (!equal(pending.payload.answers, latest.answers || {})) { compareSaved(latest); history(); return; }
            adopt(latest); text("testStatus", state.test.status === "submitted" ? (pending.action === "submit" ? "Đã nộp bài. Xem phần chấm tự động và rubric tự luận bên dưới." : "Bài đã được nộp ở phiên khác. Đang mở kết quả đã lưu.") : "Đã lưu bản nháp.");
            if (state.test.status === "submitted") byId("testSessionTitle").focus({ preventScroll: true }); history();
        }
        catch (error) { if (error.status === 409) { state.conflict = true; show("testSubmitConfirm", false); notice(error.message + " Bản đang viết vẫn được giữ. Đọc bản đã lưu trước khi lưu hoặc nộp tiếp."); } else { if (!error.ambiguous) state.pendingAction = null; notice(error.message + (state.pendingAction ? " Chưa rõ kết quả; kiểm tra lại đúng yêu cầu hoặc đọc bản đã lưu." : " Bài đang viết vẫn được giữ.")); } }
        finally { state.busy = false; controls(); }
    }
    async function openTest(id) {
        if (!guard()) return;
        const request = ++state.navigation; state.busy = true; notice(""); controls();
        try { const result = await api(API + "/" + encodeURIComponent(id)); if (request === state.navigation) { adopt(result.test); text("testStatus", "Đã mở bài đã lưu."); byId("testSessionTitle").focus({ preventScroll: true }); } }
        catch (error) { notice(error.message); } finally { state.busy = false; controls(); }
    }
    function compareSaved(latest) {
        state.latest = latest; state.pendingAction = null; state.conflict = true;
        text("testDraftComparison", JSON.stringify(state.answers, null, 2)); text("testSavedComparison", JSON.stringify(latest.answers || {}, null, 2));
        text("testConflictHelp", latest.status === "submitted" ? "Bản trên máy chủ đã nộp. Bạn có thể xem lại bản đang viết ở đây rồi chọn Use saved answers để mở kết quả; không thể ghi đè bài đã nộp." : "Keep my draft giữ phần đang viết theo phiên bản mới, chưa ghi gì lên máy chủ.");
        show("testConflict", true); notice("Bản đã lưu khác với bản đang viết. Chọn bản muốn dùng; phần đang viết vẫn được giữ.");
    }
    async function reload() {
        if (state.busy || !state.test) return;
        const preserve = dirty() || !!state.pendingAction || state.conflict; state.busy = true; controls();
        try {
            const result = await api(address()), latest = checked(result.test); state.pendingDelete = false;
            if (preserve && !equal(state.answers, latest.answers || {})) compareSaved(latest);
            else { state.pendingAction = null; adopt(latest); notice(""); text("testStatus", "Đã đọc bản mới nhất."); history(); }
        } catch (error) { if (error.status === 404 && state.pendingDelete) { state.test = null; state.pendingDelete = false; show("testDeleteConfirm", false); notice(""); render(); history(); } else notice(error.message + " Bản đang viết vẫn được giữ."); }
        finally { state.busy = false; controls(); }
    }
    function reviewSubmit() {
        if (state.busy || state.pendingAction || state.conflict || !state.test || state.test.status !== "active") return;
        const entered = state.test.questions.filter((question) => meaningful(state.answers[question.id])).length;
        text("testSubmitSummary", entered + " / " + state.test.questions.length + " câu có nội dung đã nhập. Save draft lưu để làm tiếp; Submit mở đáp án và kết quả cho toàn bộ đề."); show("testSubmitConfirm", true); byId("testSubmitConfirmTitle").focus();
    }
    function newTest() { if (!guard()) return; state.test = null; state.answers = {}; state.index = 0; show("testDeleteConfirm", false); show("testSubmitConfirm", false); notice(""); render(); byId("testCreateTitle").scrollIntoView({ block: "start" }); }
    async function remove() {
        if (state.busy || !state.test || state.pendingAction || state.conflict || dirty()) return;
        state.busy = true; controls();
        try { await api(address(), { method: "DELETE" }); state.test = null; state.answers = {}; state.pendingDelete = false; show("testDeleteConfirm", false); notice(""); render(); history(); text("testStatus", "Đã xóa đề và bài làm."); }
        catch (error) { state.pendingDelete = !!error.ambiguous; notice(error.message + " Đọc bản đã lưu để xác định kết quả trước khi thao tác tiếp."); }
        finally { state.busy = false; controls(); }
    }
    byId("testCreateForm").addEventListener("submit", (event) => { event.preventDefault(); create(); });
    byId("testSeed").addEventListener("input", controls);
    byId("randomizeTestSeed").addEventListener("click", () => { const value = new Uint32Array(1); crypto.getRandomValues(value); byId("testSeed").value = value[0] & 0x7fffffff; controls(); });
    byId("selectAllTestTopics").addEventListener("click", () => { state.selected = new Set(state.catalog.map((topic) => topic.id)); renderCatalog(); });
    byId("clearTestTopics").addEventListener("click", () => { state.selected.clear(); renderCatalog(); });
    byId("refreshTestHistory").addEventListener("click", history); byId("newTestButton").addEventListener("click", newTest);
    byId("saveTestDraft").addEventListener("click", () => act("save"));
    byId("discardTestDraft").addEventListener("click", () => { if (state.busy || state.pendingAction || state.conflict || state.latest) return; state.answers = clone(state.test.answers || {}); render(); notice(""); text("testStatus", "Đã bỏ phần chưa lưu và dùng bài đã lưu."); });
    byId("reviewTestSubmit").addEventListener("click", reviewSubmit); byId("cancelTestSubmit").addEventListener("click", () => show("testSubmitConfirm", false)); byId("confirmTestSubmit").addEventListener("click", () => act("submit"));
    byId("retryTestRequest").addEventListener("click", () => { if (state.pendingCreate) create(); else if (state.pendingAction) act(); }); byId("reloadTestButton").addEventListener("click", reload);
    byId("useSavedTest").addEventListener("click", () => { if (!state.latest || state.busy) return; state.pendingAction = null; adopt(state.latest); notice(""); text("testStatus", "Đang dùng bài đã lưu; chưa gửi thay đổi mới."); });
    byId("keepDraftTest").addEventListener("click", () => { if (!state.latest || state.latest.status !== "active" || state.busy) return; const latest = state.latest; state.pendingAction = null; adopt(latest, true); notice(""); text("testStatus", "Đã giữ bản đang viết theo phiên bản mới. Save draft hoặc Submit khi muốn gửi."); });
    byId("deleteTestButton").addEventListener("click", () => { if (guard()) { show("testDeleteConfirm", true); byId("confirmTestDelete").focus(); } }); byId("confirmTestDelete").addEventListener("click", remove); byId("cancelTestDelete").addEventListener("click", () => show("testDeleteConfirm", false));
    window.addEventListener("beforeunload", (event) => { if (state.busy || dirty() || state.pendingCreate || state.pendingAction || state.pendingDelete || state.conflict || state.latest) { event.preventDefault(); event.returnValue = ""; } });
    async function boot() {
        controls();
        const results = await Promise.allSettled([api(API + "/catalog"), history()]);
        if (results[0].status === "fulfilled") { state.catalog = results[0].value.topics || []; state.selected = new Set(state.catalog.map((topic) => topic.id)); renderCatalog(); }
        else text("testCatalogStatus", "Chưa đọc được chủ đề. Tải lại trang để thử tiếp; bài cũ vẫn có thể mở.");
        controls();
    }
    boot();
})();
