/* Source pixels and provenance only; preparing an image never interprets it. */
(function () {
    "use strict";
    const byId = (id) => document.getElementById(id);
    const make = (tag, value, className) => { const item = document.createElement(tag); if (value != null) item.textContent = String(value); if (className) item.className = className; return item; };
    const positions = { page: "Trang PDF", slide: "Slide", paragraph: "Đoạn Word", table: "Bảng Word", image: "Ảnh" };
    const kinds = { page_render: "Trang kết xuất", slide_render: "Slide kết xuất", embedded_image: "Ảnh nhúng", source_image: "Ảnh từ nguồn" };
    function locationLabel(locator) { return locator && positions[locator.kind] ? positions[locator.kind] + " " + locator.index : "Vị trí nguồn chưa xác định"; }
    function printable(value) { return typeof value === "string" ? value : JSON.stringify(value); }
    function create({ api }) {
        let current = null;
        const panel = byId("sourceVisualsPanel"), gallery = byId("sourceVisualsGallery"), prepare = byId("prepareSourceVisuals"), refresh = byId("reloadSourceVisuals");
        function status(message) { byId("sourceVisualsStatus").textContent = message; }
        function controls() {
            const working = !!current?.working;
            prepare.disabled = !current || working || !current.record || current.record.status !== "unprepared";
            prepare.textContent = current?.retry ? "Thử chuẩn bị hình lần nữa" : "Chuẩn bị hình của phần này";
            refresh.disabled = !current || working;
            panel.setAttribute("aria-busy", String(working));
        }
        function checked(record, context) {
            if (!record || record.source_id !== context.sourceId || record.unit_id !== context.unitId || !["unprepared", "ready", "partial"].includes(record.status) || !Array.isArray(record.visuals) || !Array.isArray(record.warnings)) throw new Error("Phản hồi hình chưa khớp với phần nguồn đang mở.");
            return record;
        }
        function imageAddress(visual, context) {
            try {
                if (typeof visual.id !== "string" || !visual.id || typeof visual.image_url !== "string") return null;
                const address = new URL(visual.image_url, location.href);
                if (address.origin !== location.origin || address.pathname !== context.address + "/" + encodeURIComponent(visual.id) + "/image" || address.search || address.hash || address.username || address.password) return null;
                return address.href;
            } catch (_) { return null; }
        }
        function warnings(target, values) { target.replaceChildren(...(values || []).map((value) => make("li", value))); }
        function visualCard(visual, index, context) {
            const card = make("article", null, "source-visual-card"); card.dataset.visualId = visual.id;
            const toolbar = make("div", null, "source-visual-toolbar"), heading = make("div");
            heading.append(make("h4", (kinds[visual.kind] || "Hình nguồn") + " " + (index + 1)), make("p", locationLabel(visual.locator), "source-visual-position"));
            const zoom = make("button", "Xem ảnh ở 100%", "text-button"); zoom.type = "button"; zoom.disabled = true; zoom.setAttribute("aria-pressed", "false");
            toolbar.append(heading, zoom); card.append(toolbar);
            const viewport = make("div", null, "source-visual-viewport"); viewport.tabIndex = 0; viewport.setAttribute("role", "region"); viewport.setAttribute("aria-label", "Hình nguồn " + (index + 1) + "; cuộn khi xem kích thước gốc");
            const image = document.createElement("img"); image.className = "source-visual-image"; image.decoding = "async"; image.referrerPolicy = "same-origin";
            image.alt = (kinds[visual.kind] || "Hình nguồn") + " — " + context.sourceName + ", " + locationLabel(visual.locator) + ". Chưa được diễn giải tự động.";
            const loadStatus = make("p", "Đang tải hình…", "material-help source-visual-load"); loadStatus.setAttribute("role", "status");
            image.addEventListener("load", () => { if (current !== context || !card.isConnected) return; zoom.disabled = false; loadStatus.textContent = image.naturalWidth + " × " + image.naturalHeight + " px · " + (visual.mime_type || "Hình nguồn"); });
            image.addEventListener("error", () => { if (current !== context || !card.isConnected) return; zoom.disabled = true; loadStatus.textContent = "Chưa tải được hình này. Hãy Đọc hình đã lưu để thử lại."; });
            zoom.addEventListener("click", () => { const original = viewport.classList.toggle("is-original"); zoom.setAttribute("aria-pressed", String(original)); zoom.textContent = original ? "Vừa khung xem" : "Xem ảnh ở 100%"; });
            const address = imageAddress(visual, context);
            if (address) { image.src = address; viewport.append(image); } else loadStatus.textContent = "Đường dẫn hình chưa hợp lệ. Hãy Đọc hình đã lưu để kiểm tra lại.";
            card.append(viewport, loadStatus);
            const completeUnit = ["page_render", "slide_render", "source_image"].includes(visual.kind) && Array.isArray(visual.bbox) && visual.bbox.join(",") === "0,0,1,1";
            if (completeUnit) card.append(make("p", ({ page: "Toàn bộ trang PDF nguồn", slide: "Toàn bộ slide nguồn", image: "Toàn bộ ảnh nguồn" })[visual.locator?.kind] || "Toàn bộ phần nguồn", "source-visual-coverage"));
            if (visual.native_part != null || visual.bbox != null) {
                const details = make("details", null, "source-visual-details"); details.append(make("summary", "Thông tin nguồn chi tiết"));
                if (visual.native_part != null) details.append(make("p", "Vị trí trong file gốc: " + printable(visual.native_part), "source-visual-native"));
                if (visual.bbox != null) details.append(make("p", "Vùng nguồn: " + printable(visual.bbox), "source-visual-native"));
                card.append(details);
            }
            const notes = make("ul", null, "material-warnings"); warnings(notes, visual.warnings); card.append(notes);
            return card;
        }
        function adopt(record, context, recovered = false) {
            context.record = checked(record, context); context.retry = false;
            warnings(byId("sourceVisualsWarnings"), record.warnings); gallery.replaceChildren(...record.visuals.map((visual, index) => visualCard(visual, index, context)));
            byId("sourceVisualsEmpty").hidden = record.visuals.length > 0;
            if (record.status === "unprepared") {
                byId("sourceVisualsEmpty").textContent = "Chưa chuẩn bị bản hình cho phần này. Chọn nút bên trên khi bạn muốn xem.";
                status(recovered ? "Máy chủ chưa có bản hình đã lưu. Bạn có thể chủ động thử chuẩn bị lại." : "Chỉ đang đọc trạng thái đã lưu; chưa kết xuất hay phân tích hình.");
                context.retry = recovered;
            } else {
                byId("sourceVisualsEmpty").textContent = "Không có hình để hiển thị ở phần nguồn này. Đây không phải xác nhận nội dung đã được AI hiểu.";
                status((recovered ? "Đã tìm thấy bản hình đã lưu sau khi mất phản hồi. " : "") + (record.status === "partial" ? "Chỉ có một phần hình nguồn; xem lưu ý bên dưới." : record.visuals.length ? "Đã có " + record.visuals.length + " hình nguồn để đối chiếu." : "Đã kiểm tra phần nguồn; không có hình hiển thị."));
            }
            controls();
        }
        async function read(context, recovered = false, failureMessage = "") {
            const data = await api(context.address);
            if (current === context) {
                adopt(data.record, context, recovered);
                if (failureMessage && data.record.status === "unprepared") status(failureMessage + " " + byId("sourceVisualsStatus").textContent);
            }
        }
        async function refreshCurrent() {
            const context = current; if (!context || context.working) return;
            context.working = true; status("Đang đọc bản hình đã lưu…"); controls();
            try { await read(context); }
            catch (error) { if (current === context) status(error.message || "Chưa đọc được hình đã lưu. Hãy thử lại."); }
            finally { if (current === context) { context.working = false; controls(); } }
        }
        async function prepareCurrent() {
            const context = current;
            if (!context || context.working || context.record?.status !== "unprepared") return;
            context.working = true; context.retry = false; status("Đang chuẩn bị hình của phần này… Có thể tiếp tục xem phần nguồn khác."); controls();
            try {
                const data = await api(context.address, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
                if (current === context) adopt(data.record, context);
            } catch (error) {
                if (current !== context) return;
                if (error.ambiguous) {
                    status("Chưa nhận được xác nhận. Đang tìm bản hình đã lưu; chưa yêu cầu kết xuất thêm…");
                    try { await read(context, true, error.code && error.status ? error.message : ""); }
                    catch (_) { if (current === context) { context.record = null; status("Chưa xác định được kết quả. Chọn Đọc hình đã lưu trước khi thử chuẩn bị lại."); } }
                } else status(error.message || "Chưa chuẩn bị được hình nguồn. Bạn có thể thử lại.");
            } finally { if (current === context) { context.working = false; controls(); } }
        }
        function setContext(collection, unit, source) {
            const key = collection && unit && source ? collection.id + "/" + unit.unit_id + "/" + source.source_id : null;
            if (current?.key === key) return;
            current = null; gallery.replaceChildren(); warnings(byId("sourceVisualsWarnings"), []); byId("sourceVisualsEmpty").hidden = true;
            panel.hidden = !key;
            if (!key) { controls(); return; }
            const context = { key, sourceId: source.source_id, unitId: unit.unit_id, sourceName: (source.original_names || []).join(" · "), address: "/learn/api/materials/" + encodeURIComponent(collection.id) + "/units/" + encodeURIComponent(unit.unit_id) + "/visuals", record: null, working: true, retry: false };
            current = context; byId("sourceVisualsCitation").textContent = context.sourceName + " · " + locationLabel(unit.locator);
            status("Đang đọc trạng thái hình đã lưu…"); controls();
            read(context).catch((error) => { if (current === context) status(error.message || "Chưa đọc được trạng thái hình. Chọn Đọc hình đã lưu để thử lại."); }).finally(() => { if (current === context) { context.working = false; controls(); } });
        }
        prepare.addEventListener("click", prepareCurrent); refresh.addEventListener("click", refreshCurrent); controls();
        return { setContext };
    }
    window.LearningSourceVisuals = { create };
})();
