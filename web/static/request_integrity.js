/* AUTH.WEB.1: the single owner of browser request-integrity transport.
 *
 * Same-origin POST/PUT/PATCH/DELETE fetches carry the server-issued CSRF token
 * (X-CSRF-Token) with same-origin credentials; same-origin POST forms carry it
 * as a csrf_token field. Cross-origin and safe-method requests pass through
 * untouched, so the token never leaves this origin. WEB_AUTH_TOKEN is typed by
 * the user, sent once in the POST body of /auth/login and never kept, rendered
 * or put in a URL. Rejected requests are reported, never retried.
 */
(function (global) {
    "use strict";

    const nativeFetch = global.fetch.bind(global);
    const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
    const CSRF_HEADER = "X-CSRF-Token";
    const CSRF_FIELD = "csrf_token";
    const REJECTION_HEADER = "X-CATTUS-Request-Integrity";
    const LOGIN_URL = "/auth/login";
    const SESSION_URL = "/auth/session";
    const ORIGIN_CODES = new Set([
        "origin_missing", "origin_null", "origin_malformed", "origin_ambiguous", "origin_not_allowed"
    ]);
    const MESSAGES = {
        signed_out: "This server requires WEB_AUTH_TOKEN before changes. Sign in once for this browser session; the token goes to the server and this page does not keep it.",
        signed_in: "Signed in for this browser session.",
        auth_required: "Sign-in required: the last action was not performed. Sign in, then retry it.",
        browser_session_invalid: "The browser session is no longer valid (server restart, token change or expiry). The last action was not performed.",
        browser_session_missing: "This page had no browser session. The last action was not performed; retry it.",
        csrf_missing: "The request protection token was missing. The last action was not performed; retry it.",
        csrf_invalid: "The request protection token was stale and has been refreshed. The last action was not performed; retry it.",
        csrf_ambiguous: "The request carried more than one protection token. The last action was not performed.",
        origin: "The last action was not performed: this page's address (scheme, host and port) is not an allowed origin for this server. Open the app at its configured address, or add this exact origin to WEB_ALLOWED_ORIGINS.",
        web_auth_token_invalid: "Sign-in failed: the token was not accepted.",
        sign_in_required_for_form: "Sign in before submitting. The form was not submitted.",
        unavailable: "The browser session could not be refreshed. Reload the page."
    };
    let panel = null;

    function metaElement(name) {
        return document.querySelector(`meta[name="${name}"]`);
    }

    function meta(name) {
        const element = metaElement(name);
        return element ? element.getAttribute("content") || "" : "";
    }

    function setMeta(name, value) {
        const element = metaElement(name);
        if (element) element.setAttribute("content", String(value || ""));
    }

    function csrfToken() {
        return meta("cattus-csrf-token");
    }

    function authState() {
        return meta("cattus-auth-state");
    }

    function sameOrigin(url) {
        try {
            return new URL(url, global.location.href).origin === global.location.origin;
        } catch (_) {
            return false;
        }
    }

    function requestUrl(input) {
        return input instanceof Request ? input.url : String(input);
    }

    function requestMethod(input, init) {
        if (init && init.method) return String(init.method).toUpperCase();
        return input instanceof Request ? input.method.toUpperCase() : "GET";
    }

    // Returns the (input, init) to send; only protected requests are changed.
    function prepare(input, init) {
        if (!UNSAFE_METHODS.has(requestMethod(input, init)) || !sameOrigin(requestUrl(input))) {
            return [input, init];
        }
        const source = init && init.headers !== undefined
            ? init.headers
            : (input instanceof Request ? input.headers : undefined);
        const headers = new Headers(source);
        headers.set(CSRF_HEADER, csrfToken());
        return [input, Object.assign({}, init, { headers, credentials: "same-origin" })];
    }

    async function protectedFetch(input, init) {
        const [preparedInput, preparedInit] = prepare(input, init);
        const response = await nativeFetch(preparedInput, preparedInit);
        if (preparedInit !== init) {
            const code = response.headers.get(REJECTION_HEADER);
            if (code) handleRejection(code);
        }
        return response;
    }

    async function refreshSession() {
        const response = await nativeFetch(SESSION_URL, { credentials: "same-origin", cache: "no-store" });
        if (!response.ok) throw new Error("browser session refresh failed");
        const data = await response.json();
        setMeta("cattus-csrf-token", data.csrf_token);
        setMeta("cattus-auth-state", data.auth_state);
        return data;
    }

    function handleRejection(code) {
        global.dispatchEvent(new CustomEvent("cattus:request-integrity", { detail: { code } }));
        if (ORIGIN_CODES.has(code)) {
            showPanel(code, MESSAGES.origin);
            return;
        }
        refreshSession().then(
            () => showPanel(code, MESSAGES[code] || MESSAGES.browser_session_invalid),
            () => showPanel("unavailable", MESSAGES.unavailable)
        );
    }

    async function signIn(token) {
        await refreshSession();
        const body = new URLSearchParams();
        body.set("web_auth_token", token);
        const response = await protectedFetch(LOGIN_URL, { method: "POST", body });
        const rejection = response.headers.get(REJECTION_HEADER);
        if (rejection) return { ok: false, code: rejection, handled: true };
        const data = await response.json().catch(() => ({}));
        if (response.ok && data.authenticated === true) {
            setMeta("cattus-csrf-token", data.csrf_token);
            setMeta("cattus-auth-state", data.auth_state);
            return { ok: true };
        }
        return { ok: false, code: String(data.error_code || "web_auth_token_invalid"), handled: false };
    }

    function renderText(target, text) {
        if (global.CattusSafeContent) global.CattusSafeContent.renderText(target, text);
        else target.textContent = String(text);
    }

    function signInForm() {
        const form = document.createElement("form");
        form.method = "post";
        form.action = LOGIN_URL;
        form.dataset.cattusSignIn = "true";
        Object.assign(form.style, { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", margin: "8px 0" });
        const label = document.createElement("label");
        label.htmlFor = "cattusAuthToken";
        renderText(label, "WEB_AUTH_TOKEN");
        const input = document.createElement("input");
        input.type = "password";
        input.id = "cattusAuthToken";
        input.name = "web_auth_token";
        input.autocomplete = "current-password";
        input.required = true;
        const button = document.createElement("button");
        button.type = "submit";
        button.id = "cattusAuthSignIn";
        renderText(button, "Sign in");
        form.append(label, input, button);
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const token = input.value;
            button.disabled = true;
            try {
                const result = await signIn(token);
                input.value = "";
                if (result.ok) showPanel("signed_in", MESSAGES.signed_in);
                else if (!result.handled) showPanel(result.code, MESSAGES[result.code] || MESSAGES.web_auth_token_invalid);
            } catch (_) {
                showPanel("unavailable", MESSAGES.unavailable);
            } finally {
                button.disabled = false;
            }
        });
        return form;
    }

    function ensurePanel() {
        if (panel && panel.isConnected) return panel;
        panel = document.createElement("section");
        panel.id = "cattusAuthPanel";
        panel.setAttribute("aria-live", "polite");
        panel.setAttribute("aria-label", "Browser sign-in");
        Object.assign(panel.style, {
            border: "1px solid var(--color-warning, #f59e0b)",
            background: "var(--color-warning-bg, #422006)",
            color: "var(--color-text, #fafafa)",
            borderRadius: "var(--radius-md, 6px)",
            padding: "10px 14px",
            margin: "0 0 16px"
        });
        const host = document.querySelector("main.main") || document.body;
        host.prepend(panel);
        return panel;
    }

    function showPanel(reason, message) {
        if (!document.body) return;
        const element = ensurePanel();
        const state = authState();
        element.replaceChildren();
        const text = document.createElement("p");
        text.style.margin = "0";
        renderText(text, message);
        element.append(text);
        if (state === "signed_out") element.append(signInForm());
        const dismiss = document.createElement("button");
        dismiss.type = "button";
        renderText(dismiss, "Dismiss");
        dismiss.addEventListener("click", () => { element.hidden = true; });
        element.append(dismiss);
        element.dataset.state = state;
        element.dataset.reason = reason;
        element.hidden = false;
    }

    function ensureFormToken(form) {
        if (!(form instanceof HTMLFormElement)) return;
        if (String(form.method).toLowerCase() !== "post" || !sameOrigin(form.action)) return;
        let field = form.querySelector(`input[type="hidden"][name="${CSRF_FIELD}"]`);
        if (!field) {
            field = document.createElement("input");
            field.type = "hidden";
            field.name = CSRF_FIELD;
            form.append(field);
        }
        field.value = csrfToken();
    }

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        ensureFormToken(form);
        if (form.dataset.cattusSignIn === "true") return;
        const protectedForm = String(form.method).toLowerCase() === "post" && sameOrigin(form.action);
        if (protectedForm && authState() === "signed_out") {
            event.preventDefault();
            showPanel("sign_in_required_for_form", MESSAGES.sign_in_required_for_form);
        }
    }, true);

    function initialize() {
        document.querySelectorAll("form").forEach(ensureFormToken);
        if (authState() === "signed_out") showPanel("signed_out", MESSAGES.signed_out);
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialize);
    else initialize();

    global.fetch = protectedFetch;
    global.CattusRequestIntegrity = Object.freeze({
        fetch: protectedFetch,
        prepare,
        csrfToken,
        authState,
        refreshSession,
        signIn,
        ensureFormToken
    });
})(window);
