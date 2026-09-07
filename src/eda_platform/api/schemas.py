"""API request/response DTOs."""

from pydantic import BaseModel, Field

from eda_platform.schemas import ComponentManifest, Net, Node, ProjectState


class SchematicDraft(BaseModel):
    """In-progress schematic from the UI; nets may be empty before first wire."""

    project_id: str = Field(default="schematic_project", min_length=1)
    nodes: list[Node] = Field(..., min_length=1)
    nets: list[Net] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    project_state: ProjectState
    manifests: dict[str, ComponentManifest] | None = Field(
        default=None,
        description="Optional manifest overrides; server catalog used when omitted",
    )


class ValidationIssueResponse(BaseModel):
    rule: str
    severity: str
    message: str
    net_id: str | None = None
    node_id: str | None = None
    pin_id: str | None = None


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationIssueResponse]


class ManifestListResponse(BaseModel):
    manifests: list[ComponentManifest]


class AutoWireRequest(BaseModel):
    """Template architect: wire MCU to peripherals already placed on the schematic."""

    project_state: SchematicDraft
    manifests: dict[str, ComponentManifest] | None = Field(
        default=None,
        description="Optional manifest overrides; server catalog used when omitted",
    )


class AutoWireResponse(BaseModel):
    project_state: ProjectState
    wires_added: int


class GenerateFirmwareRequest(BaseModel):
    project_state: ProjectState
    approved: bool = Field(
        ...,
        description="Must be true — schematic must be explicitly approved before codegen",
    )
    manifests: dict[str, ComponentManifest] | None = Field(
        default=None,
        description="Optional manifest overrides; server catalog used when omitted",
    )


class GenerateFirmwareResponse(BaseModel):
    success: bool
    project_id: str
    output_dir: str
    files_written: list[str]
    message: str


class UploadManifestResponse(BaseModel):
    manifest: ComponentManifest
    saved_path: str
    message: str
