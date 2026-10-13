"use client";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface StatsUnavailableProps {
  status: "loading" | "error";
  onRetry: () => void;
}

// Stats are unknown while loading or after a failed fetch. Showing nothing
// made up in that case is the point: never "Nv 1 · 0 XP" as if it were real.
export default function StatsUnavailable({ status, onRetry }: StatsUnavailableProps) {
  if (status === "loading") {
    return (
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Cargando estadísticas…</span>
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 border border-destructive/40 bg-destructive/10 p-6"
    >
      <p className="text-base text-foreground">No se pudieron cargar tus estadísticas.</p>
      <Button variant="outline" onClick={onRetry}>
        Reintentar
      </Button>
    </div>
  );
}
