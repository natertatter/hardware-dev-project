"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import { useCallback, useEffect } from "react";

import { HardwareNode } from "@/components/HardwareNode";
import { ValidationPanel } from "@/components/ValidationPanel";
import { useSchematicStore } from "@/store/useSchematicStore";

import "@xyflow/react/dist/style.css";

const nodeTypes = { hardware: HardwareNode };

function SchematicCanvas() {
  const nodes = useSchematicStore((s) => s.nodes);
  const edges = useSchematicStore((s) => s.edges);
  const catalog = useSchematicStore((s) => s.catalog);
  const catalogLoaded = useSchematicStore((s) => s.catalogLoaded);
  const validationStatus = useSchematicStore((s) => s.validationStatus);
  const validationIssues = useSchematicStore((s) => s.validationIssues);
  const validationMessage = useSchematicStore((s) => s.validationMessage);
  const schematicApproved = useSchematicStore((s) => s.schematicApproved);
  const firmwareStatus = useSchematicStore((s) => s.firmwareStatus);
  const firmwareOutputDir = useSchematicStore((s) => s.firmwareOutputDir);
  const firmwareMessage = useSchematicStore((s) => s.firmwareMessage);
  const actions = useSchematicStore((s) => s.actions);

  useEffect(() => {
    actions.loadCatalog();
  }, [actions]);

  const onNodesChange = useCallback(
    (changes: Parameters<typeof actions.onNodesChange>[0]) => actions.onNodesChange(changes),
    [actions],
  );
  const onEdgesChange = useCallback(
    (changes: Parameters<typeof actions.onEdgesChange>[0]) => actions.onEdgesChange(changes),
    [actions],
  );
  const onConnect = useCallback(
    (connection: Parameters<typeof actions.onConnect>[0]) => actions.onConnect(connection),
    [actions],
  );

  return (
    <div className="flex h-screen w-full flex-col bg-slate-950 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div>
          <h1 className="text-lg font-semibold">EDA Platform — Schematic Editor</h1>
          <p className="text-xs text-slate-400">
            Drag components, wire pins, validate against the Logic Checker API.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => actions.autoWire()}
            className="rounded-md border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800"
          >
            Auto-Wire (I2C)
          </button>
          <button
            type="button"
            onClick={() => actions.validateArchitecture()}
            disabled={validationStatus === "validating"}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            {validationStatus === "validating" ? "Validating…" : "Validate Architecture"}
          </button>
          <button
            type="button"
            onClick={() => actions.approveSchematic()}
            disabled={validationStatus !== "pass" || schematicApproved}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium hover:bg-blue-500 disabled:opacity-50"
          >
            {schematicApproved ? "Schematic Approved" : "Approve Schematic"}
          </button>
          <button
            type="button"
            onClick={() => actions.generateFirmware()}
            disabled={
              !schematicApproved ||
              validationStatus !== "pass" ||
              firmwareStatus === "generating"
            }
            className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium hover:bg-violet-500 disabled:opacity-50"
          >
            {firmwareStatus === "generating" ? "Generating…" : "Generate Firmware"}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 shrink-0 overflow-y-auto border-r border-slate-800 p-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Component Catalog
          </h2>
          {!catalogLoaded ? (
            <p className="text-xs text-slate-500">Loading manifests…</p>
          ) : (
            <ul className="space-y-2">
              {catalog.map((entry) => (
                <li key={entry.manifest.component_id}>
                  <button
                    type="button"
                    onClick={() => actions.addNodeFromCatalog(entry)}
                    className="w-full rounded border border-slate-700 px-2 py-1.5 text-left text-sm hover:border-slate-500 hover:bg-slate-900"
                  >
                    {entry.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="relative flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
            className="bg-slate-950"
          >
            <Background gap={16} color="#334155" />
            <Controls />
            <MiniMap nodeColor="#1e293b" maskColor="rgba(15,23,42,0.8)" />
          </ReactFlow>
        </main>

        <aside className="w-72 shrink-0 overflow-y-auto border-l border-slate-800 p-3">
          <ValidationPanel
            status={validationStatus}
            issues={validationIssues}
            message={validationMessage}
            schematicApproved={schematicApproved}
            firmwareStatus={firmwareStatus}
            firmwareOutputDir={firmwareOutputDir}
            firmwareMessage={firmwareMessage}
          />
        </aside>
      </div>
    </div>
  );
}

export function SchematicEditor() {
  return (
    <ReactFlowProvider>
      <SchematicCanvas />
    </ReactFlowProvider>
  );
}
