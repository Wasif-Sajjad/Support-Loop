"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  description: string;
}

const items: NavItem[] = [
  { href: "/submit", label: "Submit & Test", description: "Trigger agent triage pipeline" },
  { href: "/queue", label: "Escalation Queue", description: "Tickets awaiting human review" },
  { href: "/dashboard", label: "Metrics & Telemetry", description: "Resolution rates and costs" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <aside className="w-60 shrink-0 border-r border-border bg-surface min-h-screen px-4 py-6 flex flex-col justify-between select-none">
      <div>
        {/* Brand header */}
        <div className="px-2 mb-8">
          <div className="flex items-center justify-between">
            <span className="font-sans font-semibold text-base tracking-tight text-text-primary">
              Support Loop
            </span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-surface-raised border border-border text-text-secondary">
              v1.0
            </span>
          </div>
          <div className="text-xs text-text-secondary mt-1 tracking-normal">
            Triage Operations Console
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex flex-col gap-1.5">
          {items.map((item) => {
            const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group px-3 py-2.5 rounded border transition-colors ${
                  active
                    ? "bg-surface-raised border-border text-text-primary"
                    : "border-transparent text-text-secondary hover:text-text-primary hover:bg-surface-raised/60 hover:border-border/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{item.label}</span>
                  {active && (
                    <span className="w-1.5 h-1.5 rounded-full bg-resolve shrink-0" />
                  )}
                </div>
                <div className="text-[11px] text-text-secondary/80 mt-0.5 font-normal leading-tight">
                  {item.description}
                </div>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer status block */}
      <div className="px-2 pt-4 border-t border-border">
        <div className="flex items-center justify-between text-xs text-text-secondary">
          <span className="font-mono text-[11px]">Engine Status</span>
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-resolve">
            <span className="w-1.5 h-1.5 rounded-full bg-resolve animate-pulse" />
            Live
          </span>
        </div>
        <div className="font-mono text-[10px] text-text-secondary/60 mt-1">
          FastAPI + LangGraph + PgVector
        </div>
      </div>
    </aside>
  );
}
