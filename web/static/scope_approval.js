"use strict";
document.getElementById("scopeApprovalForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const decision = event.submitter?.value;
    if (!decision) return;
    const body = new URLSearchParams(new FormData(form));
    body.set("decision", decision);
    if (decision !== "request_scope_revision") body.set("note", "");
    for (const button of form.querySelectorAll("button")) button.disabled = true;
    try {
        const response = await fetch(form.action, {method: "POST", body});
        const result = await response.json();
        if (response.ok) {
            window.location.assign(`/session/${encodeURIComponent(body.get("session_id"))}`);
            return;
        }
        document.getElementById("scopeApprovalStatus").textContent = `Decision unavailable: ${result.code || result.status}`;
    } catch (_) {
        document.getElementById("scopeApprovalStatus").textContent = "Decision submission interrupted. Reload to check the recorded decision before retrying.";
    }
    for (const button of form.querySelectorAll("button")) button.disabled = false;
});
