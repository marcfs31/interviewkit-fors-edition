"use client";

import type { ReactNode } from "react";
import Navbar from "@/components/Navbar";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar />
      <main id="main" tabIndex={-1} className="flex-1 outline-none">{children}</main>
    </div>
  );
}
