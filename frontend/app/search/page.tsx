"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

const EXAMPLES = [
  "What is the freight rate from Meerut to Bangalore?",
  "Which transporter is cheapest to Kolkata?",
  "Show the penalty clause for late delivery",
  "Compare rates between vendors to Mumbai",
];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(query: string) {
    setBusy(true);
    setErr(null);
    try {
      setRes(await api.search(query));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Agreement Intelligence</h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) run(q);
        }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask about rates, clauses, vendors…"
          className="flex-1 rounded border px-4 py-2"
        />
        <button className="rounded bg-brand px-5 py-2 text-white disabled:opacity-50" disabled={busy}>
          {busy ? "…" : "Search"}
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => {
              setQ(ex);
              run(ex);
            }}
            className="rounded-full border px-3 py-1 text-xs text-slate-600 hover:border-brand"
          >
            {ex}
          </button>
        ))}
      </div>

      {err && <p className="text-band-low">{err}</p>}

      {res && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <span className="rounded bg-slate-200 px-2 py-0.5">{res.intent}</span>
            <span>{res.hits.length} result(s)</span>
          </div>
          {res.answer && (
            <div className="rounded-lg border-l-4 border-brand bg-white p-4 text-slate-800">
              {res.answer}
            </div>
          )}
          <ul className="space-y-2">
            {res.hits.map((h, i) => (
              <li key={`${h.ref_id}-${i}`} className="rounded-lg border bg-white p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{h.vendor ?? h.kind}</span>
                  <span className="text-xs text-slate-400">score {h.score.toFixed(2)}</span>
                </div>
                <p className="mt-1 text-slate-600">{h.snippet}</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
