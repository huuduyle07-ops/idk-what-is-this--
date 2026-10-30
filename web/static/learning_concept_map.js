(function () {
    "use strict";
    const element = (tag, value, className) => {
        const item = document.createElement(tag);
        if (value !== undefined && value !== null) item.textContent = value;
        if (className) item.className = className;
        return item;
    };
    const button = (label, className) => { const item = element("button", label, className); item.type = "button"; return item; };
    const locationName = (location) => ({ page: "Page", slide: "Slide", paragraph: "Paragraph", table: "Table", image: "Image" }[location?.kind] || "Unit") + " " + (location?.index || "");

    function create(host, { onAsk, onNavigate }) {
        let collection = null, data = null, selected = null, sequence = 0, controller = null, blocked = false;
        const details = element("details", null, "concept-map");
        const summary = element("summary");
        summary.append(element("span", "Concept map"), element("small", "Khám phá khái niệm và nguồn liên quan"));
        const body = element("div", null, "concept-map-body");
        const intro = element("p", "Nút khái niệm lấy từ nhãn bạn đã gắn vào nguồn. Đường nét đứt chỉ các khái niệm cùng xuất hiện trong một phần nguồn; không phải quan hệ nguyên nhân hay thứ tự cần học.", "concept-map-note");
        const toolbar = element("div", null, "concept-map-toolbar");
        const searchLabel = element("label", "Find a concept or file");
        const search = element("input"); search.type = "search"; search.placeholder = "Semaphore, ISR…"; search.maxLength = 100;
        search.setAttribute("aria-label", "Find a concept or file"); searchLabel.append(search);
        const relatedLabel = element("label", null, "concept-map-check");
        const related = element("input"); related.type = "checkbox"; relatedLabel.append(related, document.createTextNode("Related only"));
        const reload = button("Refresh map", "quiet-button");
        toolbar.append(searchLabel, relatedLabel, reload);
        const status = element("p", "", "concept-map-status"); status.setAttribute("role", "status");
        const content = element("div", null, "concept-map-content");
        const viewport = element("div", null, "concept-map-viewport"); viewport.setAttribute("aria-label", "Concept map nodes");
        const canvas = element("div", null, "concept-map-canvas"); viewport.append(canvas);
        const detail = element("section", null, "concept-map-detail"); detail.setAttribute("aria-label", "Selected concept and sources");
        content.append(viewport, detail); body.append(intro, toolbar, status, content); details.append(summary, body); host.append(details); host.hidden = true;

        function cancel() { sequence += 1; controller?.abort(); controller = null; }
        function sourceLink(unit) {
            const link = element("a", "Mở nguồn và sửa nhãn khái niệm (tab mới)", "concept-map-source-link");
            link.href = "/learn/materials?collection=" + encodeURIComponent(collection.id) + "&unit=" + encodeURIComponent(unit.unit_id);
            link.target = "_blank"; link.rel = "noopener";
            link.addEventListener("click", (event) => { if (onNavigate && !onNavigate()) event.preventDefault(); });
            return link;
        }
        function renderDetail() {
            detail.replaceChildren();
            const item = data?.graph.nodes.find((entry) => entry.id === selected);
            if (!item) return;
            const kind = item.type === "concept" ? "USER-LINKED CONCEPT" : item.type === "source" ? "SOURCE FILE" : "LECTURE COLLECTION";
            const heading = element("h3", item.label); heading.tabIndex = -1;
            detail.append(element("p", kind, "concept-map-kind"), heading);
            if (item.type === "collection") {
                detail.append(element("p", data.concept_count + " concepts · " + data.source_count + " files", "concept-map-note"));
                detail.append(element("p", data.concept_count ? "Chọn một nút để xem nguồn và soạn câu hỏi tiếp theo." : "Chưa có nhãn khái niệm. Chọn file bên trái, mở một đoạn nguồn rồi gắn nhãn như Semaphore hoặc ISR. Nhấn Refresh map để xem liên kết vừa lưu.", "concept-map-note"));
            } else if (item.type === "concept") {
                const ask = button("Ask about “" + item.label + "”", "concept-map-ask"); ask.disabled = blocked;
                ask.addEventListener("click", () => onAsk("Explain " + item.label + "."));
                detail.append(ask, element("p", "Chỉ điền câu hỏi vào bản nháp; bạn quyết định gửi.", "concept-map-note"));
                const neighbors = data.graph.edges.filter((edge) => edge.type === "shared_source" && (edge.source === item.id || edge.target === item.id));
                if (neighbors.length) {
                    detail.append(element("p", "Shares a source passage with", "concept-map-kind"));
                    const list = element("div", null, "concept-map-neighbors");
                    neighbors.forEach((edge) => {
                        const other = data.graph.nodes.find((entry) => entry.id === (edge.source === item.id ? edge.target : edge.source));
                        if (!other) return;
                        const linked = button(other.label, "quiet-button"); linked.addEventListener("click", () => {
                            select(other.id); detail.querySelector("h3")?.focus({ preventScroll: true });
                        }); list.append(linked);
                    });
                    detail.append(list);
                }
            }
            const units = Array.isArray(item.metadata?.units) ? item.metadata.units : [];
            if (units.length) detail.append(element("p", "Source previews · " + units.length + " / " + (item.metadata.unit_count || units.length), "concept-map-kind"));
            units.forEach((unit) => {
                const card = element("article", null, "concept-map-unit");
                card.append(element("h4", unit.source_name + " · " + locationName(unit.locator)));
                card.append(element("p", unit.origin === "user_note" ? "Your image note · not image recognition" : "Extracted text · review against the original", "concept-map-note"));
                card.append(element("blockquote", unit.excerpt || "No readable text in this unit."), sourceLink(unit)); detail.append(card);
            });
        }
        function renderGraph(focusId) {
            canvas.replaceChildren();
            if (!data) return;
            const root = data.graph.nodes.find((item) => item.type === "collection");
            const connected = new Set([selected]);
            data.graph.edges.forEach((edge) => { if (edge.type === "shared_source") { if (edge.source === selected) connected.add(edge.target); if (edge.target === selected) connected.add(edge.source); } });
            const query = search.value.trim().toLocaleLowerCase();
            const children = data.graph.nodes.filter((item) => item.type !== "collection" && (!query || item.label.toLocaleLowerCase().includes(query)) && (!related.checked || selected === root?.id || connected.has(item.id)));
            const nodes = root ? [root, ...children] : children;
            const height = Math.max(180, nodes.length * 74 + 20);
            canvas.style.height = height + "px";
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("viewBox", "0 0 360 " + height); svg.setAttribute("aria-hidden", "true"); svg.classList.add("concept-map-lines");
            function line(path, className) { const shape = document.createElementNS(svg.namespaceURI, "path"); shape.setAttribute("d", path); shape.setAttribute("class", className); svg.append(shape); }
            nodes.forEach((item, index) => {
                const top = 14 + index * 74;
                if (index) line("M 32 65 V " + (top + 25) + " H 54", "map-branch");
                const control = button("", "concept-map-node " + (item.type === "collection" ? "map-root" : item.type === "concept" ? "map-concept" : "map-source"));
                control.dataset.nodeId = item.id; control.dataset.nodeType = item.type; control.style.top = top + "px";
                control.title = item.label; control.setAttribute("aria-label", (item.type === "concept" ? "Concept: " : item.type === "source" ? "File: " : "Collection: ") + item.label);
                control.setAttribute("aria-pressed", String(item.id === selected));
                if (connected.has(item.id) && item.id !== selected) control.classList.add("map-connected");
                control.append(element("span", item.label), element("small", item.type === "collection" ? "Collection" : item.type === "concept" ? "Concept · " + (item.metadata?.unit_count || 0) + " passages" : "File"));
                control.addEventListener("click", () => select(item.id, item.id)); canvas.append(control);
            });
            const positions = new Map(nodes.map((item, index) => [item.id, 39 + index * 74]));
            data.graph.edges.filter((edge) => edge.type === "shared_source" && (edge.source === selected || edge.target === selected)).forEach((edge) => {
                if (!positions.has(edge.source) || !positions.has(edge.target)) return;
                const a = positions.get(edge.source), b = positions.get(edge.target);
                line("M 310 " + a + " C 350 " + a + " 350 " + b + " 310 " + b, "map-shared");
            });
            canvas.prepend(svg);
            if (!children.length) {
                const empty = element("p", "No matching nodes. Try another filter.", "concept-map-empty"); empty.style.top = "105px"; canvas.append(empty);
            }
            if (focusId) [...canvas.querySelectorAll("button")].find((item) => item.dataset.nodeId === focusId)?.focus({ preventScroll: true });
        }
        function select(id, focusId) { selected = id; renderGraph(focusId); renderDetail(); }
        async function load() {
            if (!collection || !details.open) return;
            cancel(); const current = sequence, id = collection.id;
            controller = new AbortController(); const active = controller;
            const timeout = setTimeout(() => active.abort(), 15000);
            reload.disabled = true; status.textContent = "Đang đọc bản đồ từ các liên kết đã lưu…"; content.hidden = true;
            try {
                const response = await fetch("/learn/api/materials/" + encodeURIComponent(id) + "/map", { credentials: "same-origin", cache: "no-store", signal: active.signal });
                const result = await response.json();
                if (current !== sequence || collection?.id !== id) return;
                const value = result.map;
                if (!response.ok || !result.ok || value?.collection?.id !== id || !Array.isArray(value.graph?.nodes) || !Array.isArray(value.graph?.edges)
                    || value.graph.nodes.length > 41 || value.graph.edges.length > 110
                    || value.graph.nodes.some((item) => !item || typeof item.id !== "string" || typeof item.label !== "string" || !["collection", "concept", "source"].includes(item.type))) throw new Error("Invalid map");
                data = value;
                if (!data.graph.nodes.some((item) => item.id === selected)) selected = data.graph.nodes.find((item) => item.type === "collection")?.id;
                status.textContent = value.truncated ? "Bản đồ đang hiển thị một phần liên kết để giữ giao diện gọn. Các đoạn xem trước cũng có giới hạn." : "Bản đồ từ cấu trúc tài liệu và nhãn bạn đã gắn. Không gọi AI khi mở hoặc chọn nút.";
                renderGraph(); renderDetail(); content.hidden = false;
            } catch (_) {
                if (current === sequence) { data = null; selected = null; canvas.replaceChildren(); detail.replaceChildren(); status.textContent = "Chưa đọc được bản đồ. Nhấn Refresh map để thử lại."; }
            } finally { clearTimeout(timeout); if (current === sequence) { reload.disabled = false; controller = null; } }
        }
        details.addEventListener("toggle", () => { if (details.open && !data) load(); });
        reload.addEventListener("click", load);
        search.addEventListener("input", () => renderGraph()); related.addEventListener("change", () => renderGraph());
        return {
            setCollection(value) {
                if ((collection?.id || null) === (value?.id || null)) return;
                cancel(); collection = value || null; data = null; selected = null; search.value = ""; related.checked = false;
                details.open = false; host.hidden = !collection; canvas.replaceChildren(); detail.replaceChildren(); content.hidden = true; status.textContent = ""; reload.disabled = false;
            },
            setBlocked(value) { blocked = !!value; detail.querySelectorAll(".concept-map-ask").forEach((item) => { item.disabled = blocked; }); },
        };
    }
    window.LearningConceptMap = Object.freeze({ create });
})();
