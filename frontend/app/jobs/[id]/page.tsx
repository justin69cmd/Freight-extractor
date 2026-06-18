"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { JobProgress } from "@/components/JobProgress";
import type { Job } from "@/lib/types";

const DONE: Job["status"][] = ["SUCCEEDED", "SUCCEEDED_WITH_FLAGS", "FAILED"];

export default function JobPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<Job | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    // Poll until the pipeline reaches a terminal or review state.
    async function tick() {
      try {
        const j = await api.getJob(params.id);
        if (!active) return;
        setJob(j);
        if (!DONE.includes(j.status) && j.status !== "REVIEW_PENDING") {
          setTimeout(tick, 1500);
        }
      } catch (e) {
        if (active) setErr((e as Error).message);
      }
    }
    tick();
    return () => {
      active = false;
    };
  }, [params.id]);

  if (err) return <p className="text-band-low">Error: {err}</p>;
  if (!job) return <p className="text-slate-500">Loading job…</p>;

  const reviewable = job.status === "REVIEW_PENDING";
  return (
    <div className="max-w-2xl space-y-5">
      <h1 className="text-xl font-semibold">Processing</h1>
      <JobProgress job={job} />
      <div className="flex gap-3">
        {reviewable && (
          <Link
            href={`/review/${job.id}?agreement=${job.agreement_id}`}
            className="rounded bg-brand px-4 py-2 text-white"
          >
            Review {job.flags_count} flagged item(s) →
          </Link>
        )}
        <Link
          href={`/search`}
          className="rounded border px-4 py-2 text-brand hover:bg-slate-100"
        >
          Search this data
        </Link>
      </div>
    </div>
  );
}
