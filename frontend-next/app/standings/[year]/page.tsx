"use client";

import { useParams } from "next/navigation";
import { StandingsView } from "@/components/season/StandingsView";

export default function StandingsYearPage() {
  const params = useParams<{ year: string }>();
  return <StandingsView yearParam={params.year} />;
}
