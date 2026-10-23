"""A compile-time-bound Java read primitive, without a product runner.

The returned source is diagnostic adapter implementation, not a scenario
harness. Rendering revalidates the frozen plan and supplied source lineage.
Neither rendering nor the adapter constructs objects or invokes product actions.
Only synthetic infrastructure tests compile this source in this phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from core import read_only_reflection as reflection

ADAPTER_CLASS_NAME = "ExactReadOnlyReflectionAdapter"
ADAPTER_VERSION = reflection.ADAPTER_VERSION


@dataclass(frozen=True, slots=True)
class BoundReadOnlyReflectionAdapter:
    source: str
    request_fingerprint: str
    adapter_class_name: str = ADAPTER_CLASS_NAME
    adapter_version: str = ADAPTER_VERSION

    @property
    def source_sha256(self):
        return sha256(self.source.encode("utf-8")).hexdigest()


def _class_literal(source_owner):
    # Exact parser-derived Java binary identities only. No runtime class lookup.
    if (type(source_owner) is not str or len(source_owner) > 256 or
            re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", source_owner) is None):
        raise reflection.ReadOnlyReflectionError("reflection_target_mismatch", "unsupported exact Java identity")
    return source_owner + ".class"


def render_read_only_reflection_adapter(request, *, execution_plan, specification,
        compile_receipt, materialized, candidate, admitted_scope, timings=None, **fresh_inputs):
    """Render one validated field read; no file, process, or runtime authority.

    The future diagnostic harness supplies an already-created object to the
    emitted read method. Class identities and the member name are constants in
    this artifact, not user/model/runtime parameters to the Java operation.
    """
    bound = reflection.validate_read_only_reflection_request(request,
        execution_plan=execution_plan, specification=specification,
        compile_receipt=compile_receipt, materialized=materialized, candidate=candidate,
        admitted_scope=admitted_scope, timings=timings, **fresh_inputs)
    declaring_owner = ((bound.target.package_name + ".") if bound.target.package_name else "")
    declaring_owner += bound.target.qualified_owner.replace("::", ".")
    declaring = _class_literal(declaring_owner)
    expected = _class_literal(bound.runtime_binding.source_owner)
    relationship = bound.runtime_binding.relationship
    if relationship == "same_class":
        relation_check = "EXPECTED_RUNTIME_CLASS == DECLARING_CLASS"
    elif relationship == "exact_direct_superclass":
        relation_check = "EXPECTED_RUNTIME_CLASS.getSuperclass() == DECLARING_CLASS"
    else:
        raise reflection.ReadOnlyReflectionError("reflection_target_mismatch", "unsupported owner relationship")
    source = _SOURCE.replace("__DECLARING_CLASS__", declaring).replace("__EXPECTED_RUNTIME_CLASS__", expected)
    source = source.replace("__RELATION_CHECK__", relation_check)
    source = source.replace("__FIELD_NAME__", bound.target.name)
    source = source.replace("__REQUEST_FINGERPRINT__", bound.fingerprint)
    source = source.replace("__ADAPTER_VERSION__", ADAPTER_VERSION)
    if bound.runtime_binding.package_name:
        package_name = bound.runtime_binding.package_name
        _class_literal(package_name)  # Apply the same closed identity grammar.
        source = "package " + package_name + ";\n\n" + source
    return BoundReadOnlyReflectionAdapter(source, bound.fingerprint)


# No command-line entrypoint, construction, enumeration, arbitrary class/member
# arguments, recursive inspection, or retained reflective handles.
_SOURCE = '''import java.lang.reflect.Field;
import java.lang.reflect.Modifier;

public final class ExactReadOnlyReflectionAdapter {
    private static final Class<?> DECLARING_CLASS = __DECLARING_CLASS__;
    private static final Class<?> EXPECTED_RUNTIME_CLASS = __EXPECTED_RUNTIME_CLASS__;
    private static final String REQUEST_FINGERPRINT = "__REQUEST_FINGERPRINT__";
    private static final String ADAPTER_VERSION = "__ADAPTER_VERSION__";

    private ExactReadOnlyReflectionAdapter() {}

    public static final class Observation {
        public final String requestFingerprint;
        public final String runtimeClassIdentity;
        public final String declaringClassIdentity;
        public final String measuredFieldType;
        public final String canonicalValueBits;
        public final String status;
        public final String failureCode;
        public final String adapterVersion;
        public final long targetValidationNanos;
        public final long reflectionReadNanos;
        public final long valueNormalizationNanos;
        public final long totalDiagnosticNanos;
        public final boolean mutationAuthority = false;

        private Observation(String runtimeClass, String declaredType, String valueBits,
                String failure, long validationNanos, long readNanos, long normalizationNanos,
                long totalNanos) {
            requestFingerprint = REQUEST_FINGERPRINT;
            runtimeClassIdentity = runtimeClass;
            declaringClassIdentity = DECLARING_CLASS.getName();
            measuredFieldType = declaredType;
            canonicalValueBits = valueBits;
            status = failure.isEmpty() ? "success" : "failure";
            failureCode = failure;
            adapterVersion = ADAPTER_VERSION;
            targetValidationNanos = validationNanos;
            reflectionReadNanos = readNanos;
            valueNormalizationNanos = normalizationNanos;
            totalDiagnosticNanos = totalNanos;
        }
    }

    public static Observation readExactBoundField(Object runtimeObject) {
        long started = System.nanoTime();
        long validationNanos = 0;
        long readNanos = 0;
        long normalizationNanos = 0;
        String runtimeClass = runtimeObject == null ? "" : runtimeObject.getClass().getName();
        String declaredType = "";
        String valueBits = "";
        String failure = "";
        Field exactField = null;
        boolean relaxed = false;
        try {
            if (runtimeObject == null || runtimeObject.getClass() != EXPECTED_RUNTIME_CLASS ||
                    !(__RELATION_CHECK__)) {
                failure = "reflection_runtime_class_mismatch";
            } else {
                exactField = DECLARING_CLASS.getDeclaredField("__FIELD_NAME__");
                declaredType = exactField.getType().getName();
                if (exactField.getDeclaringClass() != DECLARING_CLASS ||
                        exactField.getType() != double.class || Modifier.isStatic(exactField.getModifiers()) ||
                        !Modifier.isPrivate(exactField.getModifiers())) {
                    failure = "reflection_target_mismatch";
                } else {
                    validationNanos = System.nanoTime() - started;
                    long readStarted = System.nanoTime();
                    if (!exactField.canAccess(runtimeObject)) {
                        relaxed = exactField.trySetAccessible();
                        if (!relaxed) {
                            failure = "reflection_access_denied";
                        }
                    }
                    if (failure.isEmpty()) {
                        double measuredValue = exactField.getDouble(runtimeObject);
                        readNanos = System.nanoTime() - readStarted;
                        long normalizationStarted = System.nanoTime();
                        if (!Double.isFinite(measuredValue)) {
                            failure = "reflection_nonfinite_value";
                        } else {
                            String rawBits = Long.toHexString(Double.doubleToRawLongBits(measuredValue));
                            valueBits = "0000000000000000".substring(rawBits.length()) + rawBits;
                        }
                        normalizationNanos = System.nanoTime() - normalizationStarted;
                    }
                }
            }
        } catch (NoSuchFieldException exception) {
            failure = "reflection_target_mismatch";
        } catch (SecurityException exception) {
            failure = "reflection_access_denied";
        } catch (IllegalAccessException exception) {
            failure = "reflection_access_denied";
        } catch (RuntimeException exception) {
            failure = "reflection_read_failed";
        } finally {
            // This exact Field is fresh for each observation and never escapes.
            if (relaxed) {
                try {
                    exactField.setAccessible(false);
                } catch (RuntimeException exception) {
                    failure = "reflection_accessibility_restore_failed";
                }
            }
        }
        if (!failure.isEmpty()) valueBits = "";
        if (validationNanos == 0) validationNanos = System.nanoTime() - started;
        return new Observation(runtimeClass, declaredType, valueBits, failure,
            validationNanos, readNanos, normalizationNanos, System.nanoTime() - started);
    }
}
'''
