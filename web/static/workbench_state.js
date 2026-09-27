/* UX.STATE.1: the single owner of frontend workflow state.
 *
 * Navigation and presentation truth only: which repository context the page is
 * in, which workspace mode is active and what each mode is configured to run,
 * which request owns each result slot, which candidate is displayed and where
 * it came from, which run is displayed and whether its context may enter a new
 * request (UX.CONTEXT.1), and the outcome of the last candidate action. Backend
 * authority (human Apply authorization, candidate fingerprints, Undo receipts,
 * Dream review bindings) is transported unchanged and decided by the server. A
 * response reaches the page only while the context that sent it is current.
 *
 * No transport, storage or DOM lives here: request_integrity.js owns fetch,
 * request protection and sign-in, and the page subscribes to snapshots and
 * renders them.
 */
(function (global) {
    "use strict";

    const STATUS = Object.freeze({ IDLE: "idle", PENDING: "pending", SUCCEEDED: "succeeded", FAILED: "failed" });
    const EXECUTION_OPTIONS = Object.freeze({
        mode: Object.freeze(["retrieve", "deep", "control", "full"]),
        apply_policy: Object.freeze(["ask", "auto", "plan"]),
    });
    // Product contract: the server runs web_mode=chat as "retrieve" and Chat
    // never applies. Instant keeps whatever the user last chose.
    const CHAT_EXECUTION = Object.freeze({ mode: "retrieve", apply_policy: "plan" });
    const INSTANT_DEFAULT = Object.freeze({ mode: "retrieve", apply_policy: "ask" });

    // Result slots. Requests of one slot compete for it; different slots never
    // supersede each other. A "latest" slot belongs to its newest dispatched
    // request; a "single" slot refuses a second request while one is pending.
    // Candidate-bound requests also lose ownership when the candidate changes.
    // A requestRun kind transports the run context bound to the current
    // repository context, captured in its ticket (UX.CONTEXT.1).
    const KINDS = Object.freeze({
        generate: Object.freeze({ slot: "candidate", concurrency: "latest", candidate: false, action: true, requestRun: true }),
        candidates: Object.freeze({ slot: "candidates", concurrency: "latest", candidate: false, action: false, requestRun: true }),
        test: Object.freeze({ slot: "review", concurrency: "single", candidate: true, action: true }),
        apply: Object.freeze({ slot: "review", concurrency: "single", candidate: true, action: true, mutation: true }),
        undo: Object.freeze({ slot: "review", concurrency: "single", candidate: true, action: true, mutation: true }),
        critique: Object.freeze({ slot: "critique", concurrency: "latest", candidate: true, action: false }),
        upload: Object.freeze({ slot: "repository", concurrency: "latest", candidate: false, action: false }),
    });
    const SLOTS = Object.freeze(["repository", "candidate", "candidates", "review", "critique"]);
    const IDLE_SLOT = Object.freeze({ owner: null, kind: null, status: STATUS.IDLE });
    const REFUSALS = Object.freeze({
        no_candidate: "No candidate is displayed for the current repository.",
        action_pending: "Another action is already pending for this candidate; wait for its result.",
        mutation_pending: "An Apply or Undo is still pending; wait for its result before replacing the candidate.",
        not_listed: "That candidate list no longer belongs to the current repository.",
    });
    const ACTION_LABELS = Object.freeze({
        generate: Object.freeze({ pending: "generate pending", succeeded: "generated", failed: "generate failed" }),
        select: Object.freeze({ succeeded: "candidate selected" }),
        test: Object.freeze({ pending: "test pending", succeeded: "tested", failed: "test failed" }),
        apply: Object.freeze({ pending: "apply pending", succeeded: "applied", failed: "apply failed" }),
        undo: Object.freeze({ pending: "undo pending", succeeded: "undone", failed: "undo failed" }),
    });
    const SHA256_HEX = /^[0-9a-f]{64}$/;
    // The displayed run. A "server" run was rendered for this page load; its
    // contextGeneration is the repository context generation it belongs to, or
    // null when it belongs to none.
    const NO_RUN = Object.freeze({ sessionId: "", repository: "", source: "none", contextGeneration: null, context: "" });

    let hydrated = false;
    let sequence = 0;
    let contextGeneration = 0;
    let lastInvalidation = null;
    let repository = "";
    let run = NO_RUN;
    let mode = "instant";
    let instant = INSTANT_DEFAULT;
    let candidate = null;
    let candidates = null;
    let review = null;
    let action = idleAction();
    let slots = idleSlots();
    let ignored = 0;
    let lastIgnored = null;
    const listeners = new Set();

    function idleAction() {
        return Object.freeze({ kind: null, status: STATUS.IDLE, code: null, message: null, requestId: null });
    }

    function idleSlots() {
        const next = {};
        for (const name of SLOTS) next[name] = IDLE_SLOT;
        return next;
    }

    function text(value) {
        return typeof value === "string" ? value : "";
    }

    function normalizeRepository(value) {
        return text(value).trim();
    }

    function nextId() {
        sequence += 1;
        return sequence;
    }

    // -- snapshots ------------------------------------------------------------

    function execution() {
        const config = mode === "chat" ? CHAT_EXECUTION : instant;
        return Object.freeze({ web_mode: mode, mode: config.mode, apply_policy: config.apply_policy });
    }

    function snapshot() {
        return Object.freeze({
            hydrated,
            contextGeneration,
            repository,
            run,
            requestRun: requestRun(),
            mode,
            instant,
            execution: execution(),
            candidate,
            candidates,
            review,
            action,
            slots: Object.freeze({ ...slots }),
        });
    }

    function subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
    }

    function notify() {
        const view = snapshot();
        for (const listener of listeners) {
            try {
                listener(view);
            } catch (error) {
                // A renderer failure is still reported, but never undoes a transition.
                setTimeout(() => { throw error; }, 0);
            }
        }
    }

    function telemetry() {
        return Object.freeze({
            requestSequence: sequence,
            contextGeneration,
            lastInvalidation,
            ignoredStaleResponses: ignored,
            lastIgnored,
        });
    }

    // -- candidate provenance -------------------------------------------------

    function parsedPayload(candidateText) {
        const body = text(candidateText).trim();
        if (!body) return null;
        try {
            const payload = JSON.parse(body);
            return payload && typeof payload === "object" && !Array.isArray(payload) ? { body, payload } : null;
        } catch (_) {
            return null;
        }
    }

    function backendIdentity(payload) {
        // Transported as issued by the server (EXEC.APPROVAL.LIVE.1); never computed here.
        const receipt = payload.human_apply_review;
        const fingerprint = receipt && typeof receipt === "object" ? receipt.candidate_fingerprint : null;
        return typeof fingerprint === "string" && fingerprint ? fingerprint : null;
    }

    function candidateRecord(candidateText, source, requestId) {
        const parsed = parsedPayload(candidateText);
        if (!parsed) return null;
        return Object.freeze({
            id: nextId(),
            source,
            requestId,
            contextGeneration,
            repository,
            runSessionId: run.sessionId,
            backendCandidateFingerprint: backendIdentity(parsed.payload),
            text: parsed.body,
            payload: parsed.payload,
        });
    }

    function replaceCandidate(next) {
        candidate = next;
        review = null;
        slots = { ...slots, review: IDLE_SLOT, critique: IDLE_SLOT };
    }

    function refreshCandidate(candidateText) {
        const parsed = candidate ? parsedPayload(candidateText) : null;
        if (!parsed) return;
        // The server's updated payload (for example an Undo receipt) describes the
        // same candidate: its identity and provenance stay unchanged.
        candidate = Object.freeze({
            ...candidate,
            backendCandidateFingerprint: backendIdentity(parsed.payload),
            text: parsed.body,
            payload: parsed.payload,
        });
    }

    // -- repository context ---------------------------------------------------

    function invalidateContext(reason) {
        contextGeneration += 1;
        lastInvalidation = reason;
        candidate = null;
        candidates = null;
        review = null;
        action = idleAction();
        slots = idleSlots();
    }

    // Generic hook: any change of context (a repository today; for example a
    // future sign-in) ends every pending ownership and drops context-bound state.
    function invalidate(reason) {
        invalidateContext(text(reason) || "context_invalidated");
        notify();
    }

    function setRepository(value) {
        const next = normalizeRepository(value);
        if (next === repository) return false;
        repository = next;
        invalidateContext("repository_changed");
        notify();
        return true;
    }

    // -- run context (UX.CONTEXT.1) ---------------------------------------------

    // Hydration binds a server-rendered run only to the repository context the
    // server recorded it for.
    function serverRun(session) {
        const sessionId = text(session.sessionId);
        if (!sessionId) return NO_RUN;
        const runRepository = normalizeRepository(session.repository);
        return Object.freeze({
            sessionId,
            repository: runRepository,
            source: "server",
            contextGeneration: runRepository === repository ? contextGeneration : null,
            context: text(session.context),
        });
    }

    // A displayed run stays viewable, but its context may enter a new request
    // only while the run belongs to the current repository context generation.
    // Generations never repeat, so after any repository change (even typing the
    // same path back) continuing from a run takes an explicit selection of it.
    function requestRun() {
        return run.source === "server" && run.contextGeneration === contextGeneration ? run : null;
    }

    // -- workspace mode and per-mode execution configuration --------------------

    function setMode(next) {
        mode = next === "chat" ? "chat" : "instant";
        notify();
        return mode;
    }

    function setExecutionOption(name, value) {
        const allowed = EXECUTION_OPTIONS[name];
        if (!allowed) throw new TypeError("Unknown execution option: " + name);
        // Chat's execution is fixed by the product contract, so only Instant edits persist.
        const accepted = mode === "instant" && allowed.includes(value);
        if (accepted && instant[name] !== value) instant = Object.freeze({ ...instant, [name]: value });
        notify();
        return accepted;
    }

    // -- requests and result-slot ownership ---------------------------------------

    function refusal(kind, code) {
        return Object.freeze({ refused: true, kind, code, message: REFUSALS[code] });
    }

    function mutationPending() {
        const slot = slots.review;
        return slot.status === STATUS.PENDING && Boolean(KINDS[slot.kind] && KINDS[slot.kind].mutation);
    }

    function blocked(kind) {
        const spec = KINDS[kind];
        if (!spec) throw new TypeError("Unknown workbench request kind: " + kind);
        if (spec.candidate && !candidate) return refusal(kind, "no_candidate");
        if (spec.concurrency === "single" && slots[spec.slot].status === STATUS.PENDING) {
            return refusal(kind, "action_pending");
        }
        if (kind === "generate" && mutationPending()) return refusal(kind, "mutation_pending");
        return null;
    }

    // CONTROL.BOOTSTRAP.1: a requestRun kind without an eligible run is a fresh
    // task, so its ticket snapshots the task text exactly as typed at dispatch
    // (never parsed here) and a later edit cannot change the in-flight request.
    // A continuation ticket carries its run context and no task.
    function begin(kind, inputs) {
        const refused = blocked(kind);
        if (refused) return refused;
        const spec = KINDS[kind];
        const ticket = Object.freeze({
            refused: false,
            id: nextId(),
            kind,
            slot: spec.slot,
            contextGeneration,
            repository,
            candidateId: spec.candidate ? candidate.id : null,
            requestRun: spec.requestRun ? requestRun() : null,
            task: spec.requestRun && !requestRun() ? text(inputs && inputs.task) : null,
            execution: execution(),
        });
        slots = { ...slots, [spec.slot]: Object.freeze({ owner: ticket.id, kind, status: STATUS.PENDING }) };
        if (spec.action) {
            action = Object.freeze({ kind, status: STATUS.PENDING, code: null, message: null, requestId: ticket.id });
        }
        notify();
        return ticket;
    }

    function staleReason(ticket) {
        if (!ticket || ticket.refused !== false || !KINDS[ticket.kind]) return "not_a_request";
        if (ticket.contextGeneration !== contextGeneration) return "context_changed";
        if (ticket.candidateId !== null && (!candidate || candidate.id !== ticket.candidateId)) {
            return "candidate_changed";
        }
        const slot = slots[ticket.slot];
        if (slot.owner !== ticket.id) return "superseded";
        if (slot.status !== STATUS.PENDING) return "already_settled";
        return null;
    }

    function reviewRecord(kind, requestId, status, output) {
        return Object.freeze({
            id: nextId(),
            candidateId: candidate ? candidate.id : null,
            kind,
            requestId,
            status,
            output: Object.freeze({ ...output }),
        });
    }

    // Accept a response only for the context, candidate and slot owner that sent
    // it. A stale response changes nothing but bounded debug telemetry.
    function settle(ticket, outcome) {
        const reason = staleReason(ticket);
        if (reason) {
            ignored += 1;
            lastIgnored = Object.freeze({
                requestId: ticket && Number.isInteger(ticket.id) ? ticket.id : null,
                kind: ticket && typeof ticket.kind === "string" ? ticket.kind : null,
                reason,
            });
            return Object.freeze({ accepted: false, reason });
        }
        const result = outcome && typeof outcome === "object" ? outcome : {};
        const spec = KINDS[ticket.kind];
        let status = result.status === STATUS.SUCCEEDED ? STATUS.SUCCEEDED : STATUS.FAILED;
        let code = status === STATUS.FAILED ? text(result.code) || ticket.kind + "_failed" : null;
        let message = text(result.message) || null;

        if (ticket.kind === "generate" && status === STATUS.SUCCEEDED) {
            const next = candidateRecord(result.candidateText, "generate", ticket.id);
            if (next) {
                replaceCandidate(next);
            } else {
                status = STATUS.FAILED;
                code = "invalid_candidate_json";
                message = message || "The generated candidate was not valid JSON.";
            }
        } else if (ticket.kind === "candidates") {
            const items = status === STATUS.SUCCEEDED && Array.isArray(result.items) ? result.items : null;
            candidates = Object.freeze({
                id: ticket.id,
                contextGeneration,
                repository,
                items: items ? Object.freeze(items.slice()) : null,
                message,
            });
        } else if (spec.slot === "review") {
            if (ticket.kind === "apply") refreshCandidate(result.candidateText);
            // Without output (for example a failed Undo) the previous review stays true.
            if (result.output && typeof result.output === "object") {
                review = reviewRecord(ticket.kind, ticket.id, status, result.output);
            }
        } else if (ticket.kind === "upload" && status === STATUS.SUCCEEDED) {
            const next = normalizeRepository(result.repository);
            if (next && next !== repository) {
                repository = next;
                invalidateContext("repository_changed");
            }
        }

        slots = { ...slots, [ticket.slot]: Object.freeze({ owner: ticket.id, kind: ticket.kind, status }) };
        if (spec.action) action = Object.freeze({ kind: ticket.kind, status, code, message, requestId: ticket.id });
        notify();
        return Object.freeze({ accepted: true, status, code, message });
    }

    // A local refusal (no request was sent) is still a truthful failed action.
    function refuse(kind, outcome) {
        const refused = blocked(kind);
        if (refused) return refused;
        const spec = KINDS[kind];
        const result = outcome && typeof outcome === "object" ? outcome : {};
        const code = text(result.code) || kind + "_refused";
        const message = text(result.message) || null;
        if (spec.slot === "review") {
            if (result.output && typeof result.output === "object") {
                review = reviewRecord(kind, null, STATUS.FAILED, result.output);
            }
            slots = { ...slots, review: Object.freeze({ owner: null, kind, status: STATUS.FAILED }) };
        }
        if (spec.action) action = Object.freeze({ kind, status: STATUS.FAILED, code, message, requestId: null });
        notify();
        return Object.freeze({ refused: false, recorded: true, code, message });
    }

    function selectListed(listId, index) {
        const items = candidates && candidates.id === listId ? candidates.items : null;
        const item = items && Number.isInteger(index) ? items[index] : null;
        if (!item) return refusal("select", "not_listed");
        if (mutationPending()) return refusal("select", "mutation_pending");
        const next = candidateRecord(JSON.stringify(item.patch, null, 2), "candidates", listId);
        if (!next) return refusal("select", "not_listed");
        replaceCandidate(next);
        action = Object.freeze({
            kind: "select", status: STATUS.SUCCEEDED, code: null,
            message: text(item.name) || "#" + (index + 1), requestId: listId,
        });
        notify();
        return Object.freeze({ refused: false, candidateId: next.id });
    }

    // -- structured backend outcomes ------------------------------------------------

    function generateOutcome(response) {
        const data = response && typeof response === "object" ? response : {};
        if (text(data.error)) return Object.freeze({ status: STATUS.FAILED, code: "generate_failed", message: data.error });
        if (text(data.patch)) {
            return Object.freeze({ status: STATUS.SUCCEEDED, code: null, message: null, candidateText: data.patch });
        }
        return Object.freeze({
            status: STATUS.FAILED, code: "generate_failed", message: "Patch generation returned no candidate.",
        });
    }

    function reviewOutcome(kind, response) {
        const data = response && typeof response === "object" ? response : {};
        const succeeded = data.success === true;
        const message = text(data.message) || text(data.error) || (succeeded ? "OK" : "failed");
        if (succeeded) return Object.freeze({ status: STATUS.SUCCEEDED, code: null, message });
        return Object.freeze({ status: STATUS.FAILED, code: text(data.code) || kind + "_failed", message });
    }

    // DATA.UNDO.1 success is exact: success === true, the issued backup and its
    // transaction, and the independently verified restored_sha256.
    function undoOutcome(response, sent) {
        const data = response && typeof response === "object" ? response : {};
        const receipt = sent && typeof sent === "object" ? sent : {};
        const message = text(data.message);
        if (data.success !== true) {
            return Object.freeze({
                status: STATUS.FAILED, code: text(data.code) || "undo_failed",
                message: message || text(data.error) || "Undo failed.",
            });
        }
        const confirmed = text(data.backup_id) !== "" && data.backup_id === receipt.backup_id
            && text(data.transaction_id) !== ""
            && (!text(receipt.transaction_id) || data.transaction_id === receipt.transaction_id)
            && SHA256_HEX.test(text(data.restored_sha256));
        if (!confirmed) {
            return Object.freeze({
                status: STATUS.FAILED, code: "undo_receipt_incomplete",
                message: "The Undo response did not confirm the exact backup it restored.",
            });
        }
        return Object.freeze({ status: STATUS.SUCCEEDED, code: null, message: message || "Undo successful" });
    }

    function describeAction(current) {
        const labels = current ? ACTION_LABELS[current.kind] : null;
        if (!labels || !labels[current.status]) return null;
        let label = labels[current.status];
        if (current.status === STATUS.FAILED && current.code === "plan_only_policy") {
            label = "apply blocked (plan-only policy)";
        } else if (current.status === STATUS.FAILED && current.code === "network_error") {
            label = current.kind + " error";
        }
        return Object.freeze({ label, detail: current.message || null });
    }

    // -- hydration --------------------------------------------------------------------

    function hydrate(initial) {
        if (hydrated) throw new Error("WorkbenchState is hydrated once per page load.");
        const seed = initial && typeof initial === "object" ? initial : {};
        const configured = seed.instant && typeof seed.instant === "object" ? seed.instant : {};
        const session = seed.run && typeof seed.run === "object" ? seed.run : {};
        hydrated = true;
        repository = normalizeRepository(seed.repository);
        run = serverRun(session);
        mode = seed.mode === "chat" ? "chat" : "instant";
        instant = Object.freeze({
            mode: EXECUTION_OPTIONS.mode.includes(configured.mode) ? configured.mode : INSTANT_DEFAULT.mode,
            apply_policy: EXECUTION_OPTIONS.apply_policy.includes(configured.apply_policy)
                ? configured.apply_policy : INSTANT_DEFAULT.apply_policy,
        });
        candidate = candidateRecord(seed.candidateText, "server", null);
        notify();
        return snapshot();
    }

    global.WorkbenchState = Object.freeze({
        STATUS,
        EXECUTION_OPTIONS,
        CHAT_EXECUTION,
        KINDS,
        hydrate,
        subscribe,
        snapshot,
        telemetry,
        setRepository,
        invalidate,
        setMode,
        setExecutionOption,
        execution,
        blocked,
        begin,
        settle,
        refuse,
        selectListed,
        generateOutcome,
        reviewOutcome,
        undoOutcome,
        describeAction,
    });
})(window);
