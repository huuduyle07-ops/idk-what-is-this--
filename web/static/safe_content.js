/* SEC.UI.1: the sole untrusted rich-content -> DOM boundary.
 * Markdown is rendered by the existing server renderer; its HTML is UNTRUSTED.
 * Application markup is built by callers and is never passed through this policy.
 */
(function (global) {
    "use strict";

    const POLICY_VERSION = "sec_ui1_v1";
    // A private instance prevents unrelated libraries from changing our hooks/config.
    let purifier = null;
    try {
        if (typeof global.DOMPurify === "function") purifier = global.DOMPurify(global);
        if (purifier && purifier.isSupported) {
            purifier.addHook("uponSanitizeAttribute", (node, attribute) => {
                const tag = node.nodeName.toLowerCase();
                const name = attribute.attrName;
                const attributes = {
                    a: ["href", "title", "target"],
                    img: ["alt", "title"], // No src/srcset: images become text below.
                    h1: ["id"], h2: ["id"], h3: ["id"],
                    h4: ["id"], h5: ["id"], h6: ["id"],
                    ol: ["start"]
                };
                if (!(attributes[tag] || []).includes(name)) {
                    attribute.keepAttr = false;
                    return;
                }
                if (name === "href") {
                    try {
                        const url = new URL(attribute.attrValue, global.location.href);
                        if (!["http:", "https:"].includes(url.protocol)) attribute.keepAttr = false;
                    } catch (_) {
                        attribute.keepAttr = false;
                    }
                }
                if (name === "target" && !["_blank", "_self"].includes(attribute.attrValue)) {
                    attribute.keepAttr = false;
                }
            });
        }
    } catch (_) {
        purifier = null;
    }

    function renderText(target, source) {
        target.textContent = String(source ?? "");
    }

    function renderHTML(target, source, fallbackSource = source) {
        try {
            if (!purifier || !purifier.isSupported) throw new Error("Sanitizer unavailable");
            const fragment = purifier.sanitize(String(source ?? ""), {
                ALLOWED_TAGS: [
                    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
                    "strong", "b", "em", "i", "s", "del", "ul", "ol", "li",
                    "blockquote", "pre", "code", "a", "table", "caption",
                    "thead", "tbody", "tfoot", "tr", "th", "td", "img"
                ],
                ALLOWED_ATTR: ["href", "title", "target", "id", "alt", "start"],
                ALLOW_ARIA_ATTR: false,
                ALLOW_DATA_ATTR: false,
                SANITIZE_DOM: true,
                SANITIZE_NAMED_PROPS: true,
                RETURN_DOM_FRAGMENT: true
            });
            if (!fragment || fragment.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) {
                throw new Error("Sanitizer did not return a fragment");
            }
            // Only safe DOM operations follow sanitization, never HTML concatenation.
            fragment.querySelectorAll("img").forEach(img => {
                img.replaceWith(document.createTextNode(`[Image: ${img.getAttribute("alt") || "omitted"}]`));
            });
            fragment.querySelectorAll("a").forEach(link => {
                link.setAttribute("rel", "noopener noreferrer");
                const href = link.getAttribute("href");
                // DOMPurify prefixes heading IDs to prevent DOM clobbering.
                if (href && href.startsWith("#")) link.setAttribute("href", "#user-content-" + href.slice(1));
            });
            target.replaceChildren(fragment);
            return true;
        } catch (_) {
            const pre = document.createElement("pre");
            renderText(pre, fallbackSource);
            target.replaceChildren(pre);
            return false;
        }
    }

    global.CattusSafeContent = Object.freeze({ POLICY_VERSION, renderHTML, renderText });
})(window);
