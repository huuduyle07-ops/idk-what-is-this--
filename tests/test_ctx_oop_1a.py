"""CTX.OOP.1A exact-buffer Java class projection and authority boundaries."""
import hashlib
import json
import time

from core.class_semantic_context import (
    MAX_FIELDS, MAX_SERIALIZED_BYTES, project_class_semantic_context,
)
from core.treesitter_parse import structural_definitions
from tests.test_patch_basis_target1 import MAINAPP_JAVA


def project(source: str, name: str, *, kind: str = "function", occurrence: int = 0):
    raw = source.encode("utf-8")
    targets = [item for item in structural_definitions(source, "java")["definitions"]
               if item["name"] == name and item["kind"] == kind]
    assert targets
    return project_class_semantic_context(
        raw=raw, language="java", file="Example.java", target=targets[occurrence],
        expected_source_fingerprint=hashlib.sha256(raw).hexdigest(), repository_id="repo-1",
    )


def test_mainapp_exact_structure_and_static_instance_relation():
    result = project(MAINAPP_JAVA, "m3")
    assert result.status == "complete" and result.read_only
    assert result.class_identity.name == "MainApp"
    assert [(field.name, field.ownership) for field in result.fields] == [
        ("no", "instance"), ("sno", "static")]
    assert [(method.name, method.ownership) for method in result.methods] == [
        ("m1", "instance"), ("m2", "instance"), ("m3", "static"), ("main", "static")]
    assert not {"no1", "no2", "no3"} & {field.name for field in result.fields}
    assert ("m3", "no") in {(r.method_name, r.field_name) for r in result.relations
                             if r.kind == "static_to_instance_field_reference"}
    assert result.explicit_constructors == ()
    assert "Result 7" not in result.to_json()
    assert "editable" not in result.to_json()
    assert result.to_json() == project(MAINAPP_JAVA, "m3").to_json()
    assert json.loads(result.to_json())["read_only"] is True


def test_bankaccount_like_mutations_are_facts_only():
    source = """public class BankAccount {
    private int balance;
    public BankAccount(int opening) { this.balance = opening; }
    public void deposit(int amount) { balance += amount; }
    public void withdraw(int amount) { balance -= amount; }
    public void saving(int amount) { this.balance += amount; }
}"""
    result = project(source, "saving")
    assert result.fields[0].name == "balance"
    assert result.fields[0].ownership == "instance"
    assert result.fields[0].visibility == "private"
    assert [(c.name, [p.declared_type for p in c.parameters]) for c in result.explicit_constructors] == [
        ("BankAccount", ["int"])]
    assert {(r.method_name, r.access) for r in result.relations if r.kind == "field_usage"} == {
        ("deposit", "read_write"), ("withdraw", "read_write"), ("saving", "read_write")}
    assert "defect" not in result.to_json() and "should" not in result.to_json()


def test_nested_and_multiple_classes_do_not_flatten():
    source = """class A { int a; void first() {} }
class Outer { int outer; static class Inner { int inner; void target() { inner++; } } }
class B { int b; void last() {} }"""
    inner = project(source, "target")
    assert inner.class_identity.qualified_name == "Outer.Inner"
    assert [field.name for field in inner.fields] == ["inner"]
    assert [method.name for method in inner.methods] == ["target"]
    assert inner.class_identity.is_static
    outer = project(source, "Outer", kind="class")
    assert [field.name for field in outer.fields] == ["outer"]
    assert [field.name for field in project(source, "last").fields] == ["b"]


def test_overloads_shadowing_and_this_field_are_separate():
    source = """class Account {
    int balance;
    void foo() { int balance = 1; balance++; this.balance++; }
    void foo(int amount) { balance += amount; }
}"""
    result = project(source, "foo", occurrence=0)
    assert [len(method.parameters) for method in result.methods] == [0, 1]
    assert len({method.span.start for method in result.methods}) == 2
    assert [(r.method_name, r.access) for r in result.relations] == [
        ("foo", "read_write"), ("foo", "read_write")]


def test_visibility_modifiers_inheritance_and_generic_signature():
    source = """public abstract class A<T> extends Base<T> implements One, Two {
    protected static final int LIMIT = 3;
    private A() {}
    public final void get(java.util.List<T> items) {}
}"""
    result = project(source, "get")
    assert result.class_identity.visibility == "public"
    assert result.class_identity.is_abstract
    assert result.class_identity.extends == "Base<T>"
    assert result.class_identity.implements == ("One", "Two")
    assert result.fields[0].is_final and result.fields[0].ownership == "static"
    assert result.fields[0].visibility == "protected"
    assert result.explicit_constructors[0].visibility == "private"
    assert result.methods[0].return_type == "void"
    assert result.methods[0].parameters[0].declared_type == "java.util.List<T>"


def test_generic_return_target_uses_exact_snippet_and_ast_name():
    source = "class A<T> { T get() { return null; } }"
    raw = source.encode()
    target = next(item for item in structural_definitions(source, "java")["definitions"]
                  if item["kind"] == "function")
    # The older general extractor labels this method by its return type.
    assert target["name"] == "T"
    result = project_class_semantic_context(
        raw=raw, language="java", file="A.java", target=target,
        expected_source_fingerprint=hashlib.sha256(raw).hexdigest())
    assert result.status == "complete"
    assert result.target.name == "get"
    assert result.methods[0].return_type == "T"


def test_constructor_can_be_exact_target():
    source = "class A { int field; public A(int initial) { this.field = initial; } }"
    result = project(source, "A", kind="function")
    assert result.status == "complete" and result.target.name == "A"
    assert result.target.owner == "A"
    assert result.explicit_constructors[0].parameters[0].name == "initial"
    assert result.methods == ()


def test_comments_strings_and_unrelated_classes_are_not_state():
    source = """class A { // static int balance;
    String text = "static int balance";
    void target() { System.out.println("balance"); }
} class B { int balance; }"""
    result = project(source, "target")
    assert [field.name for field in result.fields] == ["text"]
    assert result.relations == ()


def test_unsupported_stale_and_ungrounded_targets_fail_closed():
    raw = b"class A { void target() {} }"
    target = next(item for item in structural_definitions(raw.decode(), "java")["definitions"]
                  if item["name"] == "target")
    sha = hashlib.sha256(raw).hexdigest()
    args = dict(raw=raw, file="A.java", target=target, expected_source_fingerprint=sha)
    assert project_class_semantic_context(**args, language="python").status == "not_supported"
    assert project_class_semantic_context(**{**args, "expected_source_fingerprint": "0" * 64},
                                          language="java").status == "unavailable"
    assert project_class_semantic_context(**{**args, "target": {**target, "start": 1}},
                                          language="java").status == "unavailable"
    assert project_class_semantic_context(**{**args, "target": {"kind": "function", "name": "target"}},
                                          language="java").status == "unavailable"

    anonymous = "class A { Runnable r = new Runnable() { public void run() {} }; }"
    assert project(anonymous, "run").status == "unavailable"


def test_explicit_bounds_and_byte_fingerprint():
    source = "class A { " + " ".join(f"int f{i};" for i in range(MAX_FIELDS + 1)) + " void target() {} }"
    result = project(source, "target")
    assert result.status == "bounded" and result.overflow == ("fields",)
    assert len(result.fields) == MAX_FIELDS
    assert len(result.to_json().encode()) <= MAX_SERIALIZED_BYTES
    assert result.source_fingerprint == hashlib.sha256(source.encode()).hexdigest()
    assert all(field.declaration_fingerprint for field in result.fields)

    many_methods = "class A { int x; int y; " + " ".join(
        f"void m{i}() {{ x++; y++; }}" for i in range(97)) + " }"
    method_result = project(many_methods, "m0")
    assert method_result.status == "bounded"
    assert method_result.overflow == ("methods", "relations")
    assert len(method_result.methods) == 96
    assert len(method_result.relations) == 128
    assert len(method_result.to_json().encode()) <= MAX_SERIALIZED_BYTES

    many_constructors = "class A { " + " ".join(
        "A(" + ", ".join(f"int p{j}" for j in range(i)) + ") {}"
        for i in range(33)) + " }"
    constructor_result = project(many_constructors, "A", kind="class")
    assert constructor_result.status == "bounded"
    assert constructor_result.overflow == ("constructors",)
    assert len(constructor_result.explicit_constructors) == 32


def test_projection_one_file_performance_smoke():
    raw = MAINAPP_JAVA.encode()
    target = next(item for item in structural_definitions(MAINAPP_JAVA, "java")["definitions"]
                  if item["name"] == "m3")
    start = time.perf_counter()
    result = project_class_semantic_context(raw=raw, language="java", file="MainApp.java",
        target=target, expected_source_fingerprint=hashlib.sha256(raw).hexdigest())
    parse_and_relations_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    result.to_json()
    serialization_ms = (time.perf_counter() - start) * 1000
    assert result.status == "complete"
    assert parse_and_relations_ms < 2000 and serialization_ms < 2000
