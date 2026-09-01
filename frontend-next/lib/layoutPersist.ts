import type { IJsonModel, Model } from "flexlayout-react";

export const LAYOUT_STORAGE_KEY = "aris_layout_v3";

export const ANALYTICS_ROW_ID = "analytics-dock-row";
export const ANALYTICS_ADD_TABSET_ID = "analytics-add-tabset";
export const ANALYTICS_ADD_TAB_ID = "analytics-add-tab";

/** Component ids of tabs currently in a flexlayout JSON tree. */
export function componentsFromLayoutJson(json: { layout?: unknown }): string[] {
  const out: string[] = [];
  const visit = (node: unknown) => {
    if (!node || typeof node !== "object") return;
    const rec = node as { type?: string; component?: string; children?: unknown[] };
    if (rec.type === "tab" && typeof rec.component === "string") out.push(rec.component);
    if (Array.isArray(rec.children)) rec.children.forEach(visit);
  };
  visit(json.layout);
  return out;
}

/** Drop the desktop analytics "+" tab from saved layouts (add-slot is mobile-only). */
export function stripAnalyticsAddFromLayout(json: IJsonModel): IJsonModel {
  const visit = (node: unknown): unknown | null => {
    if (!node || typeof node !== "object") return node;
    const rec = node as { type?: string; id?: string; component?: string; children?: unknown[] };
    if (rec.type === "tab" && (rec.component === "analytics-add" || rec.id === ANALYTICS_ADD_TAB_ID)) {
      return null;
    }
    if (rec.id === ANALYTICS_ADD_TABSET_ID) return null;
    if (!Array.isArray(rec.children)) return rec;
    const children = rec.children.map(visit).filter((child): child is NonNullable<unknown> => child != null);
    if ((rec.type === "tabset" || rec.type === "row") && children.length === 0) return null;
    return { ...rec, children };
  };
  const layout = visit(json.layout);
  return {
    ...json,
    layout: (layout && typeof layout === "object" ? layout : { type: "row", children: [] }) as IJsonModel["layout"],
  };
}

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
    return isPersistedLayout(parsed) ? stripAnalyticsAddFromLayout(parsed) : null;
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

export function clearPersistedLayout(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(LAYOUT_STORAGE_KEY);
  } catch {
    // private mode
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
