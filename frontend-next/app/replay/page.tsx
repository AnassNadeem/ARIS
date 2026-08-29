"use client";

import { Suspense } from "react";
import { useRouter } from "next/navigation";
import { AppHeader } from "@/components/layout/AppHeader";
import { ReplaySetupFlow } from "@/components/ReplaySetupFlow";

export default function ReplaySessionPage() {
  const router = useRouter();
  return (
    <>
      <AppHeader backHref="/" />
      <Suspense
        fallback={
          <main className="replay-surface flex-1 px-4 py-8 font-mono-data text-sm text-muted">
            Loading replay setup…
          </main>
        }
      >
        <ReplaySetupFlow onLoaded={() => router.push("/replay/console")} />
      </Suspense>
    </>
  );
}
