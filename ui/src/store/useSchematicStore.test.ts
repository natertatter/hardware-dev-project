import { describe, expect, it, beforeEach, vi } from "vitest";

import { COMPONENT_CATALOG } from "@/data/mockCatalog";
import { useSchematicStore } from "@/store/useSchematicStore";

describe("useSchematicStore", () => {
  beforeEach(() => {
    useSchematicStore.setState({
      nodes: [],
      edges: [],
      catalog: COMPONENT_CATALOG.map((manifest) => ({
        label: manifest.name,
        manifest,
      })),
      catalogLoaded: true,
      catalogError: null,
      catalogSource: "api",
      validationStatus: "idle",
      validationIssues: [],
      validationMessage: null,
      schematicApproved: false,
      firmwareStatus: "idle",
      firmwareOutputDir: null,
      firmwareMessage: null,
      autoWireStatus: "idle",
      autoWireMessage: null,
    });
  });

  it("adds a node from the catalog", () => {
    useSchematicStore.getState().actions.addNodeFromCatalog({
      label: "MCU",
      manifest: COMPONENT_CATALOG[0],
    });

    const { nodes } = useSchematicStore.getState();
    expect(nodes).toHaveLength(1);
    expect(nodes[0].data.manifest.component_id).toBe("mcu_rp2040");
  });

  it("clears schematic approval when the canvas changes", () => {
    useSchematicStore.setState({ schematicApproved: true, firmwareStatus: "success" });

    useSchematicStore.getState().actions.addNodeFromCatalog({
      label: "MCU",
      manifest: COMPONENT_CATALOG[0],
    });

    const state = useSchematicStore.getState();
    expect(state.schematicApproved).toBe(false);
    expect(state.firmwareStatus).toBe("idle");
    expect(state.autoWireStatus).toBe("idle");
  });

  it("rejects auto-wire when the catalog is empty", async () => {
    useSchematicStore.setState({ catalog: [], catalogLoaded: true });

    await useSchematicStore.getState().actions.autoWire();

    const state = useSchematicStore.getState();
    expect(state.autoWireStatus).toBe("error");
    expect(state.autoWireMessage).toMatch(/catalog is empty/i);
  });

  it("falls back to the built-in catalog when the API is unavailable", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Failed to fetch"));
    useSchematicStore.setState({
      catalog: [],
      catalogLoaded: false,
      catalogError: null,
      catalogSource: null,
    });
    await useSchematicStore.getState().actions.loadCatalog();

    const state = useSchematicStore.getState();
    expect(state.catalogLoaded).toBe(true);
    expect(state.catalogError).toBeNull();
    expect(state.catalogSource).toBe("mock");
    expect(state.catalog.length).toBeGreaterThan(0);

    globalThis.fetch = originalFetch;
  });
});
