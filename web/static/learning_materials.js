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
        sourceIndex: 0, note: null };

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
        if (noteDirty() || (state.note && state.note.conflict)) {
            notice("Mô tả ảnh còn thay đổi chưa được xác nhận. Hãy lưu hoặc chọn Bỏ thay đổi chưa lưu trước khi chuyển nguồn hay nhập bộ mới.");
            byId("imageDescriptionInput").focus(); return false;
        }
        return true;
    }
    function controls() {
        const blocked = state.busy || state.scanning || state.detailLoading || noteBusy();
        ["chooseFilesButton", "chooseFolderButton", "materialsFilesInput", "materialsFolderInput", "materialsTitleInput"].forEach((id) => { byId(id).disabled = blocked; });
        byId("importMaterialsButton").disabled = blocked || !state.queue.length || !byId("materialsTitleInput").value.trim();
        byId("refreshMaterialsButton").disabled = state.listBusy || state.busy;
        byId("materialsDropzone").setAttribute("aria-busy", String(blocked));
        byId("materialsImportForm").setAttribute("aria-busy", String(state.busy));
        byId("selectedFiles").querySelectorAll("button").forEach((button) => { button.disabled = blocked; });
        byId("materialSourceSelect").disabled = state.busy || state.detailLoading || noteBusy();
        byId("materialsCollections").querySelectorAll("button").forEach((button) => { button.disabled = state.busy || state.detailLoading || noteBusy(); });
        byId("imageDescriptionInput").disabled = state.busy || state.detailLoading || noteBusy();
        byId("saveDescriptionButton").disabled = blocked || !state.note || !noteDirty() || state.note.conflict;
        byId("discardDescriptionButton").disabled = blocked || !state.note || (!noteDirty() && !state.note.conflict);
        byId("reloadDescriptionButton").disabled = blocked || !state.note;
        byId("useSavedDescriptionButton").disabled = blocked || !state.note || !state.note.latest;
        byId("keepDraftDescriptionButton").disabled = blocked || !state.note || !state.note.latest;
        byId("imageDescriptionForm").setAttribute("aria-busy", String(noteBusy()));
        text("descriptionCount", byId("imageDescriptionInput").value.length.toLocaleString("vi-VN") + " / 4.000 ký tự");
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
        if (state.busy || state.scanning || state.detailLoading || noteBusy()) return;
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
        const labels = { page: "Trang PDF", slide: "Slide", paragraph: "Đoạn Word", table: "Bảng Word" };
        return (labels[unit.locator.kind] || "Phần nguồn") + " " + unit.locator.index;
    }
    function renderUnit() {
        const unit = state.units[state.unitIndex];
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
            saving: false, loading: false, conflict: false, latest: null };
        byId("imageDescriptionInput").value = state.note.baseText;
        show("descriptionConflict", false); show("latestDescriptionPanel", false);
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
        byId("imageZoomButton").disabled = !address;
        if (address) {
            text("imageLoadStatus", "Đang tải ảnh nguồn…");
            image.src = address; image.hidden = false;
        } else text("imageLoadStatus", "Chưa có đường dẫn ảnh hợp lệ để xem. Hãy tải lại bộ tài liệu.");
        controls();
    }
    function selectSource(event) {
        if (event && !guardNote()) { byId("materialSourceSelect").value = String(state.sourceIndex); return; }
        const sources = state.collection ? state.collection.sources || [] : [];
        state.sourceIndex = Number(byId("materialSourceSelect").value);
        const source = sources[state.sourceIndex];
        state.units = source ? (state.collection.units || []).filter((unit) => unit.source_id === source.source_id) : [];
        state.unitIndex = 0;
        const paths = source ? (source.upload_paths && source.upload_paths.length ? source.upload_paths : source.original_names || []) : [];
        const isImage = !!source && !!source.image;
        text("sourceDetails", source ? paths.join(" · ") + " — " + (isImage ? "Ảnh nguồn" : source.unit_count + " phần nguồn") + " · " + statusLabel(source.status) : "Chưa có file nguồn.");
        listWarnings("sourceWarnings", source ? source.warnings : []);
        show("imagePanel", isImage); show("textSourcePanel", !isImage);
        if (isImage) renderImage(source);
        else { state.note = null; byId("materialImage").removeAttribute("src"); renderUnit(); controls(); }
    }
    function displayCollection(collection, focus) {
        state.collection = collection; show("materialPreview", true);
        text("previewHeading", collection.title); text("collectionStatus", statusLabel(collection.status));
        const options = (collection.sources || []).map((source, index) => {
            const option = node("option", (source.original_names || [source.format]).join(" · "));
            option.value = String(index); return option;
        });
        byId("materialSourceSelect").replaceChildren(...options);
        selectSource(); renderCollections();
        if (focus) byId("previewHeading").focus();
    }
    async function loadCollection(id) {
        if (state.busy || state.detailLoading || !guardNote()) return;
        const request = ++state.detailRequest; clearNotice();
        state.detailLoading = true; controls();
        byId("materialPreview").setAttribute("aria-busy", "true");
        announce("Đang mở bản trích tài liệu…");
        try {
            const data = await api("/learn/api/materials/" + encodeURIComponent(id));
            if (request === state.detailRequest) { displayCollection(data.collection, true); announce("Đã mở bản trích, cần đối chiếu file gốc."); }
        } catch (error) { if (request === state.detailRequest) notice(error.status === 401 || error.status === 403 ? errorText(error) : "Chưa mở được bộ tài liệu này. Chọn lại bộ tài liệu để thử tiếp."); }
        finally { if (request === state.detailRequest) { state.detailLoading = false; byId("materialPreview").setAttribute("aria-busy", "false"); controls(); } }
    }
    async function importMaterials(event) {
        event.preventDefault();
        if (state.busy || state.scanning || state.detailLoading || !state.queue.length || !byId("materialsTitleInput").value.trim() || !guardNote()) return;
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
    byId("materialSourceSelect").addEventListener("change", selectSource);
    byId("previousUnitButton").addEventListener("click", () => { if (state.unitIndex > 0) { state.unitIndex -= 1; renderUnit(); } });
    byId("nextUnitButton").addEventListener("click", () => { if (state.unitIndex + 1 < state.units.length) { state.unitIndex += 1; renderUnit(); } });
    byId("unitNumberInput").addEventListener("change", (event) => {
        const value = Number(event.target.value);
        if (Number.isInteger(value) && value >= 1 && value <= state.units.length) state.unitIndex = value - 1;
        renderUnit();
    });
    controls(); loadCollections();
})();
