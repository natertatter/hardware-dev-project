"""Map operations sequence steps to runtime firmware behavior (Horizon B1)."""

from dataclasses import dataclass, field

from eda_platform.agents.operations_refiner.best_practices import is_boot_step
from eda_platform.schemas import OperationStep, OperationsSequence


@dataclass
class RuntimeDelayStep:
    step_id: str
    description: str
    delay_ms: int


@dataclass
class RuntimePeriodicStep:
    step_id: str
    description: str
    hal_call: str | None
    period_ms: int


@dataclass
class RuntimePlan:
    """Non-boot operations mapped for threaded runtime (not main() one-shot boot)."""

    startup_delays: list[RuntimeDelayStep] = field(default_factory=list)
    periodic_steps: list[RuntimePeriodicStep] = field(default_factory=list)

    @property
    def has_runtime_work(self) -> bool:
        return bool(self.startup_delays or self.periodic_steps)


def build_runtime_plan(operations: OperationsSequence | None) -> RuntimePlan:
    if operations is None or not operations.steps:
        return RuntimePlan()

    startup: list[RuntimeDelayStep] = []
    periodic: list[RuntimePeriodicStep] = []

    for step in operations.steps:
        timing = step.timing
        if timing and timing.delay_ms and not is_boot_step(step.description):
            startup.append(
                RuntimeDelayStep(
                    step_id=step.step_id,
                    description=step.description,
                    delay_ms=timing.delay_ms,
                )
            )
            continue

        period_ms = timing.period_ms if timing else None
        if period_ms or step.hal_call:
            periodic.append(
                RuntimePeriodicStep(
                    step_id=step.step_id,
                    description=step.description,
                    hal_call=step.hal_call,
                    period_ms=period_ms or 20,
                )
            )

    return RuntimePlan(startup_delays=startup, periodic_steps=periodic)


def boot_delay_steps(operations: OperationsSequence | None) -> list[tuple[int, str]]:
    """Boot-only delays for main() (delegates to emitter helper semantics)."""
    if operations is None:
        return []
    out: list[tuple[int, str]] = []
    for step in operations.steps:
        if step.timing and step.timing.delay_ms and is_boot_step(step.description):
            out.append((step.timing.delay_ms, step.description))
    return out
