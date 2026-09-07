"""Generate operating documents from an operations sequence."""

from pathlib import Path

from eda_platform.schemas import OperationsSequence, ProjectState


def generate_operating_procedure(
    sequence: OperationsSequence,
    project: ProjectState,
) -> str:
    lines = [
        f"# Operating Procedure — {project.project_id}",
        "",
        f"**Fidelity:** {sequence.fidelity.value} · **Version:** {sequence.version}",
        "",
    ]
    if sequence.narrative:
        lines.extend(["## Overview", "", sequence.narrative, ""])

    lines.append("## Sequence")
    lines.append("")
    for i, step in enumerate(sequence.steps, start=1):
        lines.append(f"### {i}. {step.description}")
        if step.target_node_id:
            lines.append(f"- **Node:** `{step.target_node_id}`")
        if step.condition:
            lines.append(f"- **Condition:** {step.condition}")
        if step.timing:
            if step.timing.delay_ms is not None:
                src = step.timing.source.value
                lines.append(f"- **Delay:** {step.timing.delay_ms} ms ({src})")
            if step.timing.period_ms is not None:
                src = step.timing.source.value
                lines.append(f"- **Period:** {step.timing.period_ms} ms ({src})")
        if step.hal_call:
            lines.append(f"- **HAL:** `{step.hal_call}`")
        lines.append("")

    if sequence.open_questions:
        lines.extend(["## Open Questions", ""])
        for q in sequence.open_questions:
            lines.append(f"- [{q.question_id}] {q.text}")
        lines.append("")

    return "\n".join(lines)


def generate_bringup_checklist(
    sequence: OperationsSequence,
    project: ProjectState,
) -> str:
    lines = [
        f"# Bring-Up Checklist — {project.project_id}",
        "",
        "## Pre-power",
        "- [ ] Verify schematic passed Logic Checker",
        "- [ ] Confirm all power rails within component voltage envelopes",
        "- [ ] Enable I2C on target platform (raspi-config on Pi 4)",
        "",
        "## Boot sequence",
    ]
    for step in sequence.steps:
        checkbox = f"- [ ] {step.description}"
        if step.timing and step.timing.delay_ms:
            checkbox += f" (wait {step.timing.delay_ms} ms)"
        lines.append(checkbox)

    lines.extend(
        [
            "",
            "## Post-boot verification",
            "- [ ] Confirm supervisor heartbeat in logs",
            "- [ ] Verify sensor readings within expected range",
            "",
            f"_Generated from operations sequence v{sequence.version}_",
        ]
    )
    return "\n".join(lines)


def emit_operating_docs(
    output_dir: Path,
    sequence: OperationsSequence,
    project: ProjectState,
) -> list[str]:
    """Write operating documents to disk; return relative paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "OPERATING_PROCEDURE.md": generate_operating_procedure(sequence, project),
        "BRINGUP_CHECKLIST.md": generate_bringup_checklist(sequence, project),
    }
    written: list[str] = []
    for name, content in files.items():
        path = output_dir / name
        path.write_text(content)
        written.append(name)
    return written
