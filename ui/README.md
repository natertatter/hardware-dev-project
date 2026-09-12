# EDA Platform UI

Next.js + React Flow schematic editor. Compiles nodes and edges into backend `ProjectState` JSON and calls the FastAPI backend for validation, auto-wire, operations, and firmware generation.

## Quick start

```bash
cd ui
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev   # http://localhost:3000
npm run test       # vitest (stores, net compiler, protocol profiles)
npm run build      # production build
```

## Architecture

| Path | Responsibility |
|------|----------------|
| `src/store/useSchematicStore.ts` | Canvas, catalog (API or offline mock), validation, auto-wire, firmware |
| `src/store/useOperationsStore.ts` | Operations narrative, refine/validate/merge/approve |
| `src/components/SchematicEditor.tsx` | Shell: library sidebar, canvas, validation + operations panels |
| `src/components/HardwareNode.tsx` | Custom node with pin handles and protocol selector |
| `src/components/DatasheetUpload.tsx` | Librarian upload to API |
| `src/utils/compileProjectState.ts` | Union-Find net compiler → `ProjectState` |
| `src/lib/api.ts` | Typed fetch wrappers for `/api/v1/*` |

User guide: [`../docs/HOW_TO.md`](../docs/HOW_TO.md).
