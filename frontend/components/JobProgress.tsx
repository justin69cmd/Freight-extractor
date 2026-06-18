"use client";

import type { Job, JobStatus } from "@/lib/types";

const STAGES: JobStatus[] = [
  "QUEUED", "INGESTING", "EXTRACTING", "CLASSIFYING", "VALIDATING",
  "NORMALIZING", "REVIEW_PENDING", "REVIEW_APPROVED", "EXPORTING", "SUCCEEDED",
];

export function JobProgress({ job }: { job: Job }) {
  const idx = STAGES.indexOf(job.status);
  const failed = job.status === "FAILED";
  const pct = failed ? 100 : Math.round((job.progress || 0) * 100);

  return (
    <div className="rounded-lg border bg-white p-5">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-medium">{job.status.replace(/_/g, " ")}</span>
        <span className="text-sm text-slate-500">{job.stage_detail}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full transition-all ${failed ? "bg-band-low" : "bg-brand"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-1 text-[11px] text-slate-500">
        {STAGES.map((s, i) => (
          <span
            key={s}
            className={i <= idx && !failed ? "font-semibold text-brand" : ""}
          >
            {s.replace(/_/g, " ")}
            {i < STAGES.length - 1 ? " ›" : ""}
          </span>
        ))}
      </div>
      {job.flags_count > 0 && (
        <p className="mt-3 text-sm text-band-medium">
          {job.flags_count} item(s) flagged for review.
        </p>
      )}
      {failed && <p className="mt-3 text-sm text-band-low">Failed: {job.error}</p>}
    </div>
  );
}
