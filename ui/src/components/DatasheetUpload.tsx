"use client";

import { useCallback, useRef, useState } from "react";

import { ManifestReviewForm } from "@/components/ManifestReviewForm";
import { commitManifest, uploadDatasheet } from "@/lib/api";
import {
  prepareReviewManifest,
  type ExtractionIssue,
} from "@/lib/manifestReview";
import type { ComponentManifest } from "@/types/schemas";
import { useSchematicStore } from "@/store/useSchematicStore";

interface PendingReview {
  manifest: ComponentManifest;
  issues: ExtractionIssue[];
  message: string;
  extractionSource: string;
}

export function DatasheetUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<PendingReview | null>(null);
  const loadCatalog = useSchematicStore((s) => s.actions.loadCatalog);
  const addNodeFromCatalog = useSchematicStore((s) => s.actions.addNodeFromCatalog);

  const placeManifest = useCallback(
    (manifest: ComponentManifest) => {
      addNodeFromCatalog({
        label: manifest.name,
        manifest,
      });
    },
    [addNodeFromCatalog],
  );

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      setMessage(null);
      setError(null);
      try {
        const result = await uploadDatasheet(file);
        if (result.committed === false) {
          setReview({
            manifest: prepareReviewManifest(result.manifest),
            issues: result.issues ?? [],
            message: result.message,
            extractionSource: result.extraction_source ?? "template",
          });
          return;
        }
        setReview(null);
        await loadCatalog();
        setMessage(result.message);
        placeManifest(result.manifest);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [loadCatalog, placeManifest],
  );

  const saveReview = useCallback(async () => {
    if (!review) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await commitManifest(review.manifest);
      await loadCatalog();
      placeManifest(saved.manifest);
      setReview(null);
      setMessage(saved.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [review, loadCatalog, placeManifest]);

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
        Drop a JSON manifest to add it to the library, or a PDF datasheet to extract a draft you can review before saving.
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
      {review && (
        <ManifestReviewForm
          manifest={review.manifest}
          issues={review.issues}
          note={review.message}
          extractionSource={review.extractionSource}
          saving={saving}
          error={error}
          onChange={(manifest) => setReview({ ...review, manifest })}
          onSave={() => {
            void saveReview();
          }}
          onDiscard={() => {
            setReview(null);
            setError(null);
          }}
        />
      )}
      {message && (
        <p className="panel-card__message panel-card__message--success">{message}</p>
      )}
      {error && !review && (
        <p className="panel-card__message panel-card__message--error">{error}</p>
      )}
    </div>
  );
}
