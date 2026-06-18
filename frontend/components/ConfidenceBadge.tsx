import type { ConfidenceBand } from "@/lib/types";

const STYLES: Record<ConfidenceBand, string> = {
  HIGH: "bg-band-high/10 text-band-high border-band-high/30",
  MEDIUM: "bg-band-medium/10 text-band-medium border-band-medium/30",
  LOW: "bg-band-low/10 text-band-low border-band-low/30",
};

export function ConfidenceBadge({
  band,
  value,
}: {
  band: ConfidenceBand;
  value?: number;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[band]}`}
      title={value !== undefined ? `confidence ${(value * 100).toFixed(0)}%` : undefined}
    >
      {band}
      {value !== undefined && <span className="opacity-70">{(value * 100).toFixed(0)}%</span>}
    </span>
  );
}
