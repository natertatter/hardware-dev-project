const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

import type { ComponentManifest, ProjectState } from "@/types/schemas";

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
