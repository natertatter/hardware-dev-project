"use client";

import { useCallback, useEffect, useMemo } from "react";
import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  type NodeTypes,
} from "@xyflow/react";

import { HardwareNode } from "@/components/HardwareNode";
import { compileProjectState } from "@/utils/compileProjectState";
import {
  seedDemoSchematic,
  useSchematicStore,
} from "@/store/useSchematicStore";

import "@xyflow/react/dist/style.css";

const nodeTypes: NodeTypes = {
  hardware: HardwareNode,
};

export function SchematicEditor() {
  const nodes = useSchematicStore((s) => s.nodes);
  const edges = useSchematicStore((s) => s.edges);
  const catalog = useSchematicStore((s) => s.catalog);
  const projectId = useSchematicStore((s) => s.projectId);
  const onNodesChange = useSchematicStore((s) => s.onNodesChange);
  const onEdgesChange = useSchematicStore((s) => s.onEdgesChange);
  const onConnect = useSchematicStore((s) => s.onConnect);
  const addNode = useSchematicStore((s) => s.addNode);

  // Seed demo nodes once on first mount.
  useEffect(() => {
    if (nodes.length === 0) {
      seedDemoSchematic();
    }
  }, [nodes.length]);

  const handleValidate = useCallback(() => {
    try {
      const projectState = compileProjectState(nodes, edges, projectId);
      console.log("=== Compiled ProjectState ===");
      console.log(JSON.stringify(projectState, null, 2));
      console.log("=== End ProjectState ===");
    } catch (err) {
      console.error("Compile failed:", err);
    }
  }, [nodes, edges, projectId]);

  const defaultEdgeOptions = useMemo(
    () => ({ animated: true, style: { stroke: "#64748b" } }),
    []
  );

  return (
    <div className="schematic-editor">
      <aside className="schematic-editor__sidebar">
        <h2 className="schematic-editor__title">Component Catalog</h2>
        <p className="schematic-editor__hint">
          Click a component to place it on the canvas. Wire pins together, then
          validate.
        </p>
        <ul className="schematic-editor__catalog">
          {catalog.map((manifest) => (
            <li key={manifest.component_id}>
              <button
                type="button"
                className="schematic-editor__catalog-btn"
                onClick={() => addNode(manifest)}
              >
                <span className="schematic-editor__catalog-type">
                  {manifest.type}
                </span>
                <span className="schematic-editor__catalog-name">
                  {manifest.name}
                </span>
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="schematic-editor__validate-btn"
          onClick={handleValidate}
        >
          Validate Architecture
        </button>
      </aside>

      <div className="schematic-editor__canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          connectionMode={ConnectionMode.Loose}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background gap={20} size={1} color="#334155" />
          <Controls />
          <MiniMap
            nodeColor="#1e293b"
            maskColor="rgba(15, 23, 42, 0.75)"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
