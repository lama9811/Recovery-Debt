export function ErrorState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
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
