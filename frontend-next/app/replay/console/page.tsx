"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRaceStore } from "@/store/raceStore";
import { ARISConsole } from "@/components/layout/ARISConsole";

export default function ReplayConsolePage() {
  const router = useRouter();
  const session = useRaceStore((s) => s.session);

  useEffect(() => {
    if (!session) router.replace("/replay");
  }, [session, router]);

  if (!session) return null;
  return <ARISConsole mode="replay" />;
}
