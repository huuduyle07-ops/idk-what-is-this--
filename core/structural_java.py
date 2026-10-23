"""Bounded, in-memory Java declaration and contract checks for structural drafts.

This deliberately does not compile, execute, or prove arbitrary Java behavior.
Unrecognized infrastructure/contract shapes fail closed for later escalation.
"""
from __future__ import annotations

import re
from time import perf_counter
from tree_sitter_language_pack import get_parser


class StructuralJavaError(ValueError):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason
        super().__init__(code + ": " + reason)


def fail(reason, code="author_output_outside_admitted_scope"):
    raise StructuralJavaError(code, reason)


def children(node):
    return [n for n in node.named_children if n.type not in {"line_comment", "block_comment"}]


def walk(node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def text(node, raw):
    return raw[node.start_byte:node.end_byte].decode("utf-8") if node else ""


def compact(node, raw):
    # Use syntax tokens, excluding comments; quoted text is never interpreted as code.
    if node is None:
        return ""
    if not node.children:
        return text(node, raw)
    return "".join(compact(n, raw) for n in node.children
                   if n.type not in {"line_comment", "block_comment"})


def _definition(node, owner, raw):
    kinds = {"class_declaration": "class", "method_declaration": "method",
             "field_declaration": "field", "constructor_declaration": "constructor"}
    if node.type not in kinds:
        fail("unplanned declaration/initializer")
    kind = kinds[node.type]
    modifiers = next((n for n in children(node) if n.type == "modifiers"), None)
    tokens = [text(n, raw) for n in modifiers.children] if modifiers else []
    # PLAN V1 fixes visibility, not arbitrary annotations, native methods or generics.
    if any(t not in {"public", "private", "protected", "static"} for t in tokens):
        fail("unplanned declaration modifier")
    visibility = next((t for t in tokens if t in {"public", "private", "protected"}), "package")
    if "static" in tokens and kind != "class":
        fail("unplanned static state/member")
    name = text(node.child_by_field_name("name"), raw)
    dtype = compact(node.child_by_field_name("type"), raw) if kind in {"field", "method"} else ""
    if kind == "field":
        declarators = [n for n in children(node) if n.type == "variable_declarator"]
        if len(declarators) != 1:
            fail("each field requires its own admitted identity")
        name = text(declarators[0].child_by_field_name("name"), raw)
        if declarators[0].child_by_field_name("dimensions"):
            fail("unplanned field dimensions")
    parameters = node.child_by_field_name("parameters")
    shape = []
    if parameters:
        for parameter in children(parameters):
            if parameter.type != "formal_parameter" or any(n.type in {"modifiers", "dimensions"}
                                                         for n in children(parameter)):
                fail("unplanned parameter shape")
            shape.append((compact(parameter.child_by_field_name("type"), raw),
                          text(parameter.child_by_field_name("name"), raw)))
    parent = None
    if kind == "class":
        superclass = node.child_by_field_name("superclass")
        parent = compact(children(superclass)[0], raw) if superclass and children(superclass) else None
    if node.child_by_field_name("type_parameters") or node.child_by_field_name("interfaces") or node.child_by_field_name("dimensions"):
        fail("unplanned generic/interface relationship")
    if any(n.type == "throws" for n in children(node)):
        fail("unplanned throws contract")
    if kind in {"method", "constructor"} and node.child_by_field_name("body") is None:
        fail("implementation body required", "author_output_invalid")
    return (owner, name, kind, visibility, dtype, tuple(shape), parent)


def parse_operation(operation, source, definitions, *, package_name="", timings=None, referenced_definitions=None):
    """Return exact definition/node bindings. Parsing never touches a repository."""
    tick = perf_counter()
    wrapped = operation.operation == "insert_member"
    prefix = ("class " + operation.owner + " {\n") if wrapped else ""
    raw = (prefix + source + ("\n}" if wrapped else "")).encode("utf-8")
    # Java Unicode escape preprocessing can change structure before lexing.
    if re.search(rb"\\u+[0-9a-fA-F]{4}", raw) or b"\x00" in raw:
        fail("ambiguous Java escape", "author_output_invalid")
    tree = get_parser("java").parse(raw)
    if tree.root_node.has_error:
        fail("Java syntax incomplete", "author_output_invalid")
    roots = children(tree.root_node)
    packages = [n for n in roots if n.type == "package_declaration"]
    imports = [n for n in roots if n.type == "import_declaration"]
    classes = [n for n in roots if n.type == "class_declaration"]
    if len(classes) != 1 or len(packages) > 1 or any(n.type not in {
            "class_declaration", "package_declaration", "import_declaration"} for n in roots):
        fail("exact single class required")
    actual_package = compact(children(packages[0])[0], raw) if packages else ""
    if (wrapped or operation.operation == "insert_nested_class") and (packages or imports):
        fail("member/nested insertion cannot change imports/package")
    if not wrapped and operation.operation == "draft_new_file" and actual_package != package_name:
        fail("package differs from admission")
    cls = classes[0]
    bindings = []

    def collect(node, owner):
        shape = _definition(node, owner, raw)
        matches = [d for d in definitions if (d.owner, d.name, d.kind, d.visibility,
            re.sub(r"\s+", "", d.declared_type), d.parameters, d.parent) == shape]
        if len(matches) != 1:
            fail("generated definition does not match PLAN identity/signature")
        bindings.append((matches[0], node))
        if shape[2] == "class":
            body = node.child_by_field_name("body")
            for child in children(body):
                collect(child, shape[1])

    if wrapped:
        if text(cls.child_by_field_name("name"), raw) != operation.owner:
            fail("insertion owner mismatch")
        for child in children(cls.child_by_field_name("body")):
            collect(child, operation.owner)
    else:
        name = text(cls.child_by_field_name("name"), raw)
        if operation.operation == "draft_new_file" and any(
                n.type == "modifiers" and "static" in [text(c, raw) for c in n.children] for n in children(cls)):
            fail("static top-level Java class", "author_output_invalid")
        collect(cls, name)
        if operation.operation == "draft_new_file" and name != operation.owner:
            fail("top-level class identity mismatch")
    ids = [d.identity for d, _ in bindings]
    if len(set(ids)) != len(ids):
        fail("duplicate generated definition")
    if set(ids) != set(operation.definition_ids):
        fail("missing required generated definition", "author_output_incomplete")
    # Reject hidden/local/anonymous classes and declarations inside executable bodies.
    declaration_nodes = {node.id for _, node in bindings}
    if wrapped:
        declaration_nodes.add(cls.id)
    for node in walk(tree.root_node):
        if (node.type in {"class_declaration", "method_declaration", "field_declaration",
                          "constructor_declaration"} and node.id not in declaration_nodes):
            fail("hidden unplanned definition")
        if node.type in {"object_creation_expression", "lambda_expression", "interface_declaration",
                         "enum_declaration", "record_declaration", "annotation_type_declaration"}:
            fail("unplanned executable/infrastructure structure", "author_output_semantic_drift")
    for node in walk(tree.root_node):
        if node.type in {"line_comment", "block_comment"} and re.search(
                r"(?i)\b(?:javac|powershell|bash|shell_command|write_file|apply_patch|execute_command|"
                r"Set-Content|Invoke-Expression|cmd\.exe)\b|\brm\s+-", text(node, raw)):
            fail("command/tool instruction in generated payload", "author_output_invalid")
    _imports_and_infrastructure(tree.root_node, raw, imports, referenced_definitions or definitions)
    if timings is not None:
        timings["java_structural_parsing_seconds"] += perf_counter() - tick
    return raw, tuple(bindings)


def _imports_and_infrastructure(root, raw, imports, definitions):
    # V1 supports only a deterministic, side-effect-free equality utility import.
    referenced = {text(n, raw) for n in walk(root) if n.type == "identifier"
                  and not any(p.start_byte <= n.start_byte < p.end_byte for p in imports)}
    for node in imports:
        if compact(node, raw) != "importjava.util.Objects;" or "Objects" not in referenced:
            fail("unneeded or infrastructure import", "author_output_semantic_drift")
    if len(imports) > 1:
        fail("duplicate imports")
    allowed_types = {"String", "Objects"} | {d.owner for d in definitions} | {
        d.parent for d in definitions if d.parent}
    allowed_types |= {t for d in definitions for t, _ in d.parameters}
    allowed_types |= {d.declared_type for d in definitions if d.declared_type}
    fields = {d.name for d in definitions if d.kind == "field"}
    string_receivers = {d.name for d in definitions if d.kind == "field" and d.declared_type == "String"}
    string_receivers |= {"this." + x for x in string_receivers}
    string_receivers |= {name for d in definitions for dtype, name in d.parameters if dtype == "String"}
    for node in walk(root):
        if node.type == "type_identifier" and text(node, raw) not in allowed_types:
            fail("unbound referenced type", "author_output_semantic_drift")
        if node.type in {"method_invocation", "field_access"}:
            obj = compact(node.child_by_field_name("object"), raw)
            if obj and not (obj in {"this", "super", "Objects", "System", "System.console()"}
                            or obj in fields or obj in string_receivers):
                fail("unbound external receiver", "author_output_semantic_drift")
        if node.type == "method_invocation":
            name = text(node.child_by_field_name("name"), raw)
            obj = compact(node.child_by_field_name("object"), raw)
            allowed = ({"console"} if obj == "System" else {"readLine"} if obj == "System.console()"
                       else {"equals"} if obj == "Objects" or obj in string_receivers
                       else {d.name for d in definitions if d.kind == "method"})
            if name not in allowed:
                fail("unplanned invocation/infrastructure", "author_output_semantic_drift")


def check_contracts(parsed, scope):
    """Necessary structural witnesses, intentionally short of behavioral proof."""
    all_definitions = [a.definition for a in scope.definition_allowances]
    names = lambda role: [d.name for d in all_definitions if role in d.roles]
    credentials = names("credential_state")
    balances = names("subclass_owned_state")
    base_owners = {d.parent for d in all_definitions if d.kind == "class" and d.parent}
    gates = names("authentication_gated_savings_operation")
    debits = names("base_balance_debit") + [b.name for c in scope.capability_coverage
                if c.code == "base_balance_debit" for b in c.existing_mechanisms]
    for raw, bindings in parsed:
        for definition, node in bindings:
            body = node.child_by_field_name("body")
            syntax = compact(body or node, raw)
            def drift(reason):
                fail(reason, "author_output_semantic_drift")
            bound_state = set(credentials + balances + ["balance"])
            for declaration in walk(body or node):
                if declaration.type == "local_variable_declaration" and any(
                        text(n.child_by_field_name("name"), raw) in bound_state
                        for n in children(declaration) if n.type == "variable_declarator"):
                    drift("local declaration shadows bound contract state")
            if any(n.type in {"for_statement", "while_statement", "do_statement", "try_statement",
                              "synchronized_statement", "throw_statement"} for n in walk(node)):
                drift("unplanned retry/timing/error policy")
            for n in walk(body or node):
                if n.type in {"assignment_expression", "update_expression"}:
                    left = compact(n.child_by_field_name("left") or n.named_children[0], raw)
                    if definition.owner not in base_owners and left in {"balance", "this.balance", "super.balance"}:
                        drift("inherited balance must remain encapsulated")
            roles = set(definition.roles)
            if definition.kind == "field":
                values = [n.child_by_field_name("value") for n in children(node) if n.type == "variable_declarator"]
                if "credential_state" in roles and any(v is not None for v in values):
                    drift("credential must come from supplied initialization")
                if "subclass_owned_state" in roles and any(v is not None and compact(v, raw) not in {"0", "0.0"} for v in values):
                    drift("unplanned initial savings policy")
            credential_owners = {d.owner for d in all_definitions if "credential_state" in d.roles}
            if "credential_state" in roles and (definition.owner not in credential_owners
                    or definition.kind != "field" or definition.declared_type != "String"):
                drift("credential ownership/representation")
            if "subclass_initialization" in roles:
                invocations = [n for n in children(body) if n.type == "explicit_constructor_invocation"]
                if len(invocations) != 1 or not compact(invocations[0], raw).startswith("super("):
                    drift("base constructor initialization missing")
                if not any(re.search(r"(?:this\.)?" + re.escape(c) + r"=", syntax) for c in credentials):
                    drift("credential initialization missing")
                credential_parameters = [p for dtype, p in definition.parameters if dtype == "String" and p in credentials]
                supplied_base = [p for _, p in definition.parameters if p not in credential_parameters]
                if compact(invocations[0].child_by_field_name("arguments"), raw) != "(" + ",".join(supplied_base) + ")":
                    drift("base initialization must use the selected supplied parameters")
                assignments = [compact(n, raw) for n in walk(body) if n.type == "assignment_expression"]
                allowed_assignments = {"this." + c + "=" + p for c in credentials for p in credential_parameters}
                allowed_assignments |= {"this." + b + "=0" for b in balances} | {"this." + b + "=0.0" for b in balances}
                if not credential_parameters or not set(assignments) <= allowed_assignments:
                    drift("unplanned constructor state/credential policy")
            if "authentication_gated_savings_operation" in roles:
                parameters = [name for dtype, name in definition.parameters if dtype == "String"]
                comparisons = {c + ".equals(" + p + ")" for c in credentials for p in parameters}
                comparisons |= {"this." + c + ".equals(" + p + ")" for c in credentials for p in parameters}
                comparisons |= {p + ".equals(" + c + ")" for c in credentials for p in parameters}
                comparisons |= {"Objects.equals(" + c + "," + p + ")" for c in credentials for p in parameters}
                comparisons |= {"Objects.equals(this." + c + "," + p + ")" for c in credentials for p in parameters}
                if not any(comparison in syntax for comparison in comparisons):
                    drift("in-memory password comparison missing")
                statements = children(body)
                if len(statements) != 1 or compact(statements[0], raw) not in {"return" + c + ";" for c in comparisons}:
                    drift("verification result must carry the selected credential comparison")
                if any(n.type in {"assignment_expression", "update_expression", "if_statement"} for n in walk(body)):
                    drift("unplanned password verification policy/state")
            if roles & {"savings_funding_transition", "savings_interest_behavior"}:
                statements = children(body)
                first = statements[0] if statements else None
                condition = compact(first.child_by_field_name("condition"), raw) if first else ""
                consequence = compact(first.child_by_field_name("consequence"), raw) if first else ""
                if (not first or first.type != "if_statement" or first.child_by_field_name("alternative")
                        or not any(condition.startswith("(!" + g + "(") for g in gates)
                        or consequence not in {"returnfalse;", "{returnfalse;}", "return;", "{return;}"}):
                    drift("operation-gated verification witness missing")
                gate_args = [n for n in walk(first.child_by_field_name("condition")) if n.type == "argument_list"]
                permitted_inputs = {"(" + p + ")" for dtype, p in definition.parameters if dtype == "String"}
                permitted_inputs.add("(System.console().readLine())")
                gate_calls = [n for n in walk(first.child_by_field_name("condition")) if n.type == "method_invocation"
                              and text(n.child_by_field_name("name"), raw) in gates]
                if len(gate_calls) != 1 or compact(gate_calls[0].child_by_field_name("arguments"), raw) not in permitted_inputs:
                    drift("verification must use supplied operation input")
                if condition != "(!" + compact(gate_calls[0], raw) + ")":
                    drift("unplanned combined authentication/policy predicate")
                if any(compact(n, raw) in {"(" + c + ")", "(this." + c + ")"} for c in credentials for n in gate_args):
                    drift("stored credential cannot authenticate itself")
                writes = [n for n in walk(body) if n.type == "assignment_expression"]
                branch_count = sum(n.type == "if_statement" for n in walk(body))
                if branch_count != (2 if "savings_funding_transition" in roles else 1):
                    drift("unplanned operation limit/lockout/timing policy")
                if "savings_funding_transition" in roles:
                    if len(statements) < 3:
                        drift("successful inherited debit guard missing")
                    second = statements[1]
                    cond = compact(second.child_by_field_name("condition"), raw)
                    cons = compact(second.child_by_field_name("consequence"), raw)
                    if (second.type != "if_statement" or second.child_by_field_name("alternative")
                            or not any(cond == "(!" + prefix + d + "(" + definition.parameters[0][1] + "))"
                                       for d in debits for prefix in ("", "super.", "this."))
                            or cons not in {"returnfalse;", "{returnfalse;}"}):
                        drift("credit must follow successful inherited debit")
                    amount = definition.parameters[0][1]
                    if len(writes) != 1 or compact(writes[0], raw) not in {
                            b + "+=" + amount for b in balances} | {"this." + b + "+=" + amount for b in balances}:
                        drift("unplanned fee/credit policy")
                else:
                    if len(writes) != 1 or not definition.parameters:
                        drift("interest contract witness missing")
                    params = [p[1] for p in definition.parameters[:2]]
                    expected = {b + "+=" + b + "*" + "*".join(params) for b in balances}
                    expected |= {"this." + b + "+=this." + b + "*" + "*".join(params) for b in balances}
                    if compact(writes[0], raw) not in expected:
                        drift("interest applies only to savingBalance with planned timing")
            if "base_balance_debit" in roles:
                if sum(n.type == "if_statement" for n in walk(body)) != 1:
                    drift("unplanned debit/overdraft policy")
                amount = definition.parameters[0][1]
                branch = next(n for n in walk(body) if n.type == "if_statement")
                condition = compact(branch.child_by_field_name("condition"), raw)
                if condition not in {"(" + amount + "<=" + b + ")" for b in ("balance", "this.balance")} | {
                        "(" + b + ">=" + amount + ")" for b in ("balance", "this.balance")}:
                    drift("observable debit guard missing")
                writes = [compact(n, raw) for n in walk(body) if n.type == "assignment_expression"]
                if len(writes) != 1 or writes[0] not in {"balance-=" + amount, "this.balance-=" + amount}:
                    drift("unplanned debit fee/amount policy")
                if "returntrue;" not in compact(branch.child_by_field_name("consequence"), raw):
                    drift("successful debit result must accompany debit")
                if not all(witness in syntax for witness in ("balance-=" + amount, "returntrue;", "returnfalse;")):
                    drift("observable successful debit contract missing")
