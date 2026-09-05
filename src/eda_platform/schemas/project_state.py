"""Pydantic models for the ProjectState schema (Systems Architect output)."""

from pydantic import BaseModel, Field, field_validator

from eda_platform.schemas.enums import NetType


class Node(BaseModel):
    """An instantiated component placed on the schematic."""

    node_id: str = Field(..., min_length=1, description="Unique instance id (e.g., sensor_1)")
    component_id: str = Field(..., min_length=1, description="References a ComponentManifest")
    assigned_i2c_address: str | None = Field(
        default=None, description="Override I2C address in hex (e.g., 0x40)"
    )

    @field_validator("assigned_i2c_address")
    @classmethod
    def validate_i2c_address(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.strip().lower()
        if not normalized.startswith("0x"):
            raise ValueError("I2C address must be hex prefixed with 0x")
        int(normalized, 16)
        return normalized


class NetConnection(BaseModel):
    """A single pin attachment to a net."""

    node_id: str = Field(..., min_length=1)
    pin_id: str = Field(..., min_length=1)


class Net(BaseModel):
    """Electrical net connecting one or more node pins."""

    net_id: str = Field(..., min_length=1, description="Net identifier (e.g., net_vcc)")
    net_type: NetType
    connections: list[NetConnection] = Field(..., min_length=1)


class ProjectState(BaseModel):
    """Visual schematic state produced by the Systems Architect agent."""

    project_id: str = Field(..., min_length=1)
    nodes: list[Node] = Field(..., min_length=1)
    nets: list[Net] = Field(..., min_length=1)

    @field_validator("nodes")
    @classmethod
    def unique_node_ids(cls, nodes: list[Node]) -> list[Node]:
        ids = [n.node_id for n in nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node_id values must be unique within a project")
        return nodes

    @field_validator("nets")
    @classmethod
    def unique_net_ids(cls, nets: list[Net]) -> list[Net]:
        ids = [n.net_id for n in nets]
        if len(ids) != len(set(ids)):
            raise ValueError("net_id values must be unique within a project")
        return nets
