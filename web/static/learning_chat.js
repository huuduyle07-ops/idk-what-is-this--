(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const text = (id, value) => { byId(id).textContent = value; };
    const show = (id, visible) => { byId(id).hidden = !visible; };
    const state = { config: null, conversation: null, conversations: [], busy: false, loading: false,
        payload: null, createPayload: null, collections: [], materialsLoaded: false,
        navigation: 0, listRequest: 0, poll: null, pollStarted: 0, renderKey: null };
    const API = "/learn/api/chats";
    const node = (tag, value, className) => {
        const element = document.createElement(tag);
        if (value !== undefined && value !== null) element.textContent = value;
        if (className) element.className = className;
        return element;
    };
    const requestId = () => crypto.randomUUID();
    const draft = () => byId("chatInput").value.trim();
    const pending = () => !!(state.conversation && state.conversation.pending);
    const address = (conversation = state.conversation) => API + "/" + encodeURIComponent(conversation.id);
    const conceptMap = window.LearningConceptMap.create(byId("chatConceptMap"), {
        onAsk(question) {
            if (state.busy || state.loading || pending() || state.createPayload) return false;
            if (draft() || state.payload) { notice("Bản nháp đang có nội dung. Hãy gửi hoặc bỏ bản nháp trước khi hỏi về khái niệm khác.", !!state.payload); return false; }
            byId("chatInput").value = question; controls(); byId("chatInput").focus(); return true;
        },
        onNavigate: guardDraft,
    });
    function notice(message, retry = false) {
        text("chatNoticeText", message); show("chatNotice", !!message); show("retryChatButton", retry);
    }
    function controls() {
        const locked = state.busy || state.loading;
        byId("chatInput").disabled = locked || pending() || !state.config || !state.config.available || !!state.payload;
        byId("sendChatButton").disabled = locked || pending() || !!state.payload || !draft() || !state.config || !state.config.available;
        byId("newChatButton").disabled = locked || pending();
        byId("chatCollection").disabled = locked || pending() || !!state.payload || !!state.createPayload || !state.materialsLoaded;
        byId("chatCollectionStart").disabled = locked || pending() || !!state.payload;
        byId("deleteChatButton").disabled = locked || pending() || !state.conversation || !!state.payload || !!state.createPayload;
        byId("reloadChatButton").disabled = locked;
        byId("retryChatButton").disabled = locked || !state.payload;
        byId("discardChatDraftButton").disabled = locked || (!draft() && !state.payload);
        byId("confirmDeleteChatButton").disabled = locked || pending();
        byId("cancelDeleteChatButton").disabled = locked;
        byId("chatConversations").querySelectorAll("button").forEach((button) => { button.disabled = locked || pending() || !!state.createPayload; });
        document.querySelectorAll("[data-prompt]").forEach((button) => { button.disabled = locked || pending() || !!state.payload; });
        byId("chatMessages").setAttribute("aria-busy", String(state.busy || pending()));
        text("chatInputCount", byId("chatInput").value.length.toLocaleString("vi-VN") + " / 8.000");
        renderScope();
        conceptMap.setCollection(state.conversation?.collection || null);
        conceptMap.setBlocked(locked || pending() || !!state.payload || !!state.createPayload);
    }
    function renderScope() {
        const collection = state.conversation?.collection;
        text("chatScopeBadge", collection ? "Bài giảng · " + collection.title : "Kiến thức chung");
        if (state.createPayload) text("chatScopeHelp", "Chưa xác nhận được việc mở hội thoại. Lựa chọn nguồn được giữ nguyên cho lần thử lại.");
        else if (state.conversation) text("chatScopeHelp", collection
            ? "Hội thoại này dùng bộ “" + collection.title + "”. Đổi nguồn bằng cách mở hội thoại mới ở trên. Bản trích xuất có thể thiếu nội dung; hãy đối chiếu các đoạn nguồn."
            : "Hội thoại này dùng kiến thức chung. Chọn bài giảng rồi mở hội thoại mới ở trên để học theo tài liệu.");
        else text("chatScopeHelp", byId("chatCollection").value
            ? "Câu hỏi đầu tiên sẽ mở hội thoại theo bộ bài giảng đã chọn. Các đoạn liên quan được gửi cùng câu hỏi tới model đang hiển thị."
            : "Chọn bài giảng để hỏi về nội dung đã lưu, hoặc bắt đầu bằng kiến thức chung.");
    }
    async function loadCollections() {
        const selected = byId("chatCollection").value;
        try {
            const result = await api("/learn/api/materials");
            state.collections = (result.collections || []).filter((item) => item && typeof item.id === "string" && typeof item.title === "string");
            const general = node("option", "Kiến thức chung"); general.value = "";
            byId("chatCollection").replaceChildren(general, ...state.collections.map((collection) => {
                const option = node("option", collection.title); option.value = collection.id; return option;
            }));
            if (state.collections.some((collection) => collection.id === selected)) byId("chatCollection").value = selected;
            state.materialsLoaded = true;
            text("chatCollectionHelp", state.collections.length
                ? "Chỉ tìm trong bộ đã chọn. Ảnh chỉ được dùng qua ghi chú bạn đã viết; chưa tự đọc nội dung ảnh."
                : "Chưa có bộ bài giảng. Mở Tài liệu của tôi để nhập PDF, PowerPoint hoặc Word; bạn vẫn có thể chat kiến thức chung.");
        } catch (_) {
            text("chatCollectionHelp", "Chưa đọc được kho bài giảng. Nhấn Đọc bản đã lưu để thử lại; chat kiến thức chung vẫn dùng được.");
        }
        controls();
    }
    function guardDraft() {
        if (state.busy || state.loading || pending()) { notice("Hãy đợi lượt trò chuyện hiện tại hoàn tất trước khi chuyển hội thoại."); return false; }
        if (draft() || state.payload) {
            notice("Bạn còn bản nháp hoặc lượt gửi chưa xác nhận. Hãy gửi, thử lại đúng lượt gửi, hoặc bỏ bản nháp trước khi chuyển hội thoại.", !!state.payload);
            (state.payload ? byId("retryChatButton") : byId("chatInput")).focus(); return false;
        }
        return true;
    }
    async function api(url, options = {}) {
        const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 90000);
        try {
            const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options, signal: controller.signal });
            let data;
            try { data = await response.json(); }
            catch (_) { const error = new Error("Chưa đọc được phản hồi. Hãy đọc bản đã lưu hoặc thử lại."); error.ambiguous = true; throw error; }
            if (!response.ok || !data.ok) {
                const error = new Error(data.error || "Chưa thực hiện được thao tác.");
                error.code = data.error_code; error.status = response.status; error.ambiguous = response.status >= 500; throw error;
            }
            return data;
        } catch (error) {
            if (!error.status) error.ambiguous = true;
            throw error;
        } finally { clearTimeout(timeout); }
    }
    const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    function checkedConversation(value) {
        if (!value || typeof value.id !== "string" || !Number.isInteger(value.revision) || !Array.isArray(value.messages)
                || value.messages.some((message) => !message || !["user", "assistant"].includes(message.role) || typeof message.content !== "string")) {
            const error = new Error("Phản hồi hội thoại chưa hợp lệ. Hãy đọc bản đã lưu."); error.ambiguous = true; throw error;
        }
        return value;
    }
    function displayTime(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
    }
    // Model output is a small text-only Markdown vocabulary, never HTML,
    // executable code, remote media, or an application action.
    function inline(parent, value) {
        String(value).split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g).forEach((part) => {
            if (part.startsWith("`") && part.endsWith("`") && part.length > 2) parent.append(node("code", part.slice(1, -1)));
            else if (part.startsWith("**") && part.endsWith("**") && part.length > 4) parent.append(node("strong", part.slice(2, -2)));
            else parent.append(document.createTextNode(part));
        });
    }
    function tableCells(line) { return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim()); }
    function tableStart(lines, index) {
        if (index + 1 >= lines.length || !lines[index].includes("|")) return false;
        const separator = tableCells(lines[index + 1]); const header = tableCells(lines[index]);
        return header.length >= 2 && header.length <= 12 && separator.length === header.length && separator.every((cell) => /^:?-{3,}:?$/.test(cell));
    }
    function markdown(parent, content) {
        const lines = content.replace(/\r\n?/g, "\n").split("\n"); let index = 0;
        while (index < lines.length) {
            const line = lines[index];
            if (!line.trim()) { index += 1; continue; }
            const fence = line.match(/^\s*```([^`]*)$/);
            if (fence) {
                const codeLines = []; index += 1;
                while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) codeLines.push(lines[index++]);
                if (index < lines.length) index += 1;
                const code = codeLines.join("\n"); const box = node("div", null, "chat-code");
                const toolbar = node("div", null, "chat-code-toolbar"); toolbar.append(node("span", fence[1].trim().slice(0, 40) || "Code"));
                const copy = node("button", "Sao chép code", "copy-code"); copy.type = "button";
                copy.addEventListener("click", async () => {
                    try { await navigator.clipboard.writeText(code); copy.textContent = "Đã sao chép"; }
                    catch (_) { notice("Trình duyệt chưa cho sao chép tự động. Bạn có thể chọn phần code để sao chép."); }
                });
                toolbar.append(copy); const pre = node("pre"); pre.tabIndex = 0; pre.setAttribute("aria-label", "Ví dụ code, chỉ đọc"); pre.append(node("code", code)); box.append(toolbar, pre); parent.append(box); continue;
            }
            if (tableStart(lines, index)) {
                const headers = tableCells(lines[index]); const wrapper = node("div", null, "chat-table-wrap"); wrapper.tabIndex = 0; wrapper.setAttribute("role", "region"); wrapper.setAttribute("aria-label", "Bảng so sánh, cuộn ngang nếu cần");
                const table = node("table"); const head = node("thead"); const headRow = node("tr");
                headers.forEach((label) => { const cell = node("th"); cell.scope = "col"; inline(cell, label); headRow.append(cell); }); head.append(headRow); table.append(head);
                const body = node("tbody"); index += 2;
                while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
                    const cells = tableCells(lines[index]); if (cells.length !== headers.length) break;
                    const row = node("tr"); cells.forEach((value) => { const cell = node("td"); inline(cell, value); row.append(cell); }); body.append(row); index += 1;
                }
                table.append(body); wrapper.append(table); parent.append(wrapper); continue;
            }
            const heading = line.match(/^(#{1,4})\s+(.+)$/);
            if (heading) { const element = node("h" + Math.min(heading[1].length + 1, 4)); inline(element, heading[2]); parent.append(element); index += 1; continue; }
            const bullet = line.match(/^\s*(?:([-*])|\d+[.)])\s+(.+)$/);
            if (bullet) {
                const ordered = !bullet[1]; const list = node(ordered ? "ol" : "ul");
                while (index < lines.length) {
                    const item = lines[index].match(/^\s*(?:([-*])|\d+[.)])\s+(.+)$/);
                    if (!item || (!item[1]) !== ordered) break;
                    const element = node("li"); inline(element, item[2]); list.append(element); index += 1;
                }
                parent.append(list); continue;
            }
            const paragraph = [line]; index += 1;
            while (index < lines.length && lines[index].trim() && !/^\s*```/.test(lines[index]) && !/^#{1,4}\s/.test(lines[index]) && !/^\s*(?:[-*]|\d+[.)])\s/.test(lines[index]) && !tableStart(lines, index)) paragraph.push(lines[index++]);
            const element = node("p"); inline(element, paragraph.join("\n")); parent.append(element);
        }
    }
    function renderMessages(scroll = false) {
        const conversation = state.conversation;
        const key = conversation ? conversation.id + ":" + conversation.revision + ":" + JSON.stringify(conversation.pending) + ":" + JSON.stringify(conversation.last_error) : "empty";
        show("chatWelcome", !conversation || !conversation.messages.length);
        show("chatFollowups", !!conversation && conversation.messages.some((message) => message.role === "assistant") && !pending());
        text("chatTitle", conversation && conversation.messages.length ? conversation.title : "Cùng làm rõ một điều.");
        if (key === state.renderKey) return;
        state.renderKey = key;
        byId("chatMessages").replaceChildren(...(conversation ? conversation.messages : []).map((message) => {
            const article = node("article", null, "chat-message"); article.dataset.role = message.role;
            const header = node("div", null, "chat-message-header"); header.append(node("strong", message.role === "user" ? "Bạn" : "C.A.T.T.U.S"));
            const time = node("time", displayTime(message.created_at)); if (typeof message.created_at === "string") time.dateTime = message.created_at; header.append(time);
            if (message.role === "assistant" && message.model) header.append(node("span", message.model));
            if (message.role === "user" && message.status === "failed") header.append(node("span", "Lượt này chưa nhận được câu trả lời"));
            const body = node("div", null, "chat-content");
            if (message.role === "assistant") markdown(body, message.content); else body.textContent = message.content;
            article.append(header, body);
            if (message.role === "assistant" && message.evidence) article.append(renderEvidence(message.evidence));
            return article;
        }));
        if (scroll) byId("chatMessages").lastElementChild?.scrollIntoView({ block: "start" });
    }
    function renderEvidence(evidence) {
        const panel = node("section", null, "chat-evidence"); panel.setAttribute("aria-label", "Nguồn cho câu trả lời");
        const sources = Array.isArray(evidence.sources) ? evidence.sources.filter((source) => source && typeof source.text === "string" && typeof source.citation_id === "string") : [];
        const cited = new Set(Array.isArray(evidence.cited_ids) ? evidence.cited_ids : []);
        const unknown = Array.isArray(evidence.invalid_citation_ids) ? evidence.invalid_citation_ids : [];
        panel.append(node("p", "Đối chiếu bài giảng", "evidence-heading"));
        if (evidence.status === "no_match" || !sources.length) {
            panel.append(node("p", "Chưa tìm thấy đoạn phù hợp trong bộ bài giảng cho lượt này. Không xem phần trả lời là đã được bài giảng xác nhận.", "evidence-note"));
            return panel;
        }
        panel.append(node("p", evidence.selection === "overview"
            ? "Bản tổng quan dựa trên một số đoạn được chọn, chưa bao quát toàn bộ tài liệu. Mở từng đoạn để đối chiếu."
            : "Các đoạn dưới đây đã được cung cấp cho AI, không phải toàn bộ bài giảng. Trích dẫn xác định đoạn nguồn, không tự xác nhận mọi nhận định là đúng.", "evidence-note"));
        if (evidence.selection === "concept_link") panel.append(node("p", "Các đoạn được chọn qua nhãn khái niệm bạn đã gắn. Liên kết này chưa xác minh rằng nguồn chứng minh mọi nhận định về khái niệm.", "evidence-note"));
        if (!sources.some((source) => cited.has(source.citation_id))) panel.append(node("p", "AI chưa chỉ rõ đoạn nào hỗ trợ câu trả lời. Bạn có thể mở các đoạn đã cung cấp để đối chiếu.", "evidence-note evidence-warning"));
        if (unknown.length) panel.append(node("p", "Câu trả lời có mã nguồn không hợp lệ. Những mã đó không liên kết tới tài liệu.", "evidence-note evidence-warning"));
        const kinds = { page: "Trang", slide: "Slide", paragraph: "Đoạn", table: "Bảng", image: "Ảnh" };
        sources.forEach((source) => {
            if (!source || typeof source.text !== "string" || typeof source.citation_id !== "string") return;
            const card = node("details", null, "chat-source-card");
            const summary = node("summary");
            const location = source.locator ? (kinds[source.locator.kind] || "Phần") + " " + source.locator.index : "Phần trích xuất";
            summary.append(node("span", "[" + source.citation_id + "] " + (source.title || "Tài liệu") + " · " + location, "source-card-title"));
            summary.append(node("span", cited.has(source.citation_id) ? "AI có trích dẫn" : "Đoạn đã cung cấp", "source-card-badge"));
            card.append(summary);
            const origin = source.origin === "user_note" ? "Ghi chú ảnh do bạn viết; không phải nội dung AI đọc từ ảnh." : "Văn bản trích xuất tự động; có thể cần đối chiếu bản gốc.";
            card.append(node("p", origin, "evidence-note"), node("blockquote", source.text, "source-excerpt"));
            if (source.origin === "user_note" && Number.isInteger(source.annotation_revision)) card.append(node("p", "Phiên bản ghi chú: " + source.annotation_revision, "evidence-note"));
            if (Array.isArray(source.warnings) && source.warnings.length) card.append(node("p", "Lưu ý trích xuất: " + source.warnings.join(" · "), "evidence-note"));
            panel.append(card);
        });
        return panel;
    }
    function renderList() {
        text("chatListEmpty", state.conversations.length ? "" : "Chưa có hội thoại. Bắt đầu bằng câu hỏi đầu tiên."); show("chatListEmpty", !state.conversations.length);
        byId("chatConversations").replaceChildren(...state.conversations.map((conversation) => {
            const item = node("li"); const button = node("button"); button.type = "button";
            button.setAttribute("aria-current", String(!!state.conversation && state.conversation.id === conversation.id));
            button.append(node("span", conversation.title), node("small", (conversation.collection ? conversation.collection.title + " · " : "") + displayTime(conversation.updated_at)));
            button.addEventListener("click", () => loadConversation(conversation.id)); item.append(button); return item;
        })); controls();
    }
    async function refreshList() {
        const sequence = ++state.listRequest;
        try { const result = await api(API); if (sequence === state.listRequest) { state.conversations = result.conversations || []; renderList(); } }
        catch (error) { if (sequence === state.listRequest) { notice(error.message); text("chatListEmpty", "Chưa đọc được hội thoại. Nhấn Đọc bản đã lưu để thử lại."); show("chatListEmpty", true); } }
    }
    function stopPolling() { if (state.poll) clearTimeout(state.poll); state.poll = null; }
    function status() {
        if (state.busy) text("chatStatus", "Đang gửi và chờ AI trả lời…");
        else if (pending()) text("chatStatus", "Tin nhắn đã lưu. AI đang trả lời; bạn có thể đọc lại kết quả sau.");
        else if (state.conversation && state.conversation.last_error) text("chatStatus", "Lượt vừa rồi chưa có câu trả lời. Bạn có thể viết và gửi một lượt mới.");
        else text("chatStatus", state.conversation && state.conversation.messages.length ? "Hội thoại đã được lưu. Bạn muốn làm rõ thêm điều gì?" : "Bạn chọn nhịp trò chuyện.");
    }
    function adopt(value, scroll = false) {
        state.conversation = checkedConversation(value); renderMessages(scroll); renderList(); status(); controls();
        if (pending()) schedulePoll(); else { stopPolling(); state.pollStarted = 0; }
    }
    function schedulePoll() {
        stopPolling();
        if (!pending() || state.busy) return;
        if (!state.pollStarted) state.pollStarted = Date.now();
        if (Date.now() - state.pollStarted > 150000) { text("chatStatus", "Chưa xác nhận được kết quả. Nhấn Đọc bản đã lưu để kiểm tra lại."); return; }
        const id = state.conversation.id; const navigation = state.navigation;
        state.poll = setTimeout(async () => {
            try {
                const result = await api(API + "/" + encodeURIComponent(id));
                if (navigation !== state.navigation || state.conversation?.id !== id) return;
                adopt(result.conversation, !result.conversation.pending);
            } catch (_) { if (navigation === state.navigation && state.conversation?.id === id) { text("chatStatus", "Chưa đọc được kết quả; đang chờ để kiểm tra lại."); schedulePoll(); } }
        }, 2000);
    }
    async function loadConversation(id, force = false) {
        if (!force && !guardDraft()) return;
        stopPolling(); const sequence = ++state.navigation; state.loading = true; show("deleteChatConfirm", false); controls();
        try {
            const result = await api(API + "/" + encodeURIComponent(id));
            if (sequence !== state.navigation) return;
            adopt(result.conversation, true);
        } catch (error) { if (sequence === state.navigation) notice(error.message, !!state.payload); }
        finally { if (sequence === state.navigation) { state.loading = false; controls(); schedulePoll(); } }
    }
    async function createConversation() {
        if (!state.createPayload) {
            state.createPayload = { request_id: requestId() };
            if (byId("chatCollection").value) state.createPayload.collection_id = byId("chatCollection").value;
        }
        let result;
        try { result = await api(API, json("POST", state.createPayload)); }
        catch (error) {
            if (error.status && error.status < 500) state.createPayload = null;
            throw error;
        }
        state.createPayload = null; state.navigation += 1; state.pollStarted = 0; adopt(result.conversation); await refreshList();
        return state.conversation;
    }
    async function newConversation() {
        if (!guardDraft()) return;
        state.busy = true; notice(""); show("deleteChatConfirm", false); controls();
        try { await createConversation(); }
        catch (error) { notice(error.message || "Chưa mở được hội thoại. Hãy thử lại."); }
        finally { state.busy = false; status(); controls(); byId("chatInput").focus(); }
    }
    async function submit(retry = false) {
        if (state.busy || state.loading || !state.config?.available) return;
        if (!retry && (pending() || state.payload || !draft())) return;
        if (retry && !state.payload) return;
        state.busy = true; stopPolling(); notice(""); show("deleteChatConfirm", false); status(); controls();
        try {
            if (!state.conversation || state.createPayload) await createConversation();
            if (!state.payload) state.payload = { request_id: requestId(), text: byId("chatInput").value, expected_revision: state.conversation.revision };
            const submitted = state.payload;
            const result = await api(address() + "/messages", json("POST", submitted));
            const conversation = checkedConversation(result.conversation);
            const failed = conversation.last_error?.request_id === submitted.request_id;
            if (!failed && byId("chatInput").value === submitted.text) byId("chatInput").value = "";
            state.payload = null; adopt(conversation, true); await refreshList();
            if (failed) notice("Lượt gửi đã được ghi nhận nhưng AI chưa trả lời được. Bản nháp vẫn được giữ; bạn có thể gửi một lượt mới khi sẵn sàng.");
        } catch (error) {
            if (error.status === 409) {
                state.payload = null;
                notice("Hội thoại đã thay đổi ở lượt khác. Bản nháp vẫn được giữ. Hãy đọc bản mới dưới đây rồi gửi lại nếu muốn.");
                if (state.conversation) await loadConversation(state.conversation.id, true);
            } else if (error.code === "chat_provider_error") {
                state.payload = null;
                notice("Lượt AI vừa rồi không trả lời được. Câu hỏi đã lưu và bản nháp vẫn được giữ. Bạn có thể gửi lại thành một lượt mới.");
                if (state.conversation) await loadConversation(state.conversation.id, true);
            } else if (error.code === "chat_not_configured") {
                state.payload = null; notice(error.message); await loadConfig();
            } else if (error.ambiguous && state.payload) {
                notice("Chưa nhận được xác nhận cho lượt gửi. Bản nháp vẫn được giữ. Thử lại đúng lượt gửi sẽ đọc kết quả đã lưu nếu lượt đó đã được xử lý.", true);
            } else { state.payload = null; notice(error.message || "Chưa gửi được tin nhắn. Bản nháp vẫn được giữ."); }
        } finally { state.busy = false; status(); controls(); schedulePoll(); }
    }
    async function reload() {
        if (state.busy || state.loading) return;
        await loadConfig();
        await loadCollections();
        if (state.conversation) await loadConversation(state.conversation.id, true);
        await refreshList();
        if (state.payload) notice("Đã đọc bản hiện có. Nhấn Thử lại đúng lượt gửi để xác nhận lượt chưa nhận phản hồi; bản nháp vẫn được giữ.", true);
    }
    async function deleteConversation() {
        if (!state.conversation || state.busy || pending() || !guardDraft()) return;
        state.busy = true; controls(); const target = state.conversation;
        try {
            await api(address(target), { method: "DELETE" });
            stopPolling(); state.navigation += 1; state.conversation = null; state.renderKey = null; state.pollStarted = 0;
            renderMessages(); show("deleteChatConfirm", false); notice("Đã xóa hội thoại khỏi C.A.T.T.U.S."); await refreshList();
        } catch (error) { notice(error.message || "Chưa xác nhận được việc xóa. Hãy đọc bản đã lưu trước khi thử lại."); }
        finally { state.busy = false; status(); controls(); }
    }
    byId("chatForm").addEventListener("submit", (event) => { event.preventDefault(); submit(); });
    byId("chatInput").addEventListener("input", controls);
    byId("chatInput").addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); if (!byId("sendChatButton").disabled) submit(); }
    });
    byId("newChatButton").addEventListener("click", newConversation);
    byId("chatCollectionStart").addEventListener("click", newConversation);
    byId("chatCollection").addEventListener("change", renderScope);
    byId("retryChatButton").addEventListener("click", () => submit(true));
    byId("reloadChatButton").addEventListener("click", reload);
    byId("discardChatDraftButton").addEventListener("click", () => {
        if (state.busy || state.loading) return;
        byId("chatInput").value = ""; state.payload = null;
        notice("Đã bỏ bản nháp trên màn hình. Tin nhắn đã lưu và lượt AI đã gửi vẫn có thể còn trong hội thoại."); controls();
        if (state.conversation) loadConversation(state.conversation.id, true);
    });
    byId("deleteChatButton").addEventListener("click", () => {
        if (!state.conversation || !guardDraft()) return;
        text("deleteChatText", 'Xóa toàn bộ tin nhắn trong “' + state.conversation.title + '” khỏi C.A.T.T.U.S? Thao tác này không xóa bài giảng hoặc bài thực hành Java.');
        show("deleteChatConfirm", true); byId("confirmDeleteChatButton").focus();
    });
    byId("confirmDeleteChatButton").addEventListener("click", deleteConversation);
    byId("cancelDeleteChatButton").addEventListener("click", () => show("deleteChatConfirm", false));
    document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
        if (draft() || state.payload) { notice("Bản nháp đang có nội dung. Hãy gửi hoặc bỏ bản nháp trước khi chọn gợi ý khác.", !!state.payload); return; }
        byId("chatInput").value = button.dataset.prompt; controls(); byId("chatInput").focus();
    }));
    document.querySelectorAll("a[href]").forEach((link) => link.addEventListener("click", (event) => { if (!guardDraft()) event.preventDefault(); }));
    window.addEventListener("beforeunload", (event) => { if (draft() || state.payload || state.busy) { event.preventDefault(); event.returnValue = ""; } });
    async function loadConfig() {
        try {
            const result = await api("/learn/api/chat/config"); state.config = result.config;
            const config = state.config;
            text("configStatus", config.available ? config.provider + " · " + config.model : (config.reason || "AI chưa được cấu hình."));
            if (!config.available) notice(config.reason || "Chưa có model sẵn sàng. Cấu hình AI trên máy chủ để bắt đầu trò chuyện.");
        } catch (error) { text("configStatus", "Chưa đọc được cấu hình AI."); notice(error.message); }
        controls();
    }
    async function boot() {
        state.loading = true;
        controls();
        await loadConfig();
        await loadCollections();
        await refreshList();
        if (state.conversations.length && !state.conversation) await loadConversation(state.conversations[0].id, true);
        state.loading = false;
        controls();
    }
    boot();
})();
