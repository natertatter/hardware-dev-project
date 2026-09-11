const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

import type { ComponentManifest, OperationsSequence, ProjectState } from "@/types/schemas";

export interface ValidationIssue {
  rule: string;
  severity: string;
  message: string;
  net_id?: string | null;
  node_id?: string | null;
  pin_id?: string | null;
}

export interface ValidateResponse {
  valid: boolean;
  errors: ValidationIssue[];
}

export interface AutoWireResponse {
  project_state: ProjectState;
  wires_added: number;
}

export interface GenerateFirmwareResponse {
  success: boolean;
  project_id: string;
  output_dir: string;
  files_written: string[];
  message: string;
}

export interface UploadManifestResponse {
  manifest: ComponentManifest;
  saved_path: string;
  message: string;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} failed (${res.status}): ${detail}`);
  }

  return res.json() as Promise<T>;
}

export async function fetchManifests(): Promise<ComponentManifest[]> {
  const data = await apiFetch<{ manifests: ComponentManifest[] }>("/api/v1/manifests");
  return data.manifests;
}

export async function validateProjectState(
  projectState: ProjectState
): Promise<ValidateResponse> {
  return apiFetch<ValidateResponse>("/api/v1/validate", {
    method: "POST",
    body: JSON.stringify({ project_state: projectState }),
  });
}

export async function autoWireProjectState(
  projectState: ProjectState
): Promise<AutoWireResponse> {
  return apiFetch<AutoWireResponse>("/api/v1/architect/auto-wire", {
    method: "POST",
    body: JSON.stringify({ project_state: projectState }),
  });
}

export async function generateFirmware(
  projectState: ProjectState,
  approved: boolean,
  operations?: OperationsSequence | null,
  operationsApproved?: boolean,
): Promise<GenerateFirmwareResponse> {
  return apiFetch<GenerateFirmwareResponse>("/api/v1/firmware/generate", {
    method: "POST",
    body: JSON.stringify({
      project_state: projectState,
      approved,
      operations: operations ?? null,
      operations_approved: operationsApproved ?? false,
    }),
  });
}

export interface RefineOperationsResponse {
  refined: OperationsSequence;
  fidelity_promoted: boolean;
  previous_fidelity: string;
  steps_bound: number;
  questions_added: number;
  warnings: string[];
}

export interface OperationsValidationIssue {
  rule: string;
  severity: string;
  message: string;
  step_id?: string | null;
  node_id?: string | null;
}

export interface ValidateOperationsResponse {
  valid: boolean;
  errors: OperationsValidationIssue[];
}

export async function refineOperations(
  operations: OperationsSequence,
  projectState: ProjectState,
): Promise<RefineOperationsResponse> {
  return apiFetch<RefineOperationsResponse>("/api/v1/operations/refine", {
    method: "POST",
    body: JSON.stringify({ operations, project_state: projectState, persist: false }),
  });
}

export async function validateOperations(
  operations: OperationsSequence,
  projectState: ProjectState,
): Promise<ValidateOperationsResponse> {
  return apiFetch<ValidateOperationsResponse>("/api/v1/operations/validate", {
    method: "POST",
    body: JSON.stringify({ operations, project_state: projectState }),
  });
}

export async function mergeOperations(
  operations: OperationsSequence,
  projectState?: ProjectState,
): Promise<{ master: OperationsSequence; message: string }> {
  return apiFetch("/api/v1/operations/merge", {
    method: "POST",
    body: JSON.stringify({
      operations,
      project_state: projectState ?? null,
      bump_version: true,
    }),
  });
}

export async function saveOperationsDraft(
  projectId: string,
  operations: OperationsSequence,
): Promise<{ saved_path: string }> {
  return apiFetch(`/api/v1/projects/${projectId}/operations/drafts`, {
    method: "POST",
    body: JSON.stringify({ operations }),
  });
}

export async function uploadDatasheet(file: File): Promise<UploadManifestResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/v1/librarian/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }

  return res.json() as Promise<UploadManifestResponse>;
}
