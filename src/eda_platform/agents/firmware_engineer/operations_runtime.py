"""Map operations sequence steps to runtime firmware behavior (Horizon B1).

Boot/init steps with one-shot delays belong in ``main()`` (see ``boot_delay_steps``).
They run once at startup. Non-boot one-shot delays without a declared ``period_ms``
are not representable as a fire-once thread without ``depends_on`` sequencing — those
step ids are surfaced in ``RuntimeCodegenNotes`` for degrade messaging.

Periodic steps (``period_ms`` and/or ``hal_call``) are emitted into
``runtime/ops_interpreter.c`` and driven by ``task_operations_runtime``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from eda_platform.agents.operations_refiner.best_practices import (
    I2C_SENSOR_POLL_PERIOD_MS,
    is_boot_step,
)
from eda_platform.agents.firmware_engineer.errors import FirmwareEngineerError
from eda_platform.schemas import OperationStep, OperationsSequence


@dataclass
class RuntimePeriodicStep:
    step_id: str
    description: str
    period_ms: int
    hal_call: str | None
    c_body: str
    unresolved_hal: bool = False


@dataclass
class RuntimePlan:
    """Periodic runtime operations (not main() boot delays)."""

    periodic_steps: list[RuntimePeriodicStep] = field(default_factory=list)
    tick_period_ms: int = I2C_SENSOR_POLL_PERIOD_MS

    @property
    def has_runtime_work(self) -> bool:
        return bool(self.periodic_steps)


@dataclass
class RuntimeCodegenNotes:
    deferred_delay_step_ids: list[str] = field(default_factory=list)
    conditioned_step_ids: list[str] = field(default_factory=list)
    unresolved_hal_step_ids: list[str] = field(default_factory=list)
    default_period_step_ids: list[str] = field(default_factory=list)

    def degrade_fragments(self) -> list[str]:
        parts: list[str] = []
        if self.deferred_delay_step_ids:
            ids = ", ".join(self.deferred_delay_step_ids)
            parts.append(
                f"{len(self.deferred_delay_step_ids)} step(s) have one-shot delays "
                f"with no period — not represented in runtime firmware ({ids})"
            )
        if self.conditioned_step_ids:
            ids = ", ".join(self.conditioned_step_ids)
            parts.append(
                f"{len(self.conditioned_step_ids)} step(s) have conditions "
                f"not implemented in runtime firmware ({ids})"
            )
        if self.unresolved_hal_step_ids:
            ids = ", ".join(self.unresolved_hal_step_ids)
            parts.append(
                f"{len(self.unresolved_hal_step_ids)} step(s) have unresolved hal_call ({ids})"
            )
        if self.default_period_step_ids:
            ids = ", ".join(self.default_period_step_ids)
            parts.append(
                f"{len(self.default_period_step_ids)} step(s) use default poll period "
                f"{I2C_SENSOR_POLL_PERIOD_MS} ms ({ids})"
            )
        return parts


def _topo_sort_steps(steps: list[OperationStep]) -> list[OperationStep]:
    by_id = {s.step_id: s for s in steps}
    indegree = {s.step_id: 0 for s in steps}
    for step in steps:
        for dep in step.depends_on:
            if dep in by_id:
                indegree[step.step_id] += 1
    ready = [s for s in steps if indegree[s.step_id] == 0]
    ordered: list[OperationStep] = []
    while ready:
        step = ready.pop(0)
        ordered.append(step)
        for other in steps:
            if step.step_id in other.depends_on:
                indegree[other.step_id] -= 1
                if indegree[other.step_id] == 0:
                    ready.append(other)
    if len(ordered) != len(steps):
        raise FirmwareEngineerError("operations sequence has cyclic depends_on")
    return ordered


def _sensor_for_step(step: OperationStep, sensors: list[dict]) -> dict | None:
    if step.target_node_id:
        for sensor in sensors:
            if sensor["node_id"] == step.target_node_id:
                return sensor
    if step.hal_call:
        match = re.search(r"(hal_[a-z0-9_]+)", step.hal_call)
        if match:
            module = match.group(1)
            for sensor in sensors:
                if sensor["hal_module"] == module:
                    return sensor
    return None


def _resolve_hal_body(step: OperationStep, sensors: list[dict]) -> tuple[str, bool]:
    """Return (C statements, unresolved)."""
    if not step.hal_call:
        return "", False

    sensor = _sensor_for_step(step, sensors)
    if sensor is None:
        return f"    /* UNRESOLVED hal_call: {step.hal_call} */", True

    hal = sensor["hal_module"]
    node_id = sensor["node_id"]
    call_lower = step.hal_call.lower()
    if "read" in call_lower or "poll" in call_lower or "sensor" in call_lower:
        return (
            f"    float {node_id}_ma = 0.0f;\n"
            f"    if ({hal}_read_current_ma(&{node_id}_ma) != 0) {{\n"
            f'        fprintf(stderr, "[runtime] {step.step_id}: read failed\\n");\n'
            f"    }} else {{\n"
            f'        printf("[runtime] %s: %.2f mA\\n", "{step.step_id}", {node_id}_ma);\n'
            f"    }}",
            False,
        )
    if "init" in call_lower:
        return f"    {hal}_init();", False

    return f"    /* UNRESOLVED hal_call: {step.hal_call} */", True


def _escape_c_string(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _log_only_body(step: OperationStep) -> str:
    desc = _escape_c_string(step.description)
    return f'    printf("[runtime] %s: %s\\n", "{step.step_id}", "{desc}");'


def build_runtime_plan(
    operations: OperationsSequence | None,
    sensors: list[dict],
) -> tuple[RuntimePlan, RuntimeCodegenNotes]:
    notes = RuntimeCodegenNotes()
    if operations is None or not operations.steps:
        return RuntimePlan(), notes

    periodic: list[RuntimePeriodicStep] = []
    ordered = _topo_sort_steps(list(operations.steps))

    for step in ordered:
        if step.condition:
            notes.conditioned_step_ids.append(step.step_id)
            continue

        timing = step.timing
        delay_ms = timing.delay_ms if timing else None
        period_ms = timing.period_ms if timing else None

        if delay_ms and is_boot_step(step.description):
            continue

        if period_ms is not None:
            if period_ms < 1:
                raise FirmwareEngineerError(
                    f"step {step.step_id}: period_ms must be >= 1 for runtime emission"
                )
            if step.hal_call:
                body, unresolved = _resolve_hal_body(step, sensors)
            else:
                body, unresolved = _log_only_body(step), False
            periodic.append(
                RuntimePeriodicStep(
                    step_id=step.step_id,
                    description=step.description,
                    period_ms=period_ms,
                    hal_call=step.hal_call,
                    c_body=body,
                    unresolved_hal=unresolved,
                )
            )
            if unresolved:
                notes.unresolved_hal_step_ids.append(step.step_id)
            continue

        if delay_ms:
            notes.deferred_delay_step_ids.append(step.step_id)
            continue

        if step.hal_call:
            body, unresolved = _resolve_hal_body(step, sensors)
            if unresolved:
                notes.unresolved_hal_step_ids.append(step.step_id)
            notes.default_period_step_ids.append(step.step_id)
            periodic.append(
                RuntimePeriodicStep(
                    step_id=step.step_id,
                    description=step.description,
                    period_ms=I2C_SENSOR_POLL_PERIOD_MS,
                    hal_call=step.hal_call,
                    c_body=body,
                    unresolved_hal=unresolved,
                )
            )

    tick = min((s.period_ms for s in periodic), default=I2C_SENSOR_POLL_PERIOD_MS)
    return RuntimePlan(periodic_steps=periodic, tick_period_ms=tick), notes


def boot_delay_steps(operations: OperationsSequence | None) -> list[tuple[int, str]]:
    """Boot-only delays for main() — one-shot at startup, not recurring runtime.

    Steps are emitted in ``depends_on`` topological order so boot sequencing
    matches the operations graph when delays are present.
    """
    if operations is None or not operations.steps:
        return []
    out: list[tuple[int, str]] = []
    for step in _topo_sort_steps(list(operations.steps)):
        if step.timing and step.timing.delay_ms and is_boot_step(step.description):
            out.append((step.timing.delay_ms, step.description))
    return out


def partition_step_ids(
    operations: OperationsSequence,
    sensors: list[dict],
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Return (boot_delay_ids, periodic_ids, deferred_ids, skipped_condition_ids)."""
    boot_ids: set[str] = set()
    plan, notes = build_runtime_plan(operations, sensors)
    periodic_ids = {s.step_id for s in plan.periodic_steps}
    for step in operations.steps:
        timing = step.timing
        delay_ms = timing.delay_ms if timing else None
        if delay_ms and is_boot_step(step.description):
            boot_ids.add(step.step_id)
    deferred_ids = set(notes.deferred_delay_step_ids)
    conditioned_ids = set(notes.conditioned_step_ids)
    return boot_ids, periodic_ids, deferred_ids, conditioned_ids
