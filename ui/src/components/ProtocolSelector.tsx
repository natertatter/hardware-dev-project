"use client";

import { useCallback } from "react";

import { useSchematicStore } from "@/store/useSchematicStore";
import { availableProtocols } from "@/utils/protocolProfiles";

interface ProtocolSelectorProps {
  nodeId: string;
  selectedProtocol: string | null;
  protocols: string[];
}

export function ProtocolSelector({
  nodeId,
  selectedProtocol,
  protocols,
}: ProtocolSelectorProps) {
  const setNodeProtocol = useSchematicStore((s) => s.actions.setNodeProtocol);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setNodeProtocol(nodeId, e.target.value);
    },
    [nodeId, setNodeProtocol],
  );

  if (protocols.length <= 1) {
    return null;
  }

  return (
    <div className="protocol-selector" onClick={(e) => e.stopPropagation()}>
      <label className="protocol-selector__label">
        <span>Protocol</span>
        <select
          className="protocol-selector__select"
          value={selectedProtocol ?? protocols[0]}
          onChange={onChange}
        >
          {protocols.map((proto) => (
            <option key={proto} value={proto}>
              {proto}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

/** Derive protocols for a node from its manifest. */
export function useNodeProtocols(manifest: Parameters<typeof availableProtocols>[0]) {
  return availableProtocols(manifest);
}
