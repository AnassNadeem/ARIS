import { SEASON_YEARS } from "@/lib/seasonYears";

export function generateStaticParams() {
  return SEASON_YEARS.map((year) => ({ year: String(year) }));
}

export default function StandingsYearLayout({ children }: { children: React.ReactNode }) {
  return children;
}
