"""Template architect API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.agents.architect.template_layout import template_i2c_layout
from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.schemas import AutoWireRequest, AutoWireResponse
from eda_platform.schemas import Net, NetConnection, NetType, ProjectState

router = APIRouter(prefix="/api/v1", tags=["architect"])


def _draft_to_project_state(draft) -> ProjectState:
    """Convert a UI schematic draft into a ProjectState for template processing."""
    if draft.nets:
        return ProjectState(
            project_id=draft.project_id,
            nodes=draft.nodes,
            nets=draft.nets,
        )

    # Placement-only draft: synthesize a throwaway net so ProjectState validates.
    return ProjectState(
        project_id=draft.project_id,
        nodes=draft.nodes,
        nets=[
            Net(
                net_id="_draft_placeholder",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id=draft.nodes[0].node_id, pin_id="GND"),
                ],
            )
        ],
    )


@router.post("/architect/auto-wire", response_model=AutoWireResponse)
def auto_wire_schematic(body: AutoWireRequest) -> AutoWireResponse:
    manifests = body.manifests if body.manifests is not None else load_all_manifests()
    if not manifests:
        raise HTTPException(status_code=500, detail="No manifests loaded on server")

    draft = body.project_state
    had_nets = bool(draft.nets)

    try:
        updated_state, wires_added = template_i2c_layout(
            _draft_to_project_state(draft), manifests
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not had_nets:
        updated_state = ProjectState(
            project_id=updated_state.project_id,
            nodes=updated_state.nodes,
            nets=[n for n in updated_state.nets if n.net_id != "_draft_placeholder"],
        )

    return AutoWireResponse(project_state=updated_state, wires_added=wires_added)
