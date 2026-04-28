const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const params = await searchParams;
  const justConnected = params.connected === "1";

  return (
    <div className="relative flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-10 pt-10">
        <Brand />
        <span className="rd-eyebrow">v.2026.04.27</span>
      </header>

      <main className="flex flex-1 items-center px-10 pb-24">
        <div className="flex w-full max-w-2xl flex-col gap-10">
          <span className="rd-eyebrow">Recovery Debt</span>

          <h1 className="rd-display text-[clamp(3rem,8vw,5.5rem)]">
            A bank statement
            <br />
            for your body.
          </h1>

          <p className="max-w-lg text-[1.0625rem] leading-7 text-[color:var(--rd-fg-body)]">
            Connect your WHOOP and a per-user model learns your specific
            patterns. Every recovery score comes back as an itemized receipt —
            sleep, alcohol, strain, stress — so you can see, in numbers,{" "}
            <em className="italic text-[color:var(--rd-accent)]">why</em>.
          </p>

          {justConnected ? (
            <div className="flex flex-col gap-3">
              <span className="rd-chip rd-chip-deposit mono w-fit">
                <span className="rd-chip-dot" /> Connected
              </span>
              <p className="text-sm text-[color:var(--rd-fg-muted)]">
                Backfill of the last six months runs on Day 3.
              </p>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <a
                href={`${API_URL}/api/whoop/connect`}
                className="rd-btn rd-btn-primary"
              >
                Connect WHOOP
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </a>
              <span className="rd-eyebrow">Read · cycles · sleep · workouts</span>
            </div>
          )}

          <div className="rd-divider" />

          <p className="max-w-lg text-xs leading-relaxed text-[color:var(--rd-fg-muted)]">
            <span className="rd-eyebrow mr-2">Honesty</span>
            Before sixty days of data, every insight ships labeled{" "}
            <em className="italic">early estimate</em> with a confidence
            interval. The model never makes a causal or medical claim.
          </p>
        </div>
      </main>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
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
      <div className="leading-tight">
        <div className="font-[family-name:var(--font-display)] text-[16px] font-medium tracking-[-0.02em] text-[color:var(--rd-fg)]">
          Recovery Debt
        </div>
      </div>
    </div>
  );
}
