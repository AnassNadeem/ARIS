import type { IJsonModel, Model } from "flexlayout-react";

export const LAYOUT_STORAGE_KEY = "aris_layout_v1";

function isJsonRow(value: unknown): value is IJsonModel["layout"] {
  return Boolean(value && typeof value === "object" && (value as { type?: string }).type === "row");
}

export function isPersistedLayout(value: unknown): value is IJsonModel {
  if (!value || typeof value !== "object") return false;
  return isJsonRow((value as IJsonModel).layout);
}

export function loadPersistedLayout(): IJsonModel | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isPersistedLayout(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function savePersistedLayout(model: Model): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(model.toJson()));
  } catch {
    // quota / private mode — layout still works in-memory
  }
}

/** Walks the persisted JSON for a row's weight (used to restore analytics extraVh). */
export function rowWeightFromLayout(json: IJsonModel, rowId: string): number | null {
  const visit = (node: unknown): number | null => {
    if (!node || typeof node !== "object") return null;
    const rec = node as { id?: string; weight?: number; children?: unknown[] };
    if (rec.id === rowId && typeof rec.weight === "number") return rec.weight;
    if (!Array.isArray(rec.children)) return null;
    for (const child of rec.children) {
      const found = visit(child);
      if (found != null) return found;
    }
    return null;
  };
  return visit(json.layout);
}
