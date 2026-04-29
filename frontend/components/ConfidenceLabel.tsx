/**
 * PRD §13 + CLAUDE.md honesty rules: every insight before day 60 is labeled
 * "early estimate" with a confidence interval.
 */
export function ConfidenceLabel({
  nDays,
  className,
}: {
  nDays: number;
  className?: string;
}) {
  if (nDays >= 60) return null;
  return (
    <span
      className={`rd-chip rd-chip-accent mono ${className ?? ""}`}
      title={`Model is still learning — ${nDays} days of training data`}
    >
      <span className="rd-chip-dot" />
      Early estimate · {nDays}d
    </span>
  );
}
