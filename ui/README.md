# EDA Platform UI

Next.js + React Flow schematic editor. Compiles visual nodes/edges into backend `ProjectState` JSON.

## Quick Start

```bash
cd ui
npm install
npm run dev        # http://localhost:3000
npm run test       # vitest unit tests (net compiler)
npm run build      # production build
```

## Architecture

| Path | Responsibility |
|------|----------------|
| `src/store/useSchematicStore.ts` | Zustand store — nodes, edges, catalog, actions |
| `src/components/HardwareNode.tsx` | Custom React Flow node with dynamic pin Handles |
| `src/components/SchematicEditor.tsx` | Canvas MVP + "Validate Architecture" button |
| `src/utils/compileProjectState.ts` | Union-Find net compiler → `ProjectState` JSON |
| `src/data/mockCatalog.ts` | MCU + INA219 ComponentManifest fixtures |

Click **Validate Architecture** to compile the canvas and `console.log` the resulting `ProjectState`.
