import { SchematicEditor } from "@/components/SchematicEditor";

export default function Home() {
  return (
    <main className="app">
      <header className="app__header">
        <h1>Hardware Schematic Editor</h1>
        <p>Drag components, wire pins, then validate architecture.</p>
      </header>
      <SchematicEditor />
    </main>
  );
}
