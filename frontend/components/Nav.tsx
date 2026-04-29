import Link from "next/link";

const TABS = [
  { href: "/", label: "Ledger" },
  { href: "/whatif", label: "What-If" },
  { href: "/plan", label: "Plan" },
  { href: "/profile", label: "Profile" },
  { href: "/wallet", label: "Wallet" },
  { href: "/checkin", label: "Check-in" },
];

export function Nav() {
  return (
    <header className="flex items-center justify-between px-10 pt-10 pb-6">
      <Link href="/" className="flex items-center gap-3">
        <div className="relative grid size-8 place-items-center rounded-md bg-[color:var(--rd-ink)] text-[color:var(--rd-fg-on-ink)]">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="size-[18px]"
            aria-hidden="true"
          >
            <rect x="4" y="14" width="16" height="6" rx="1.5" />
            <rect x="6" y="9" width="12" height="5" rx="1.5" />
            <rect x="8" y="4" width="8" height="5" rx="1.5" />
          </svg>
          <span className="absolute -right-[2px] -top-[2px] size-[6px] rounded-full bg-[color:var(--rd-accent)]" />
        </div>
        <span className="font-[family-name:var(--font-display)] text-[16px] font-medium tracking-[-0.02em] text-[color:var(--rd-fg)]">
          Recovery Debt
        </span>
      </Link>
      <nav className="flex items-center gap-1">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="px-3 py-1.5 text-[12px] font-medium tracking-tight text-[color:var(--rd-fg-muted)] hover:text-[color:var(--rd-fg)] transition-colors"
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
