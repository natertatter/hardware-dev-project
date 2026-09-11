"use client";

import { useCallback, useRef, useState } from "react";

import { uploadDatasheet } from "@/lib/api";
import { useSchematicStore } from "@/store/useSchematicStore";

export function DatasheetUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadCatalog = useSchematicStore((s) => s.actions.loadCatalog);
  const addNodeFromCatalog = useSchematicStore((s) => s.actions.addNodeFromCatalog);

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      setMessage(null);
      setError(null);
      try {
        const result = await uploadDatasheet(file);
        await loadCatalog();
        setMessage(result.message);
        addNodeFromCatalog({
          label: result.manifest.name,
          manifest: result.manifest,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [loadCatalog, addNodeFromCatalog],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
      e.target.value = "";
    },
    [handleFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  return (
    <div className="datasheet-upload">
      <h3 className="datasheet-upload__title">Upload Datasheet</h3>
      <p className="schematic-editor__hint">
        Drop a PDF datasheet or JSON manifest to add a new component to the library and place it on the canvas.
      </p>
      <div
        className="datasheet-upload__dropzone"
        onDrop={onDrop}
        onDragOver={onDragOver}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            inputRef.current?.click();
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.json"
          className="datasheet-upload__input"
          onChange={onInputChange}
          disabled={uploading}
        />
        {uploading ? (
          <span className="datasheet-upload__prompt">Processing…</span>
        ) : (
          <span className="datasheet-upload__prompt">
            Drop file here or click to browse
          </span>
        )}
      </div>
      {message && (
        <p className="panel-card__message panel-card__message--success">{message}</p>
      )}
      {error && (
        <p className="panel-card__message panel-card__message--error">{error}</p>
      )}
    </div>
  );
}
