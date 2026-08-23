"use client";

import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/layout/AppHeader";
import { SessionSelector } from "@/components/ui/SessionSelector";

export default function ReplaySessionPage() {
  const router = useRouter();
  return (
    <>
      <AppHeader backHref="/" />
      <SessionSelector onLoaded={() => router.push("/replay/console")} />
    </>
  );
}
