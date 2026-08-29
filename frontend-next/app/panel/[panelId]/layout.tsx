import { PANEL_CATALOGUE } from "@/lib/panelRegistry";

export function generateStaticParams() {
  return PANEL_CATALOGUE.map((entry) => ({ panelId: entry.componentId }));
}

export default function PanelLayout({ children }: { children: React.ReactNode }) {
  return children;
}
