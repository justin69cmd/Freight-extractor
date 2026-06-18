"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { ExtractedTables } from "@/components/ExtractedTables";
import type { AgreementMetadata, ExtractedTable, ReviewTask } from "@/lib/types";

export default function ReviewPage({ params }: { params: { id: string } }) {
  const jobId = params.id;
  const agreementId = useSearchParams().get("agreement") || "";

  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [meta, setMeta] = useState<AgreementMetadata | null>(null);
  const [tables, setTables] = useState<ExtractedTable[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [includeFlagged, setIncludeFlagged] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setTasks(await api.listReviewTasks(jobId, true));
    if (agreementId) {
      try {
        setMeta(await api.getMetadata(agreementId));
      } catch {
        /* metadata may not exist */
      }
      try {
        setTables(await api.getTables(agreementId));
      } catch {
        /* tables may not exist */
      }
    }
  }, [jobId, agreementId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function approveAndExport() {
    setMsg(null);
    setBusy(true);
    try {
      await api.approveJob(jobId, "reviewer@mankind");
      const { blob, filename } = await api.downloadExcel(agreementId, includeFlagged);
      const outcome = await saveBlob(blob, filename);
      setMsg(
        outcome === "cancelled"
          ? "Approved. Save cancelled — click again to choose a location."
          : outcome === "picked"
            ? `Approved and saved as ${filename}.`
            : `Approved. ${filename} downloaded to your Downloads folder.`
      );
    } catch (e) {
      setMsg(
        e instanceof ApiError && e.isReviewBlocked
          ? "Resolve all flagged items before exporting."
          : (e as Error).message
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Review & Approve</h1>

      {meta && (
        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-2 font-medium">Agreement metadata</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <dt className="text-slate-500">Vendor</dt><dd>{meta.vendor_name ?? "—"}</dd>
            <dt className="text-slate-500">Effective</dt><dd>{meta.effective_date ?? "—"}</dd>
            <dt className="text-slate-500">Expiry</dt><dd>{meta.expiry_date ?? "—"}</dd>
            <dt className="text-slate-500">Payment terms</dt><dd>{meta.payment_terms ?? "—"}</dd>
          </dl>
          {meta.clauses.length > 0 && (
            <div className="mt-3">
              <p className="text-sm font-medium">Clauses</p>
              <ul className="mt-1 space-y-1 text-sm text-slate-600">
                {meta.clauses.map((c) => (
                  <li key={c.id}><span className="font-medium">{c.clause_type}:</span> {c.text.slice(0, 140)}…</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <section className="rounded-lg border bg-white p-5">
        <h2 className="mb-3 font-medium">
          Extracted tables{" "}
          <span className="text-sm font-normal text-slate-500">
            ({tables.length}) — the source the rates were normalized from
          </span>
        </h2>
        <ExtractedTables tables={tables} />
      </section>

      <section className="rounded-lg border bg-white p-5">
        <h2 className="mb-3 font-medium">
          Flagged items{" "}
          <span className="text-sm font-normal text-slate-500">({tasks.length} open)</span>
        </h2>
        {tasks.length === 0 ? (
          <p className="text-sm text-band-high">No open items — ready to approve.</p>
        ) : (
          <ul className="divide-y">
            {tasks.map((t) => (
              <TaskRow key={t.id} task={t} onResolved={refresh} />
            ))}
          </ul>
        )}
      </section>

      <div className="flex flex-wrap items-center gap-4">
        <button
          onClick={approveAndExport}
          disabled={tasks.length > 0 || busy}
          className="rounded bg-brand px-4 py-2 text-white disabled:opacity-50"
          title={tasks.length > 0 ? "Resolve all flagged items first" : "Choose where to save"}
        >
          {busy ? "Preparing…" : "Approve & export Excel…"}
        </button>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeFlagged}
            onChange={(e) => setIncludeFlagged(e.target.checked)}
          />
          include flagged rows
        </label>
        {msg && <span className="text-sm text-slate-600">{msg}</span>}
      </div>
      <p className="text-xs text-slate-400">
        On Chrome/Edge/Brave a “Save As” dialog lets you pick the folder; other browsers
        save to your Downloads folder.
      </p>
    </div>
  );
}

function TaskRow({ task, onResolved }: { task: ReviewTask; onResolved: () => void }) {
  const [field, setField] = useState("rate_value");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.correctItem(task.id, field, value, "reviewer@mankind");
      onResolved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-2 py-3 text-sm">
      <span className="rounded bg-band-low/10 px-2 py-0.5 text-xs text-band-low">{task.item_kind}</span>
      <span className="text-slate-600">{task.reason}</span>
      <span className="ml-auto flex items-center gap-2">
        <input
          value={field}
          onChange={(e) => setField(e.target.value)}
          className="w-32 rounded border px-2 py-1"
          aria-label="field"
        />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="corrected value"
          className="w-40 rounded border px-2 py-1"
          aria-label="value"
        />
        <button
          onClick={save}
          disabled={busy}
          className="rounded bg-slate-800 px-3 py-1 text-white disabled:opacity-50"
        >
          {busy ? "…" : "Fix"}
        </button>
      </span>
    </li>
  );
}
