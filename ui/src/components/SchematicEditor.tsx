"use client";

import {
  Background,
  ConnectionMode,
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

const defaultEdgeOptions = {
  style: { stroke: "#22d3ee", strokeWidth: 2 },
};

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
        <div className="editor-shell__brand">
          <div className="editor-shell__logo" aria-hidden="true">⬡</div>
          <div>
            <h1>EDA Platform</h1>
            <p className="editor-shell__tagline">Design · Validate · Generate</p>
          </div>
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
            {validationStatus === "validating" ? "Validating…" : "Validate"}
          </button>
          <button
            type="button"
            onClick={() => actions.approveSchematic()}
            disabled={validationStatus !== "pass" || schematicApproved}
            className="editor-shell__btn editor-shell__btn--approve"
          >
            {schematicApproved ? "Approved ✓" : "Approve"}
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
          <h2 className="schematic-editor__title">Parts Library</h2>
          <p className="schematic-editor__hint">
            Click a component to place it on the canvas. Drag to reposition, connect pin to pin.
          </p>
          {!catalogLoaded && !catalogError ? (
            <p className="schematic-editor__hint">Loading catalog…</p>
          ) : catalogError ? (
            <>
              <p className="panel-card__message" style={{ color: "var(--accent-rose)" }}>
                {catalogError}
              </p>
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
          {nodes.length === 0 && (
            <div className="canvas-empty">
              <div className="canvas-empty__icon" aria-hidden="true">⬡</div>
              <p className="canvas-empty__title">Your schematic starts here</p>
              <p className="canvas-empty__text">
                Pick a part from the library, wire the pins, then validate and generate firmware for your Raspberry Pi.
              </p>
            </div>
          )}
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
          >
            <Background gap={20} color="rgba(34, 211, 238, 0.06)" />
            <Controls />
            <MiniMap
              nodeColor="#1a2236"
              maskColor="rgba(6, 8, 15, 0.85)"
              style={{ borderRadius: 8 }}
            />
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
