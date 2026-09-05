import { describe, expect, it, beforeEach } from "vitest";

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
      validationStatus: "idle",
      validationIssues: [],
      validationMessage: null,
      schematicApproved: false,
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
    useSchematicStore.setState({ schematicApproved: true });

    useSchematicStore.getState().actions.addNodeFromCatalog({
      label: "MCU",
      manifest: COMPONENT_CATALOG[0],
    });

    expect(useSchematicStore.getState().schematicApproved).toBe(false);
  });
});
