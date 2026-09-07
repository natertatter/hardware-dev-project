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


def _node_keywords(node_id: str, component_id: str, manifest: ComponentManifest) -> set[str]:
    """Tokens usable for fuzzy matching step descriptions to nodes."""
    tokens: set[str] = set()
    for value in (node_id, component_id, manifest.name):
        for part in re.split(r"[_\s\-/]+", value.lower()):
            if len(part) >= 3:
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

    return best_id if best_score > 0 else None


def classification_for_node(
    node_id: str, classifications: list[NodeClassification]
) -> NodeClassification | None:
    for c in classifications:
        if c.node_id == node_id:
            return c
    return None
