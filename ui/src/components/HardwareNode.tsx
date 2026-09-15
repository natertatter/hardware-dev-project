"use client";

import { memo, useMemo } from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";

import { ProtocolSelector } from "@/components/ProtocolSelector";
import { useSchematicStore } from "@/store/useSchematicStore";
import type { HardwareNodeData, Pin } from "@/types/schemas";
import { pinSide } from "@/utils/pinSide";
import {
  availableProtocols,
  defaultProtocol,
  pinsForProtocol,
} from "@/utils/protocolProfiles";

export { pinSide } from "@/utils/pinSide";

function PinRow({
  pin,
  side,
  index,
  total,
}: {
  pin: Pin;
  side: "left" | "right";
  index: number;
  total: number;
}) {
  const topPct = ((index + 1) / (total + 1)) * 100;
  const handleType = side === "left" ? "target" : "source";

  return (
    <div
      className={`hardware-node__pin hardware-node__pin--${side}`}
      style={{ top: `${topPct}%` }}
    >
      {side === "left" && (
        <Handle
          type={handleType}
          position={Position.Left}
          id={pin.pin_id}
          className="hardware-node__handle"
        />
      )}
      <span className="hardware-node__pin-label">
        <span className="hardware-node__pin-id">{pin.pin_id}</span>
        <span className="hardware-node__pin-type">{pin.pin_type}</span>
      </span>
      {side === "right" && (
        <Handle
          type={handleType}
          position={Position.Right}
          id={pin.pin_id}
          className="hardware-node__handle"
        />
      )}
    </div>
  );
}

function HardwareNodeComponent({ id, data }: NodeProps<Node<HardwareNodeData>>) {
  const { manifest, selected_protocol } = data;
  const removeNode = useSchematicStore((s) => s.actions.removeNode);
  const edges = useSchematicStore((s) => s.edges);
  const protocols = useMemo(() => availableProtocols(manifest), [manifest]);
  const activeProtocol =
    selected_protocol ?? defaultProtocol(manifest) ?? protocols[0] ?? null;
  const visiblePins = useMemo(() => {
    const protoPins = pinsForProtocol(manifest, activeProtocol);
    const connectedIds = new Set<string>();
    for (const edge of edges) {
      if (edge.source === id && edge.sourceHandle) connectedIds.add(edge.sourceHandle);
      if (edge.target === id && edge.targetHandle) connectedIds.add(edge.targetHandle);
    }
    if (connectedIds.size === 0) {
      return protoPins;
    }
    const byId = new Map(manifest.pins.map((p) => [p.pin_id, p]));
    const seen = new Set(protoPins.map((p) => p.pin_id));
    const extras = [...connectedIds]
      .map((pinId) => byId.get(pinId))
      .filter((pin): pin is Pin => pin != null && !seen.has(pin.pin_id));
    return [...protoPins, ...extras];
  }, [manifest, activeProtocol, edges, id]);

  const leftPins = visiblePins.filter((p) => pinSide(manifest, p) === "left");
  const rightPins = visiblePins.filter((p) => pinSide(manifest, p) === "right");

  return (
    <div className="hardware-node">
      <header className="hardware-node__header">
        <div className="hardware-node__header-row">
          <span className="hardware-node__type">{manifest.type}</span>
          <button
            type="button"
            className="hardware-node__remove nodrag nopan"
            aria-label={`Remove ${manifest.name} from schematic`}
            title="Remove board"
            onClick={(event) => {
              event.stopPropagation();
              removeNode(id);
            }}
            onPointerDown={(event) => event.stopPropagation()}
          >
            Remove
          </button>
        </div>
        <strong className="hardware-node__name">{manifest.name}</strong>
        <span className="hardware-node__id">{manifest.component_id}</span>
      </header>

      <ProtocolSelector
        nodeId={id}
        selectedProtocol={activeProtocol}
        protocols={protocols}
      />

      <div className="hardware-node__body">
        <div className="hardware-node__column hardware-node__column--left">
          {leftPins.map((pin, i) => (
            <PinRow
              key={pin.pin_id}
              pin={pin}
              side="left"
              index={i}
              total={leftPins.length}
            />
          ))}
        </div>
        <div className="hardware-node__column hardware-node__column--right">
          {rightPins.map((pin, i) => (
            <PinRow
              key={pin.pin_id}
              pin={pin}
              side="right"
              index={i}
              total={rightPins.length}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export const HardwareNode = memo(HardwareNodeComponent);
