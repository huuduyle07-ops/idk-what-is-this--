/* Lecture text stays source data. Importing does not activate a lesson. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const MAX_FILES = 10;
    const MAX_FILE_BYTES = 20 * 1024 * 1024;
    const MAX_TOTAL_BYTES = 64 * 1024 * 1024;
    const MAX_ENTRIES = 1000;
    const MAX_DEPTH = 12;
    const MAX_PREVIEW = 24000;
    const supported = /\.(pdf|pptx|docx|png|jpe?g)$/i;
    const state = { queue: [], ignored: 0, busy: false, scanning: false, pending: null,
        collections: [], collection: null, units: [], unitIndex: 0, titleEdited: false,
        detailRequest: 0, detailLoading: false, listBusy: false, collectionsVersion: 0,
        sourceIndex: 0, note: null, knowledge: null };
    let fileLabels = null, sourceVisuals = null;

    function text(id, value) { byId(id).textContent = String(value == null ? "" : value); }
    function show(id, visible) { byId(id).hidden = !visible; }
    function announce(value) { text("materialsAnnouncement", value); }
    function notice(value) { text("materialsNoticeText", value); show("materialsNotice", true); }
    function clearNotice() { show("materialsNotice", false); }
    function node(tag, value, className) {
        const element = document.createElement(tag);
        if (value != null) element.textContent = String(value);
        if (className) element.className = className;
        return element;
    }
    function bytesLabel(size) { return (size / 1024 / 1024).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + " MiB"; }
    function statusLabel(status) {
        if (status === "needs_visual_review") return "Cần xem lại hình";
        return status === "no_readable_text" ? "Chưa trích được chữ" : "Cần đối chiếu nguồn";
    }
    function noteDirty() { return !!state.note && byId("imageDescriptionInput").value !== state.note.baseText; }
    function noteBusy() { return !!state.note && (state.note.saving || state.note.loading); }
    function guardNote() {
        if (noteBusy()) { notice("Đang xử lý mô tả ảnh. Hãy đợi thao tác này hoàn tất."); return false; }
        if (noteDirty() || (state.note && (state.note.conflict || state.note.uncertain))) {
            notice("Mô tả ảnh còn thay đổi chưa được xác nhận. Hãy lưu hoặc chọn Bỏ thay đổi chưa lưu trước khi chuyển nguồn hay nhập bộ mới.");
            byId("imageDescriptionInput").focus(); return false;
        }
        return true;
    }
    function controls() {
        const otherBlocked = state.busy || state.scanning || state.detailLoading || noteBusy() || knowledgeBusy();
        const blocked = otherBlocked || !!fileLabels?.isBusy();
        fileLabels?.setBlocked(otherBlocked);
        ["chooseFilesButton", "chooseFolderButton", "materialsFilesInput", "materialsFolderInput", "materialsTitleInput"].forEach((id) => { byId(id).disabled = blocked; });
        byId("importMaterialsButton").disabled = blocked || !state.queue.length || !byId("materialsTitleInput").value.trim();
        byId("refreshMaterialsButton").disabled = state.listBusy || state.busy;
        byId("materialsDropzone").setAttribute("aria-busy", String(blocked));
        byId("materialsImportForm").setAttribute("aria-busy", String(state.busy));
        byId("selectedFiles").querySelectorAll("button").forEach((button) => { button.disabled = blocked; });
        byId("materialSourceSelect").disabled = blocked;
        byId("materialsCollections").querySelectorAll("button").forEach((button) => { button.disabled = blocked; });
        byId("imageDescriptionInput").disabled = state.busy || state.detailLoading || noteBusy() || !!fileLabels?.isBusy();
        byId("saveDescriptionButton").disabled = blocked || !state.note || (!noteDirty() && !state.note.uncertain) || state.note.conflict;
        byId("discardDescriptionButton").disabled = blocked || !state.note || (!noteDirty() && !state.note.conflict && !state.note.uncertain);
        byId("reloadDescriptionButton").disabled = blocked || !state.note;
        byId("useSavedDescriptionButton").disabled = blocked || !state.note || !state.note.latest;
        byId("keepDraftDescriptionButton").disabled = blocked || !state.note || !state.note.latest;
        byId("imageDescriptionForm").setAttribute("aria-busy", String(noteBusy()));
        text("descriptionCount", byId("imageDescriptionInput").value.length.toLocaleString("vi-VN") + " / 4.000 ký tự");
        knowledgeControls();
    }
    function changed() { state.pending = null; text("importStatus", "Chỉ gửi file khi bạn nhấn Nhập tài liệu."); controls(); }
    function renderQueue() {
        const fragment = document.createDocumentFragment();
        state.queue.forEach((entry, index) => {
            const item = node("li");
            const info = node("div", null, "selected-file-info");
            info.append(node("span", entry.path, "selected-file-path"), node("span", bytesLabel(entry.file.size), "selected-file-size"));
            const remove = node("button", "Bỏ", "text-button");
            remove.type = "button";
            remove.setAttribute("aria-label", "Bỏ " + entry.path);
            remove.addEventListener("click", () => {
                if (state.busy || state.scanning) return;
                state.queue.splice(index, 1); changed(); renderQueue();
            });
            item.append(info, remove); fragment.append(item);
        });
        byId("selectedFiles").replaceChildren(fragment);
        const total = state.queue.reduce((sum, entry) => sum + entry.file.size, 0);
        let message = state.queue.length ? state.queue.length + " file · " + bytesLabel(total) + " · Chưa gửi" : "Chưa chọn tài liệu được hỗ trợ.";
        if (state.ignored) message += " Đã bỏ qua " + state.ignored + " file không hỗ trợ (chỉ nhận PDF, PPTX, DOCX, PNG, JPG, JPEG).";
        text("selectionMessage", message); controls();
    }
    function relativePath(value) {
        const path = String(value || "").replace(/\\/g, "/");
        const parts = path.split("/");
        if (!path || path.startsWith("/") || /[\x00-\x1f:]/.test(path) || parts.some((part) => !part || part === "." || part === "..")) throw new Error("Có đường dẫn file không hợp lệ. Hãy chọn lại file trong thư mục bài giảng.");
        if (parts.length > MAX_DEPTH) throw new Error("Thư mục quá sâu. Hãy chọn một thư mục con gần bài giảng hơn (đường dẫn tối đa 12 phần).");
        return path;
    }
    function acceptSelection(entries) {
        if (entries.length > MAX_ENTRIES) throw new Error("Thư mục có quá nhiều file để duyệt. Hãy chọn một thư mục nhỏ hơn (tối đa 1.000 mục).");
        const selected = []; let ignored = 0; let total = 0;
        const seen = new Set(); const directories = new Set();
        for (const entry of entries) {
            const path = relativePath(entry.path || entry.file.name);
            const parts = path.split("/");
            for (let index = 1; index < parts.length; index += 1) directories.add(parts.slice(0, index).join("/"));
            if (entries.length + directories.size > MAX_ENTRIES) throw new Error("Thư mục vượt 1.000 mục. Hãy chọn một thư mục nhỏ hơn.");
            if (!supported.test(entry.file.name)) { ignored += 1; continue; }
            const foldedPath = path.toLowerCase();
            if (seen.has(foldedPath)) throw new Error("Có hai file cùng đường dẫn " + path + " (không phân biệt hoa/thường). Hãy nhập từng thư mục riêng.");
            seen.add(foldedPath);
            if (entry.file.size > MAX_FILE_BYTES) throw new Error("File " + path + " vượt 20 MiB. Danh sách trước đó vẫn được giữ.");
            total += entry.file.size;
            selected.push({ file: entry.file, path });
        }
        if (selected.length > MAX_FILES) throw new Error("Có hơn 10 file được hỗ trợ. Hãy chọn một chương nhỏ hơn; danh sách trước đó vẫn được giữ.");
        if (total > MAX_TOTAL_BYTES) throw new Error("Tổng file vượt 64 MiB. Hãy chọn ít file hơn; danh sách trước đó vẫn được giữ.");
        state.queue = selected; state.ignored = ignored; changed();
        if ((!state.titleEdited || !byId("materialsTitleInput").value.trim()) && selected.length) {
            const first = selected[0].path.split("/");
            const oneFolder = first.length > 1 && selected.every((entry) => entry.path.split("/")[0] === first[0]);
            byId("materialsTitleInput").value = (oneFolder ? first[0] : selected[0].file.name.replace(/\.[^.]+$/, "")).slice(0, 200);
        }
        renderQueue(); announce(selected.length + " file đã chọn. Chưa gửi tới máy chủ.");
    }
    async function selectionTask(reader) {
        if (state.busy || state.scanning || state.detailLoading || noteBusy() || knowledgeBusy() || fileLabels?.isBusy()) return;
        state.scanning = true; clearNotice(); controls();
        text("importStatus", "Đang đọc danh sách file, chưa gửi nội dung…");
        try { acceptSelection(await reader()); }
        catch (error) { notice(error.message || "Không đọc được danh sách. Hãy dùng nút Chọn file hoặc Chọn thư mục."); }
        finally { state.scanning = false; text("importStatus", state.pending ? "Chưa xác nhận lần nhập trước. Bạn có thể thử lại với cùng danh sách." : "Chỉ gửi file khi bạn nhấn Nhập tài liệu."); controls(); }
    }
    function entryFile(entry) { return new Promise((resolve, reject) => entry.file(resolve, () => reject(new Error("Không đọc được file trong thư mục. Hãy chọn lại file bằng nút Chọn file.")))); }
    function entryBatch(reader) { return new Promise((resolve, reject) => reader.readEntries(resolve, () => reject(new Error("Không duyệt được thư mục. Hãy dùng nút Chọn thư mục.")))); }
    async function readEntries(roots) {
        const files = []; let visited = 0;
        async function visit(entry, parent, depth) {
            visited += 1;
            if (visited > MAX_ENTRIES) throw new Error("Thư mục vượt 1.000 mục. Hãy chọn một thư mục nhỏ hơn.");
            if (depth > MAX_DEPTH) throw new Error("Thư mục vượt 12 cấp. Hãy chọn thư mục con chứa bài giảng.");
            const path = parent ? parent + "/" + entry.name : entry.name;
            if (entry.isFile) files.push({ file: await entryFile(entry), path });
            else if (entry.isDirectory) {
                const reader = entry.createReader();
                // Chromium returns a directory in batches; one read is insufficient.
                while (true) {
                    const batch = await entryBatch(reader);
                    if (!batch.length) break;
                    for (const child of batch) await visit(child, path, depth + 1);
                }
            }
        }
        for (const root of roots) await visit(root, "", 0);
        return files;
    }
    function requestId() {
        if (globalThis.crypto.randomUUID) return globalThis.crypto.randomUUID();
        const values = new Uint8Array(16); globalThis.crypto.getRandomValues(values);
        values[6] = (values[6] & 15) | 64; values[8] = (values[8] & 63) | 128;
        const hex = Array.from(values, (value) => value.toString(16).padStart(2, "0")).join("");
        return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
    }
    async function api(url, options) {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 60000);
        try {
            const response = await fetch(url, Object.assign({ credentials: "same-origin", cache: "no-store", signal: controller.signal }, options));
            let data;
            try { data = await response.json(); }
            catch (_) { const error = new Error("Không đọc được phản hồi máy chủ."); error.ambiguous = true; throw error; }
            if (!response.ok || data.ok === false) {
                const error = new Error(data.error || "Yêu cầu chưa được xử lý.");
                error.status = response.status; error.code = data.error_code; error.ambiguous = response.status >= 500; throw error;
            }
            return data;
        } catch (error) { if (!error.status) error.ambiguous = true; throw error; }
        finally { clearTimeout(timeout); }
    }
    function errorText(error) {
        if (error.status === 401 || error.status === 403) return "Cần xác thực lại phiên truy cập. Dùng phần đăng nhập trên trang rồi thử lại; danh sách file vẫn được giữ.";
        if (error.code === "import_incomplete") return error.message + " Chọn lại file hoặc sửa tên bộ tài liệu để tạo một lần nhập mới.";
        if (error.ambiguous) return "Chưa nhận được xác nhận từ máy chủ. Danh sách file vẫn được giữ. Nhấn Nhập tài liệu lần nữa để kiểm tra cùng yêu cầu, tránh tạo bản trùng.";
        return error.message || "Không thực hiện được yêu cầu. Hãy thử lại.";
    }
    function renderCollections() {
        const fragment = document.createDocumentFragment();
        state.collections.forEach((collection) => {
            const item = node("li"); const button = node("button", null, "collection-button");
            button.type = "button"; button.dataset.collectionId = String(collection.id);
            button.setAttribute("aria-pressed", String(!!state.collection && state.collection.id === collection.id));
            button.append(node("span", collection.title, "collection-title"));
            let date = "";
            if (collection.created_at && !Number.isNaN(Date.parse(collection.created_at))) date = " · " + new Date(collection.created_at).toLocaleDateString("vi-VN");
            button.append(node("span", collection.source_count + " file · " + collection.chunk_count + " đoạn trích" + date, "collection-meta"), node("span", statusLabel(collection.status), "collection-state"));
            button.addEventListener("click", () => loadCollection(collection.id));
            item.append(button); fragment.append(item);
        });
        byId("materialsCollections").replaceChildren(fragment);
        show("collectionsEmpty", !state.collections.length);
        text("collectionsEmpty", "Chưa có bộ tài liệu nào trong trình duyệt này. Chọn file hoặc thư mục để bắt đầu.");
        controls();
    }
    async function loadCollections() {
        if (state.listBusy) return;
        state.listBusy = true; controls();
        const version = state.collectionsVersion;
        try { const data = await api("/learn/api/materials"); if (version === state.collectionsVersion) { state.collections = data.collections || []; renderCollections(); } }
        catch (error) { notice(error.status === 401 || error.status === 403 ? errorText(error) : "Chưa tải được danh sách tài liệu. Nhấn Tải lại để thử tiếp."); if (!state.collections.length) text("collectionsEmpty", "Chưa tải được danh sách; chưa thể xác nhận có tài liệu hay không."); }
        finally { state.listBusy = false; controls(); }
    }
    function listWarnings(id, warnings) { byId(id).replaceChildren(...(warnings || []).map((value) => node("li", value))); }
    function citation(unit) {
        if (!unit || !unit.locator) return "Chưa có phần nguồn";
        const labels = { page: "Trang PDF", slide: "Slide", paragraph: "Đoạn Word", table: "Bảng Word", image: "Ảnh" };
        return (labels[unit.locator.kind] || "Phần nguồn") + " " + unit.locator.index;
    }
    function renderUnit() {
        const unit = state.units[state.unitIndex];
        sourceVisuals?.setContext(state.collection, unit, state.collection?.sources?.[state.sourceIndex]);
        renderPracticeLink();
        text("unitCitation", citation(unit)); text("unitCount", "/ " + state.units.length);
        byId("unitNumberInput").max = String(Math.max(1, state.units.length));
        byId("unitNumberInput").value = String(state.units.length ? state.unitIndex + 1 : 0);
        byId("unitNumberInput").disabled = !state.units.length;
        byId("previousUnitButton").disabled = state.unitIndex <= 0;
        byId("nextUnitButton").disabled = state.unitIndex >= state.units.length - 1;
        listWarnings("unitWarnings", unit ? unit.warnings : []);
        const full = unit ? String(unit.text || "") : "";
        text("unitText", full.trim() ? full.slice(0, MAX_PREVIEW) : "Không tìm thấy chữ ở phần này. Hãy đối chiếu file gốc; có thể cần OCR hoặc kiểm tra hình ảnh.");
        show("previewLimitNote", full.length > MAX_PREVIEW);
        text("previewLimitNote", "Đang hiển thị " + MAX_PREVIEW.toLocaleString("vi-VN") + " ký tự đầu của phần này. Bản trích lưu trên máy chủ vẫn giữ toàn bộ văn bản; hãy đối chiếu file gốc để xem phần còn lại.");
        loadKnowledge();
    }
    function knowledgeBusy() {
        const knowledge = state.knowledge;
        return !!knowledge && (knowledge.saving || (knowledge.loading && !!knowledge.pending));
    }
    function knowledgeDirty() { return !!state.knowledge && (!!state.knowledge.pending || !!byId("conceptInput").value.trim()); }
    function guardKnowledge() {
        if (knowledgeBusy()) { notice("Đang xử lý liên kết khái niệm. Hãy đợi thao tác hoàn tất."); return false; }
        if (knowledgeDirty()) {
            notice("Khái niệm còn thay đổi chưa xác nhận. Hãy gắn khái niệm, thử lại lượt lưu hoặc bỏ thay đổi trước khi chuyển nguồn.");
            (state.knowledge.pending ? byId("discardKnowledgeButton") : byId("conceptInput")).focus(); return false;
        }
        return true;
    }
    function knowledgeControls() {
        const knowledge = state.knowledge;
        const blocked = !knowledge || !knowledge.view || knowledge.loading || knowledge.saving || state.busy || state.detailLoading || noteBusy() || !!fileLabels?.isBusy();
        byId("conceptInput").disabled = blocked || !!knowledge.pending;
        byId("addConceptButton").disabled = blocked || !!knowledge.pending || !byId("conceptInput").value.trim() || knowledge.view.concepts.length >= 12;
        byId("conceptTags").querySelectorAll("button").forEach((button) => { button.disabled = blocked || !!knowledge.pending; });
        byId("relatedSources").querySelectorAll("button").forEach((button) => { button.disabled = knowledgeBusy() || state.busy || state.detailLoading || noteBusy(); });
        byId("discardKnowledgeButton").disabled = !knowledge || knowledge.loading || knowledge.saving || !knowledgeDirty();
        byId("reloadKnowledgeButton").disabled = !knowledge || knowledge.loading || knowledge.saving || state.busy || state.detailLoading;
        byId("retryKnowledgeButton").disabled = blocked || !knowledge.pending || knowledge.conflict;
        show("retryKnowledgeButton", !!knowledge && !!knowledge.pending && !knowledge.conflict && !knowledge.saving);
        byId("useSavedKnowledgeButton").disabled = blocked || !knowledge.latest;
        byId("applyDraftKnowledgeButton").disabled = blocked || !knowledge.latest || !knowledge.pending;
        byId("knowledgePanel").setAttribute("aria-busy", String(!!knowledge && (knowledge.loading || knowledge.saving)));
        const navigationBlocked = state.busy || state.detailLoading || knowledgeBusy();
        byId("previousUnitButton").disabled = navigationBlocked || state.unitIndex <= 0;
        byId("nextUnitButton").disabled = navigationBlocked || state.unitIndex >= state.units.length - 1;
        byId("unitNumberInput").disabled = navigationBlocked || !state.units.length;
    }
    function knowledgeAddress(knowledge) {
        return "/learn/api/materials/" + encodeURIComponent(knowledge.collectionId) + "/units/" + encodeURIComponent(knowledge.unitId) + "/knowledge";
    }
    function checkedKnowledge(knowledge, value) {
        if (!value || value.unit_id !== knowledge.unitId || !Number.isInteger(value.revision) || value.revision < 0 || !Array.isArray(value.concepts) || !Array.isArray(value.related) || value.concepts.some((concept) => !concept || typeof concept.label !== "string" || typeof concept.id !== "string")) {
            const error = new Error("Chưa đọc được phản hồi liên kết khái niệm."); error.ambiguous = true; throw error;
        }
        return value;
    }
    function renderKnowledge(knowledge) {
        const view = knowledge.view;
        byId("conceptTags").replaceChildren(...view.concepts.map((concept) => {
            const item = node("li", null, "concept-tag");
            const remove = node("button", "×", "concept-remove"); remove.type = "button";
            remove.setAttribute("aria-label", "Bỏ khái niệm " + concept.label);
            remove.addEventListener("click", () => submitConcepts(view.concepts.filter((item) => item.id !== concept.id).map((item) => item.label), false));
            item.append(node("span", concept.label), remove); return item;
        }));
        byId("relatedSources").replaceChildren(...view.related.map((related) => {
            const item = node("li"); const button = node("button", null, "related-source-button"); button.type = "button";
            button.dataset.unitId = related.unit_id;
            button.append(node("span", related.source_name, "related-source-name"), node("span", citation(related), "related-source-citation"));
            button.append(node("span", "Cùng khái niệm: " + related.concepts.map((concept) => concept.label).join(" · "), "related-source-concepts"));
            if (related.excerpt) button.append(node("span", related.excerpt, "related-source-excerpt"));
            button.addEventListener("click", () => openRelatedSource(knowledge, related)); item.append(button); return item;
        }));
        show("relatedSourcesEmpty", !view.related.length);
        text("relatedSourcesEmpty", view.concepts.length ? "Chưa có phần nguồn khác cùng khái niệm. Gắn cùng tên khái niệm vào phần muốn kết nối trong bộ này." : "Gắn một khái niệm để tìm các phần nguồn có cùng khái niệm.");
        text("relatedSourcesSummary", view.related.length ? (view.related_truncated ? "Hiển thị " + view.related.length + " / " + view.related_total : view.related.length) + " phần nguồn · Trong bộ tài liệu này" : "");
        controls();
    }
    async function loadKnowledge() {
        const unit = state.units[state.unitIndex];
        if (!state.collection || !unit) { state.knowledge = null; show("knowledgePanel", false); return; }
        if (state.knowledge && state.knowledge.collectionId === state.collection.id && state.knowledge.unitId === unit.unit_id) return;
        const knowledge = { collectionId: state.collection.id, unitId: unit.unit_id, view: null, loading: true, saving: false, pending: null, conflict: false, latest: null };
        state.knowledge = knowledge; byId("conceptInput").value = "";
        show("knowledgePanel", true); show("knowledgeConflict", false); show("latestKnowledgePanel", false);
        text("knowledgeCitation", citation(unit) + " · " + state.collection.title);
        byId("conceptTags").replaceChildren(); byId("relatedSources").replaceChildren(); text("relatedSourcesSummary", "");
        show("relatedSourcesEmpty", true); text("relatedSourcesEmpty", "Đang đọc liên kết của phần nguồn này…");
        text("knowledgeStatus", "Đang đọc khái niệm đã gắn…"); controls();
        try {
            const data = await api(knowledgeAddress(knowledge));
            if (state.knowledge !== knowledge) return;
            knowledge.view = checkedKnowledge(knowledge, data.knowledge); renderKnowledge(knowledge);
            text("knowledgeStatus", knowledge.view.concepts.length ? "Đã tải liên kết do bạn chọn. Có thể bỏ hoặc gắn thêm khái niệm." : "Chưa gắn khái niệm cho phần nguồn này.");
        } catch (error) {
            if (state.knowledge === knowledge) { text("knowledgeStatus", "Chưa đọc được liên kết. Nhấn Đọc liên kết đã lưu để thử lại."); text("relatedSourcesEmpty", "Chưa tải được kết nối; chưa thể xác nhận có nguồn liên quan hay không."); }
        } finally { knowledge.loading = false; if (state.knowledge === knowledge) controls(); }
    }
    function adoptKnowledge(knowledge, view, clearInput) {
        knowledge.view = view; knowledge.pending = null; knowledge.latest = null; knowledge.conflict = false;
        if (clearInput) byId("conceptInput").value = "";
        show("knowledgeConflict", false); show("latestKnowledgePanel", false); renderKnowledge(knowledge);
    }
    async function readLatestKnowledge(discard) {
        const knowledge = state.knowledge;
        if (!knowledge || knowledge.loading || knowledge.saving) return;
        knowledge.loading = true; controls(); text("knowledgeStatus", "Đang đọc liên kết đã lưu. Phần bạn đang chọn vẫn được giữ…");
        try {
            const data = await api(knowledgeAddress(knowledge));
            if (state.knowledge !== knowledge) return;
            const view = checkedKnowledge(knowledge, data.knowledge);
            if (!knowledge.pending || discard) {
                adoptKnowledge(knowledge, view, discard);
                text("knowledgeStatus", discard ? "Đã bỏ thay đổi chưa xác nhận và dùng liên kết hiện có trên máy chủ." : "Đã đọc liên kết mới nhất. Tên khái niệm đang nhập vẫn được giữ.");
                clearNotice();
            } else {
                knowledge.latest = view; knowledge.conflict = true;
                text("pendingConceptLabels", knowledge.pending.labels.join(" · ") || "(Không có khái niệm)");
                text("latestConceptLabels", view.concepts.map((concept) => concept.label).join(" · ") || "(Không có khái niệm)");
                show("knowledgeConflict", true); show("latestKnowledgePanel", true);
                text("knowledgeStatus", "Đã đọc bản mới nhất. Chọn danh sách muốn giữ bên dưới; chưa ghi thay đổi nào.");
            }
        } catch (error) { if (state.knowledge === knowledge) text("knowledgeStatus", "Chưa đọc được liên kết đã lưu. Phần bạn đang chọn vẫn được giữ; hãy thử lại."); }
        finally { knowledge.loading = false; if (state.knowledge === knowledge) controls(); }
    }
    function submitConcepts(labels, clearInput) {
        const knowledge = state.knowledge;
        if (!knowledge || !knowledge.view || knowledge.loading || knowledge.saving || knowledge.pending || state.busy || state.detailLoading || noteBusy()) return;
        knowledge.pending = { labels: labels.slice(), expected_revision: knowledge.view.revision, clearInput };
        saveKnowledge();
    }
    async function saveKnowledge() {
        const knowledge = state.knowledge;
        if (!knowledge || !knowledge.pending || knowledge.loading || knowledge.saving || knowledge.conflict) return;
        const pending = knowledge.pending;
        knowledge.saving = true; clearNotice(); controls(); text("knowledgeStatus", "Đang lưu liên kết bạn đã chọn…");
        try {
            const data = await api(knowledgeAddress(knowledge) + "/concepts", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ labels: pending.labels, expected_revision: pending.expected_revision }) });
            if (state.knowledge !== knowledge) return;
            adoptKnowledge(knowledge, checkedKnowledge(knowledge, data.knowledge), pending.clearInput);
            fileLabels?.refresh();
            text("knowledgeStatus", "Đã lưu liên kết khái niệm. Nội dung nguồn vẫn cần được đối chiếu."); announce("Đã lưu liên kết khái niệm.");
        } catch (error) {
            if (state.knowledge !== knowledge) return;
            if (error.code === "knowledge_conflict") {
                knowledge.conflict = true; knowledge.latest = null;
                text("pendingConceptLabels", pending.labels.join(" · ") || "(Không có khái niệm)");
                show("knowledgeConflict", true); show("latestKnowledgePanel", false);
                text("knowledgeStatus", "Liên kết đã đổi ở nơi khác. Danh sách bạn vừa chọn vẫn được giữ.");
            } else if (error.ambiguous) text("knowledgeStatus", "Chưa nhận được xác nhận. Thử lại đúng lượt lưu hoặc đọc liên kết đã lưu để đối chiếu; danh sách bạn chọn được giữ nguyên.");
            else { knowledge.pending = null; text("knowledgeStatus", error.status === 401 || error.status === 403 ? "Cần xác thực lại phiên truy cập trước khi lưu. Tên đang nhập vẫn được giữ." : (error.message || "Chưa lưu được liên kết. Hãy thử lại.")); }
        } finally { knowledge.saving = false; if (state.knowledge === knowledge) controls(); }
        if (state.knowledge === knowledge && knowledge.conflict) readLatestKnowledge(false);
    }
    function openRelatedSource(knowledge, related) {
        if (state.knowledge !== knowledge || state.busy || state.detailLoading || !guardNote() || !guardKnowledge() || !fileLabels.guard()) return;
        const sources = state.collection.sources || [];
        const index = sources.findIndex((source) => source.source_id === related.source_id);
        if (index < 0 || !(state.collection.units || []).some((unit) => unit.unit_id === related.unit_id && unit.source_id === related.source_id)) { notice("Phần nguồn này chưa có trong bản đang mở. Hãy mở lại bộ tài liệu."); return; }
        state.sourceIndex = index; renderSourceOptions();
        byId("materialSourceSelect").value = String(index); selectSource(null, related.unit_id);
        byId("materialSourceSelect").focus(); byId("materialSourceSelect").scrollIntoView({ block: "center" });
        announce("Đã mở " + related.source_name + ", " + citation(related) + ".");
    }
    function imageAddress(source) {
        try {
            if (!source.image_url || !state.collection) return null;
            const digest = String(source.source_id || "").replace(/^sha256:/, "");
            if (!/^[a-f0-9]{64}$/.test(digest)) return null;
            const url = new URL(source.image_url, location.href);
            const expected = "/learn/api/materials/" + encodeURIComponent(state.collection.id) + "/sources/" + digest + "/image";
            if (url.origin !== location.origin || url.pathname !== expected || url.search || url.hash || url.username || url.password) return null;
            return url.href;
        } catch (_) { return null; }
    }
    function renderImage(source) {
        const description = source.description || { text: "", revision: 0, origin: "user" };
        state.note = { sourceId: source.source_id, collectionId: state.collection.id,
            baseText: String(description.text || ""), revision: description.revision,
            saving: false, loading: false, conflict: false, uncertain: false, latest: null };
        byId("imageDescriptionInput").value = state.note.baseText;
        show("descriptionConflict", false); show("latestDescriptionPanel", false);
        fileLabels?.refresh();
        text("descriptionStatus", state.note.baseText ? "Mô tả do bạn viết đã được tải từ máy chủ." : "Chưa có mô tả của bạn. Ảnh chưa được diễn giải tự động.");
        const metadata = source.image || {};
        text("imageDimensions", Number.isInteger(metadata.width) && Number.isInteger(metadata.height) ? metadata.width + " × " + metadata.height + " px · " + (metadata.mime_type === "image/png" ? "PNG" : "JPEG") : "Ảnh nguồn");
        byId("imageViewport").classList.remove("natural-size");
        byId("imageZoomButton").setAttribute("aria-pressed", "false");
        text("imageZoomButton", "Xem kích thước gốc");
        const image = byId("materialImage");
        image.removeAttribute("src"); image.hidden = true;
        image.alt = "Ảnh nguồn: " + (source.original_names || []).join(" · ") + ". Chưa có diễn giải tự động.";
        const address = imageAddress(source);
        byId("imageZoomButton").disabled = true;
        if (address) {
            text("imageLoadStatus", "Đang tải ảnh nguồn…");
            image.src = address; image.hidden = false;
        } else text("imageLoadStatus", "Chưa có đường dẫn ảnh hợp lệ để xem. Hãy tải lại bộ tài liệu.");
        controls();
    }
    function checkedDescription(value) {
        if (!value || typeof value.text !== "string" || !Number.isInteger(value.revision) || value.revision < 0 || value.origin !== "user") {
            const error = new Error("Phản hồi mô tả chưa hợp lệ."); error.ambiguous = true; throw error;
        }
        return value;
    }
    function adoptDescription(note, description, keepDraft) {
        note.baseText = description.text; note.revision = description.revision;
        note.conflict = false; note.uncertain = false; note.latest = null;
        if (!keepDraft) byId("imageDescriptionInput").value = description.text;
        const source = (state.collection.sources || []).find((item) => item.source_id === note.sourceId);
        if (source) source.description = description;
        fileLabels?.refresh();
        show("descriptionConflict", false); show("latestDescriptionPanel", false);
        controls();
    }
    function descriptionError(error) {
        if (error.status === 401 || error.status === 403) return "Cần xác thực lại phiên truy cập rồi thử lại. Mô tả đang viết vẫn được giữ.";
        if (error.ambiguous) return "Chưa nhận được xác nhận. Mô tả đang viết vẫn được giữ. Nhấn Lưu mô tả lần nữa để xác nhận cùng nội dung, hoặc đọc bản đã lưu trước khi quyết định.";
        return (error.message || "Chưa lưu được mô tả.") + " Mô tả đang viết vẫn được giữ.";
    }
    async function saveDescription(event) {
        event.preventDefault();
        const note = state.note;
        if (!note || noteBusy() || state.busy || state.detailLoading || note.conflict || (!noteDirty() && !note.uncertain)) return;
        const source = (state.collection.sources || []).find((item) => item.source_id === note.sourceId);
        const address = source && imageAddress(source);
        if (!address) { text("descriptionStatus", "Chưa xác định được ảnh để lưu mô tả. Bản đang viết vẫn được giữ."); return; }
        const submitted = byId("imageDescriptionInput").value;
        note.saving = true; clearNotice(); controls();
        text("descriptionStatus", "Đang lưu mô tả của bạn…");
        try {
            const data = await api(address.replace(/\/image$/, "/description"), {
                method: "PUT", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: submitted, expected_revision: note.revision })
            });
            if (state.note !== note) return;
            const description = checkedDescription(data.description);
            if (description.text !== submitted) { const error = new Error("Phản hồi chưa xác nhận đúng bản mô tả vừa gửi."); error.ambiguous = true; throw error; }
            adoptDescription(note, description, false);
            text("descriptionStatus", "Đã lưu mô tả của bạn. Nội dung vẫn cần được đối chiếu với ảnh nguồn.");
            announce("Đã lưu mô tả ảnh.");
        } catch (error) {
            if (state.note !== note) return;
            if (error.code === "description_conflict") {
                note.conflict = true; note.latest = null;
                show("descriptionConflict", true); show("latestDescriptionPanel", false);
                text("descriptionStatus", "Mô tả đã thay đổi ở nơi khác. Bản đang viết vẫn được giữ; hãy đọc bản đã lưu để đối chiếu.");
            } else {
                if (error.ambiguous) { note.uncertain = true; show("descriptionConflict", true); }
                text("descriptionStatus", descriptionError(error));
            }
        } finally { note.saving = false; controls(); }
    }
    async function reloadDescription(discardDraft) {
        const note = state.note;
        if (!note || noteBusy() || state.busy || state.detailLoading) return;
        note.loading = true; controls();
        text("descriptionStatus", "Đang đọc mô tả đã lưu; bản đang viết được giữ nguyên…");
        try {
            const data = await api("/learn/api/materials/" + encodeURIComponent(note.collectionId));
            if (state.note !== note) return;
            const source = (data.collection.sources || []).find((item) => item.source_id === note.sourceId);
            const description = checkedDescription(source && source.description);
            if (discardDraft) {
                adoptDescription(note, description, false);
                clearNotice();
                text("descriptionStatus", "Đã bỏ thay đổi chưa lưu và dùng mô tả hiện có trên máy chủ.");
            } else {
                note.latest = description; note.conflict = true;
                text("latestDescriptionText", description.text || "(Chưa có mô tả đã lưu)");
                show("descriptionConflict", true); show("latestDescriptionPanel", true);
                text("descriptionStatus", "Đã đọc bản mới nhất. Chọn dùng bản đã lưu hoặc giữ bản đang viết; chưa ghi thay đổi nào.");
            }
        } catch (error) {
            if (state.note === note) text("descriptionStatus", error.status === 401 || error.status === 403 ? descriptionError(error) : "Chưa đọc được bản đã lưu. Bản đang viết vẫn được giữ; hãy thử lại.");
        } finally { note.loading = false; controls(); }
    }
    function discardDescription() {
        if (!state.note || noteBusy()) return;
        if (state.note.conflict || state.note.uncertain) { reloadDescription(true); return; }
        byId("imageDescriptionInput").value = state.note.baseText;
        text("descriptionStatus", "Đã bỏ thay đổi chưa lưu."); clearNotice(); controls();
    }
    function renderPracticeLink() {
        const unit = state.units[state.unitIndex], link = byId("practiceFromUnit");
        link.hidden = !unit || !state.collection;
        if (unit && state.collection) link.href = "/learn/practice?collection=" + encodeURIComponent(state.collection.id) + "&unit=" + encodeURIComponent(unit.unit_id);
    }
    function selectSource(event, targetUnitId) {
        if (event && (!guardNote() || !guardKnowledge() || !fileLabels.guard())) { byId("materialSourceSelect").value = String(state.sourceIndex); return; }
        const sources = state.collection ? state.collection.sources || [] : [];
        state.sourceIndex = Number(byId("materialSourceSelect").value);
        const source = sources[state.sourceIndex];
        fileLabels?.setSource(state.collection, source);
        state.units = source ? (state.collection.units || []).filter((unit) => unit.source_id === source.source_id) : [];
        state.unitIndex = Math.max(0, state.units.findIndex((unit) => unit.unit_id === targetUnitId));
        renderPracticeLink();
        const paths = source ? (source.upload_paths && source.upload_paths.length ? source.upload_paths : source.original_names || []) : [];
        const isImage = !!source && !!source.image;
        text("sourceDetails", source ? paths.join(" · ") + " — " + (isImage ? "Ảnh nguồn" : source.unit_count + " phần nguồn") + " · " + statusLabel(source.status) : "Chưa có file nguồn.");
        listWarnings("sourceWarnings", source ? source.warnings : []);
        show("imagePanel", isImage); show("textSourcePanel", !isImage);
        if (isImage) { renderImage(source); sourceVisuals?.setContext(state.collection, state.units[state.unitIndex], source); loadKnowledge(); }
        else { state.note = null; byId("materialImage").removeAttribute("src"); renderUnit(); controls(); }
    }
    function renderSourceOptions() {
        if (!state.collection) return;
        const query = byId("materialFileFilter").value.trim().toLocaleLowerCase();
        const sources = state.collection.sources || [];
        let matched = 0, selectedMatches = false;
        const options = [];
        sources.forEach((source, index) => {
            const searchable = [...(source.original_names || []), ...(source.upload_paths || []), fileLabels?.confirmedText(source.source_id) || ""].join(" ").toLocaleLowerCase();
            const matches = !query || searchable.includes(query);
            if (matches) matched += 1;
            if (index === state.sourceIndex) selectedMatches = matches;
            if (!matches && index !== state.sourceIndex) return;
            const option = node("option", (source.original_names || [source.format]).join(" · "));
            option.value = String(index); options.push(option);
        });
        byId("materialSourceSelect").replaceChildren(...options);
        byId("materialSourceSelect").value = String(state.sourceIndex);
        text("materialFileFilterStatus", query ? matched + " / " + sources.length + " files match confirmed labels or filename." + (!selectedMatches ? " File đang xem được giữ để không mất vị trí." : "") : "Tìm theo tên file hoặc nhãn bạn đã xác nhận. Gợi ý chưa xác nhận không tham gia lọc.");
    }
    function displayCollection(collection, focus, targetUnitId) {
        state.collection = collection; show("materialPreview", true);
        state.sourceIndex = 0; byId("materialFileFilter").value = "";
        text("previewHeading", collection.title); text("collectionStatus", statusLabel(collection.status));
        renderSourceOptions();
        const targetUnit = targetUnitId && (collection.units || []).find((unit) => unit.unit_id === targetUnitId);
        if (targetUnit) {
            const index = (collection.sources || []).findIndex((source) => source.source_id === targetUnit.source_id);
            if (index >= 0) byId("materialSourceSelect").value = String(index);
        }
        selectSource(null, targetUnit ? targetUnit.unit_id : undefined); renderCollections();
        if (targetUnitId && !targetUnit) notice("Phần nguồn trong liên kết không còn thuộc bộ tài liệu này. Hãy chọn lại phần cần xem.");
        if (focus) byId("previewHeading").focus();
    }
    async function loadCollection(id, targetUnitId) {
        if (state.busy || state.detailLoading || !guardNote() || !guardKnowledge() || !fileLabels.guard()) return;
        const request = ++state.detailRequest; clearNotice();
        state.detailLoading = true; controls();
        byId("materialPreview").setAttribute("aria-busy", "true");
        announce("Đang mở bản trích tài liệu…");
        try {
            const data = await api("/learn/api/materials/" + encodeURIComponent(id));
            if (request === state.detailRequest) { displayCollection(data.collection, true, targetUnitId); announce("Đã mở bản trích, cần đối chiếu file gốc."); }
        } catch (error) { if (request === state.detailRequest) notice(error.status === 401 || error.status === 403 ? errorText(error) : "Chưa mở được bộ tài liệu này. Chọn lại bộ tài liệu để thử tiếp."); }
        finally { if (request === state.detailRequest) { state.detailLoading = false; byId("materialPreview").setAttribute("aria-busy", "false"); controls(); } }
    }
    async function importMaterials(event) {
        event.preventDefault();
        if (state.busy || state.scanning || state.detailLoading || !state.queue.length || !byId("materialsTitleInput").value.trim() || !guardNote() || !guardKnowledge() || !fileLabels.guard()) return;
        state.busy = true; clearNotice(); controls();
        text("importStatus", "Đang gửi và trích xuất tài liệu… Giữ trang này mở trong lúc chờ.");
        try {
            if (!state.pending) state.pending = { id: requestId(), title: byId("materialsTitleInput").value.trim(), queue: state.queue.slice() };
            const pending = state.pending;
            const form = new FormData();
            form.append("title", pending.title); form.append("request_id", pending.id);
            form.append("paths", JSON.stringify(pending.queue.map((entry) => entry.path)));
            pending.queue.forEach((entry) => form.append("files", entry.file, entry.file.name));
            const data = await api("/learn/api/materials", { method: "POST", body: form });
            const collection = data.collection;
            state.detailRequest += 1;
            state.collectionsVersion += 1;
            state.collections = [collection].concat(state.collections.filter((item) => item.id !== collection.id));
            state.queue = []; state.ignored = 0; state.pending = null; state.titleEdited = false;
            byId("materialsTitleInput").value = ""; renderQueue(); displayCollection(collection, true);
            byId("materialPreview").setAttribute("aria-busy", "false");
            text("importStatus", "Đã nhập. Hãy xem lại nguồn bên dưới; chưa đưa vào bài học hoặc diễn giải ảnh bằng AI.");
            announce("Đã nhập tài liệu. Nội dung đang chờ bạn xem lại.");
        } catch (error) { notice(errorText(error)); text("importStatus", "Chưa hoàn tất xác nhận. File đã chọn vẫn còn; giữ nguyên danh sách và thử lại."); }
        finally { state.busy = false; controls(); }
    }

    byId("chooseFilesButton").addEventListener("click", () => byId("materialsFilesInput").click());
    byId("chooseFolderButton").addEventListener("click", () => byId("materialsFolderInput").click());
    for (const id of ["materialsFilesInput", "materialsFolderInput"]) {
        byId(id).addEventListener("change", (event) => {
            const files = Array.from(event.target.files || []);
            event.target.value = "";
            if (files.length) selectionTask(async () => files.map((file) => ({ file, path: file.webkitRelativePath || file.name })));
        });
    }
    const dropzone = byId("materialsDropzone");
    window.addEventListener("dragover", (event) => event.preventDefault());
    window.addEventListener("drop", (event) => event.preventDefault());
    dropzone.addEventListener("dragover", (event) => { event.preventDefault(); if (!state.busy && !state.scanning) dropzone.classList.add("dragging"); });
    dropzone.addEventListener("dragleave", (event) => { if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("dragging"); });
    dropzone.addEventListener("drop", (event) => {
        event.preventDefault(); dropzone.classList.remove("dragging");
        // Capture entries synchronously; the browser clears DataTransfer after drop.
        const items = Array.from(event.dataTransfer.items || []).filter((item) => item.kind === "file");
        const roots = items.map((item) => typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null);
        const fallback = Array.from(event.dataTransfer.files || []);
        if (roots.length && roots.every(Boolean)) selectionTask(() => readEntries(roots));
        else if (fallback.length) selectionTask(async () => fallback.map((file) => ({ file, path: file.webkitRelativePath || file.name })));
        else notice("Trình duyệt chưa đọc được mục được thả. Hãy dùng nút Chọn file hoặc Chọn thư mục.");
    });
    byId("materialsTitleInput").addEventListener("input", () => { state.titleEdited = true; changed(); });
    byId("materialsImportForm").addEventListener("submit", importMaterials);
    byId("refreshMaterialsButton").addEventListener("click", () => { clearNotice(); loadCollections(); });
    fileLabels = window.LearningFileLabels.create({ api, onChange: controls, onRecords: renderSourceOptions, notice });
    sourceVisuals = window.LearningSourceVisuals.create({ api });
    byId("materialFileFilter").addEventListener("input", renderSourceOptions);
    byId("practiceFromUnit").addEventListener("click", (event) => { if (!guardNote() || !guardKnowledge() || !fileLabels.guard()) event.preventDefault(); });
    byId("materialSourceSelect").addEventListener("change", selectSource);
    byId("conceptInput").addEventListener("input", () => controls());
    byId("conceptForm").addEventListener("submit", (event) => {
        event.preventDefault();
        const knowledge = state.knowledge; const label = byId("conceptInput").value.trim();
        if (!knowledge || !knowledge.view || !label || knowledge.view.concepts.length >= 12) return;
        submitConcepts(knowledge.view.concepts.map((concept) => concept.label).concat(label), true);
    });
    byId("retryKnowledgeButton").addEventListener("click", saveKnowledge);
    byId("reloadKnowledgeButton").addEventListener("click", () => readLatestKnowledge(false));
    byId("discardKnowledgeButton").addEventListener("click", () => {
        const knowledge = state.knowledge;
        if (!knowledge || knowledge.loading || knowledge.saving) return;
        if (knowledge.pending) { readLatestKnowledge(true); return; }
        byId("conceptInput").value = ""; clearNotice();
        text("knowledgeStatus", "Đã bỏ tên khái niệm chưa gắn. Liên kết đã lưu vẫn được giữ."); controls();
    });
    byId("useSavedKnowledgeButton").addEventListener("click", () => {
        const knowledge = state.knowledge;
        if (!knowledge || knowledge.loading || knowledge.saving || !knowledge.latest) return;
        adoptKnowledge(knowledge, knowledge.latest, true); clearNotice();
        text("knowledgeStatus", "Đang dùng liên kết đã lưu trên máy chủ. Không ghi thay đổi mới.");
    });
    byId("applyDraftKnowledgeButton").addEventListener("click", () => {
        const knowledge = state.knowledge;
        if (!knowledge || knowledge.loading || knowledge.saving || !knowledge.latest || !knowledge.pending) return;
        knowledge.pending.expected_revision = knowledge.latest.revision; knowledge.conflict = false;
        knowledge.latest = null; show("knowledgeConflict", false); show("latestKnowledgePanel", false);
        saveKnowledge();
    });
    byId("imageDescriptionInput").addEventListener("input", () => {
        if (!state.note) return;
        text("descriptionStatus", state.note.conflict ? "Bản đang viết được giữ. Hãy đối chiếu bản đã lưu trước khi lưu tiếp." : (state.note.uncertain ? "Lần lưu trước chưa được xác nhận. Giữ nội dung và thử lưu lại, hoặc đọc bản đã lưu." : (noteDirty() ? "Có thay đổi chưa lưu." : "Chưa có thay đổi mới.")));
        controls();
    });
    byId("imageDescriptionForm").addEventListener("submit", saveDescription);
    byId("discardDescriptionButton").addEventListener("click", discardDescription);
    byId("reloadDescriptionButton").addEventListener("click", () => reloadDescription(false));
    byId("useSavedDescriptionButton").addEventListener("click", () => {
        if (!state.note || noteBusy() || !state.note.latest) return;
        adoptDescription(state.note, state.note.latest, false);
        text("descriptionStatus", "Đang dùng bản đã lưu trên máy chủ. Không ghi thay đổi mới."); clearNotice();
    });
    byId("keepDraftDescriptionButton").addEventListener("click", () => {
        if (!state.note || noteBusy() || !state.note.latest) return;
        adoptDescription(state.note, state.note.latest, true);
        text("descriptionStatus", noteDirty() ? "Đã giữ bản đang viết. Nhấn Lưu mô tả khi bạn muốn thay bản đã lưu bằng nội dung này." : "Bản đang viết trùng với bản đã lưu. Không cần lưu lại."); clearNotice();
        byId("imageDescriptionInput").focus();
    });
    byId("materialImage").addEventListener("load", () => {
        if (!state.note || !byId("materialImage").naturalWidth) return;
        text("imageLoadStatus", "Đã tải ảnh nguồn. Bạn có thể mở kích thước gốc để xem rõ chi tiết.");
        byId("imageZoomButton").disabled = false;
    });
    byId("materialImage").addEventListener("error", () => {
        if (!state.note || !byId("materialImage").getAttribute("src")) return;
        byId("materialImage").hidden = true; byId("imageZoomButton").disabled = true;
        text("imageLoadStatus", "Chưa tải được ảnh. Hãy kiểm tra phiên truy cập rồi mở lại bộ tài liệu. Mô tả đang viết vẫn được giữ.");
    });
    byId("imageZoomButton").addEventListener("click", () => {
        const natural = byId("imageViewport").classList.toggle("natural-size");
        byId("imageZoomButton").setAttribute("aria-pressed", String(natural));
        text("imageZoomButton", natural ? "Vừa khung xem" : "Xem kích thước gốc");
        text("imageLoadStatus", natural ? "Đang xem kích thước gốc. Cuộn trong khung để xem các phần còn lại; có thể dùng phím mũi tên khi khung được chọn." : "Ảnh vừa khung xem.");
        if (natural) byId("imageViewport").focus();
    });
    window.addEventListener("beforeunload", (event) => {
        if (noteDirty() || noteBusy() || knowledgeDirty() || knowledgeBusy() || fileLabels.isDirty() || fileLabels.isBusy() || (state.note && (state.note.conflict || state.note.uncertain))) {
            event.preventDefault(); event.returnValue = "";
        }
    });
    byId("previousUnitButton").addEventListener("click", () => { if (state.unitIndex > 0 && guardKnowledge()) { state.unitIndex -= 1; renderUnit(); } });
    byId("nextUnitButton").addEventListener("click", () => { if (state.unitIndex + 1 < state.units.length && guardKnowledge()) { state.unitIndex += 1; renderUnit(); } });
    byId("unitNumberInput").addEventListener("change", (event) => {
        const value = Number(event.target.value);
        if (Number.isInteger(value) && value >= 1 && value <= state.units.length && guardKnowledge()) state.unitIndex = value - 1;
        renderUnit();
    });
    async function boot() {
        controls();
        await loadCollections();
        const params = new URLSearchParams(window.location.search);
        const collection = params.get("collection"), unit = params.get("unit");
        if (!collection && !unit) return;
        if (!collection || !/^[a-f0-9]{32}$/.test(collection) || (unit && !/^unit-[a-f0-9]{64}$/.test(unit))) {
            notice("Liên kết tới phần nguồn không hợp lệ. Hãy chọn bộ tài liệu trong danh sách."); return;
        }
        await loadCollection(collection, unit || undefined);
        if (unit && state.collection?.id === collection && state.units[state.unitIndex]?.unit_id === unit) {
            const panel = byId("knowledgePanel"); panel.setAttribute("tabindex", "-1");
            panel.scrollIntoView({ block: "center" }); panel.focus({ preventScroll: true });
        }
    }
    boot();
})();
