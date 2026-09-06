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
  const catalogError = useSchematicStore((s) => s.catalogError);
  const autoWireStatus = useSchematicStore((s) => s.autoWireStatus);
  const autoWireMessage = useSchematicStore((s) => s.autoWireMessage);
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
    <div className="editor-shell">
      <header className="editor-shell__toolbar">
        <div>
          <h1>EDA Platform — Schematic Editor</h1>
          <p>Drag components, wire pins, validate against the Logic Checker API.</p>
        </div>
        <div className="editor-shell__actions">
          <button
            type="button"
            onClick={() => actions.autoWire()}
            className="editor-shell__btn"
          >
            Auto-Wire (I2C)
          </button>
          <button
            type="button"
            onClick={() => actions.validateArchitecture()}
            disabled={validationStatus === "validating"}
            className="editor-shell__btn editor-shell__btn--validate"
          >
            {validationStatus === "validating" ? "Validating…" : "Validate Architecture"}
          </button>
          <button
            type="button"
            onClick={() => actions.approveSchematic()}
            disabled={validationStatus !== "pass" || schematicApproved}
            className="editor-shell__btn editor-shell__btn--approve"
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
            className="editor-shell__btn editor-shell__btn--firmware"
          >
            {firmwareStatus === "generating" ? "Generating…" : "Generate Firmware"}
          </button>
        </div>
      </header>

      <div className="editor-shell__body">
        <aside className="schematic-editor__sidebar">
          <h2 className="schematic-editor__title">Component Catalog</h2>
          <p className="schematic-editor__hint">
            Click a part to place it on the canvas. Drag nodes to reposition them.
          </p>
          {!catalogLoaded && !catalogError ? (
            <p className="schematic-editor__hint">Loading manifests…</p>
          ) : catalogError ? (
            <>
              <p className="editor-shell__status editor-shell__status--fail">{catalogError}</p>
              <button
                type="button"
                onClick={() => actions.loadCatalog()}
                className="schematic-editor__catalog-btn"
              >
                Retry
              </button>
            </>
          ) : (
            <ul className="schematic-editor__catalog">
              {catalog.map((entry) => (
                <li key={entry.manifest.component_id}>
                  <button
                    type="button"
                    onClick={() => actions.addNodeFromCatalog(entry)}
                    className="schematic-editor__catalog-btn"
                  >
                    <span className="schematic-editor__catalog-type">{entry.manifest.type}</span>
                    <span className="schematic-editor__catalog-name">{entry.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="schematic-editor__canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background gap={16} color="#334155" />
            <Controls />
            <MiniMap nodeColor="#1e293b" maskColor="rgba(15,23,42,0.8)" />
          </ReactFlow>
        </main>

        <aside className="editor-shell__panel">
          <ValidationPanel
            status={validationStatus}
            issues={validationIssues}
            message={validationMessage}
            schematicApproved={schematicApproved}
            autoWireStatus={autoWireStatus}
            autoWireMessage={autoWireMessage}
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
