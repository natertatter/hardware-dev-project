"""Template architect API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.agents.architect.template_layout import template_auto_wire
from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.schemas import AutoWireRequest, AutoWireResponse
from eda_platform.schemas import ComponentManifest, Net, NetConnection, NetType, PinType, ProjectState

router = APIRouter(prefix="/api/v1", tags=["architect"])


def _draft_to_project_state(
    draft, manifests: dict[str, ComponentManifest]
) -> ProjectState:
    """Convert a UI schematic draft into a ProjectState for template processing."""
    if draft.nets:
        return ProjectState(
            project_id=draft.project_id,
            nodes=draft.nodes,
            nets=draft.nets,
        )

    first = draft.nodes[0]
    gnd_pin_id = "GND"
    manifest = manifests.get(first.component_id)
    if manifest is not None:
        gnd_pins = [p for p in manifest.pins if p.pin_type == PinType.GND]
        if gnd_pins:
            gnd_pin_id = gnd_pins[0].pin_id

    # Placement-only draft: synthesize a throwaway net so ProjectState validates.
    return ProjectState(
        project_id=draft.project_id,
        nodes=draft.nodes,
        nets=[
            Net(
                net_id="_draft_placeholder",
                net_type=NetType.SIGNAL,
                connections=[
                    NetConnection(node_id=first.node_id, pin_id=gnd_pin_id),
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
        updated_state, wires_added = template_auto_wire(
            _draft_to_project_state(draft, manifests), manifests
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
