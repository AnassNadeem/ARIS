"use client";

import { useRouter } from "next/navigation";
import { SessionSelector } from "@/components/ui/SessionSelector";

export default function ReplaySessionPage() {
  const router = useRouter();
  return <SessionSelector onLoaded={() => router.push("/replay/console")} />;
}
