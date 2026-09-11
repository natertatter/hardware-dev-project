"use client";

import {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { useCallback, useEffect, useRef } from "react";

import { HardwareNode } from "@/components/HardwareNode";
import { DatasheetUpload } from "@/components/DatasheetUpload";
import { OperationsPanel } from "@/components/OperationsPanel";
import { ValidationPanel } from "@/components/ValidationPanel";
import { useOperationsStore } from "@/store/useOperationsStore";
import { useSchematicStore } from "@/store/useSchematicStore";
import type { CatalogEntry } from "@/types/schemas";

import "@xyflow/react/dist/style.css";

const nodeTypes = { hardware: HardwareNode };

const defaultEdgeOptions = {
  type: "smoothstep" as const,
  style: { stroke: "var(--lab-border)", strokeWidth: 2 },
};

function SchematicCanvas() {
  const nodes = useSchematicStore((s) => s.nodes);
  const edges = useSchematicStore((s) => s.edges);
  const catalog = useSchematicStore((s) => s.catalog);
  const catalogLoaded = useSchematicStore((s) => s.catalogLoaded);
  const catalogSource = useSchematicStore((s) => s.catalogSource);
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
  const { screenToFlowPosition } = useReactFlow();
  const canvasRef = useRef<HTMLElement>(null);

  const narrative = useOperationsStore((s) => s.narrative);
  const refinedSequence = useOperationsStore((s) => s.refinedSequence);
  const operationsStatus = useOperationsStore((s) => s.operationsStatus);
  const operationsIssues = useOperationsStore((s) => s.operationsIssues);
  const operationsMessage = useOperationsStore((s) => s.operationsMessage);
  const refineMessage = useOperationsStore((s) => s.refineMessage);
  const operationsApproved = useOperationsStore((s) => s.operationsApproved);
  const opsActions = useOperationsStore((s) => s.actions);

  useEffect(() => {
    actions.loadCatalog();
  }, [actions]);

  const placeFromCatalog = useCallback(
    (entry: CatalogEntry) => {
      const canvas = canvasRef.current;
      if (canvas) {
        const rect = canvas.getBoundingClientRect();
        const center = screenToFlowPosition({
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        });
        const stackOffset = nodes.length % 6;
        actions.addNodeFromCatalog(entry, {
          x: center.x + stackOffset * 28 - 70,
          y: center.y + stackOffset * 24 - 50,
        });
        return;
      }
      actions.addNodeFromCatalog(entry);
    },
    [actions, nodes.length, screenToFlowPosition],
  );

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
          <div className="editor-shell__logo" aria-hidden="true" />
          <div>
            <h1>EDA Platform</h1>
            <p className="editor-shell__tagline">Industrial schematic lab</p>
          </div>
        </div>
        <div className="editor-shell__actions">
          <button
            type="button"
            onClick={() => actions.autoWire()}
            className="editor-shell__btn"
          >
            Auto-Wire
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
            {schematicApproved ? "Approved" : "Approve"}
          </button>
          <button
            type="button"
            onClick={() => actions.generateFirmware()}
            disabled={
              !schematicApproved ||
              validationStatus !== "pass" ||
              firmwareStatus === "generating" ||
              (refinedSequence != null && !operationsApproved)
            }
            className="editor-shell__btn editor-shell__btn--firmware"
          >
            {firmwareStatus === "generating" ? "Generating…" : "Generate Firmware"}
          </button>
        </div>
      </header>

      <div className="editor-shell__body">
        <aside className="schematic-editor__sidebar">
          <DatasheetUpload />
          <h2 className="schematic-editor__title">Parts Library</h2>
          <p className="schematic-editor__hint">
            Click a module to place it on the drafting table. Use the protocol switch on multi-bus parts.
          </p>
          {catalogSource === "mock" && (
            <p className="schematic-editor__offline-note">
              API offline — using built-in parts library. Start the API for live manifests.
            </p>
          )}
          {!catalogLoaded ? (
            <p className="schematic-editor__hint">Loading catalog…</p>
          ) : catalogError ? (
            <>
              <p className="panel-card__message panel-card__message--error">{catalogError}</p>
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
                    onClick={() => placeFromCatalog(entry)}
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

        <main className="schematic-editor__canvas" ref={canvasRef}>
          {nodes.length === 0 && (
            <div className="canvas-empty">
              <div className="canvas-empty__reticle" aria-hidden="true" />
              <p className="canvas-empty__title">Drafting table ready</p>
              <p className="canvas-empty__text">
                Place modules from the library. Wire pins with 90° traces, then validate and compile firmware.
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
            connectionLineStyle={{ stroke: "var(--pop-blue)", strokeWidth: 2 }}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.25}
            maxZoom={2}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="var(--lab-border)"
            />
            <Controls />
            <MiniMap
              nodeColor="var(--lab-surface)"
              maskColor="rgba(28, 30, 33, 0.92)"
              className="schematic-minimap"
            />
          </ReactFlow>
        </main>

        <aside className="editor-shell__panel">
          <OperationsPanel
            narrative={narrative}
            onNarrativeChange={opsActions.setNarrative}
            fidelity={refinedSequence?.fidelity ?? null}
            refinedSteps={refinedSequence?.steps ?? []}
            openQuestions={refinedSequence?.open_questions ?? []}
            status={operationsStatus}
            issues={operationsIssues}
            message={operationsMessage}
            refineMessage={refineMessage}
            operationsApproved={operationsApproved}
            onCaptureDraft={opsActions.captureDraft}
            onRefine={opsActions.refine}
            onValidate={opsActions.validate}
            onMerge={opsActions.mergeToMaster}
            onApprove={opsActions.approveOperations}
          />
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
