"""Bind operation steps to ProjectState nodes and HAL modules."""

import re

from eda_platform.agents.firmware_engineer.classifier import classify_nodes
from eda_platform.agents.firmware_engineer.models import NodeClassification
from eda_platform.agents.operations_refiner.best_practices import suggest_hal_call
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    OperationStep,
    ProjectState,
)

# Generic electronics/hardware terms that appear in many component names
# (e.g. "INA219 Current/Power Monitor") but do not identify any specific
# node. Matching on these alone causes false positives — e.g. a generic
# "Enable power rail" boot step incorrectly binding to a current sensor
# just because its manifest name happens to contain "Power". Excluded from
# keyword matching entirely; a real match must come from the node_id
# substring check or a genuinely distinguishing token (model number, etc.).
_GENERIC_STOPWORDS = {
    "power",
    "current",
    "voltage",
    "monitor",
    "module",
    "board",
    "circuit",
    "system",
    "controller",
    "driver",
    "device",
    "unit",
    "signal",
    "output",
    "input",
    "sensor",
    "actuator",
    "component",
}

# Minimum accumulated score required to accept a fuzzy match. A single
# generic-keyword hit (weight 2) must never be sufficient on its own —
# only an exact node_id substring match (weight 3) or multiple corroborating
# tokens should bind a step to a node. Ambiguous steps are left unbound and
# surfaced as open questions instead (a false negative is safe; a false
# positive silently corrupts the operations sequence and generated firmware).
_MIN_MATCH_SCORE = 3


def _node_keywords(node_id: str, component_id: str, manifest: ComponentManifest) -> set[str]:
    """Tokens usable for fuzzy matching step descriptions to nodes."""
    tokens: set[str] = set()
    for value in (node_id, component_id, manifest.name):
        for part in re.split(r"[_\s\-/]+", value.lower()):
            if len(part) >= 3 and part not in _GENERIC_STOPWORDS:
                tokens.add(part)
    return tokens


def match_node_for_step(
    description: str,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
) -> str | None:
    """Return the best-matching node_id for a step description, or None."""
    lower = description.lower()
    best_id: str | None = None
    best_score = 0

    for node in project.nodes:
        manifest = manifests.get(node.component_id)
        if manifest is None or manifest.type == ComponentType.MCU:
            continue
        score = 0
        if node.node_id.lower() in lower:
            score += 3
        for token in _node_keywords(node.node_id, node.component_id, manifest):
            if token in lower:
                score += 2
        if score > best_score:
            best_score = score
            best_id = node.node_id

    return best_id if best_score >= _MIN_MATCH_SCORE else None


def classification_for_node(
    node_id: str, classifications: list[NodeClassification]
) -> NodeClassification | None:
    for c in classifications:
        if c.node_id == node_id:
            return c
    return None
