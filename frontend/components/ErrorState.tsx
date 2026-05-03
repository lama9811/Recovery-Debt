export function ErrorState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  // 503 from any /api/* endpoint means the model isn't trained yet — that's
  // an expected state for newly-connected users (no training data, or no
  // nightly retrain has fired). Render a friendlier "model still training"
  // copy instead of a stack-trace flavored error.
  const isModelMissing =
    typeof hint === "string" && / → 503\b/.test(hint);

  if (isModelMissing) {
    return (
      <div className="rd-card flex flex-col items-start gap-3">
        <span className="rd-eyebrow">Still training</span>
        <h3 className="rd-h2 text-[20px]">Your model isn&apos;t ready yet.</h3>
        <p className="text-sm text-[color:var(--rd-fg-muted)]">
          The Ridge regression needs a nightly retrain on your data before this
          page can render. Check back tomorrow morning, or trigger
          <code className="mono mx-1">cron-train-now</code>
          on Railway to run it immediately.
        </p>
      </div>
    );
  }

  return (
    <div className="rd-card flex flex-col items-start gap-3">
      <span className="rd-eyebrow">Heads up</span>
      <h3 className="rd-h2 text-[20px]">{title}</h3>
      {hint ? (
        <p className="text-sm text-[color:var(--rd-fg-muted)]">{hint}</p>
      ) : null}
    </div>
  );
}
