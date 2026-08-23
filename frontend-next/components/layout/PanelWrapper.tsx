"use client";

import type { ReactNode } from "react";
import type { ITabRenderValues, TabNode } from "flexlayout-react";
import { tearOffPanel } from "@/lib/broadcastChannel";

/** Wraps a panel's rendered content with consistent sizing/overflow behaviour. */
export function PanelWrapper({ children }: { children: ReactNode }) {
  return <div className="h-full w-full overflow-hidden bg-carbon">{children}</div>;
}

/**
 * flexlayout-react `onRenderTab` handler: injects the ⤢ tear-off button into
 * every tab's header, next to the native × close button. The × itself is
 * handled natively by flexlayout (tabEnableClose).
 */
export function renderTabWithTearOff(node: TabNode, renderValues: ITabRenderValues) {
  const componentId = node.getComponent();
  renderValues.buttons.push(
    <button
      key="tearoff"
      title="Open in new window"
      onClick={(e) => {
        e.stopPropagation();
        tearOffPanel(componentId ?? node.getId(), node.getName());
      }}
      className="mr-1 rounded px-1 text-[11px] text-muted hover:bg-border hover:text-white"
    >
      ⤢
    </button>,
  );
}
