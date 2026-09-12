"""On-disk schematic shape (nodes required; nets may be empty)."""

from eda_platform.api.schemas import SchematicDraft

# Re-export for callers that distinguish persistence from API DTOs.
SchematicFile = SchematicDraft

DRAFT_NET_PREFIX = "_draft_"
DRAFT_PLACEHOLDER_NET_ID = "_draft_placeholder"


def strip_draft_nets(draft: SchematicDraft) -> SchematicDraft:
    """Remove synthetic placeholder nets before persisting or returning to clients."""
    filtered = [n for n in draft.nets if not n.net_id.startswith(DRAFT_NET_PREFIX)]
    if len(filtered) == len(draft.nets):
        return draft
    return SchematicDraft(
        project_id=draft.project_id,
        nodes=draft.nodes,
        nets=filtered,
    )


def draft_content_key(draft: SchematicDraft) -> tuple:
    """Stable comparison key for nodes + nets (approval invalidation)."""
    return (
        tuple(
            (
                n.node_id,
                n.component_id,
                n.assigned_i2c_address,
                n.selected_protocol,
            )
            for n in draft.nodes
        ),
        tuple(
            (
                net.net_id,
                net.net_type,
                tuple((c.node_id, c.pin_id) for c in net.connections),
            )
            for net in draft.nets
        ),
    )
