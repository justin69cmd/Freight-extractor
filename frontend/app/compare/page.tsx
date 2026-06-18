"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";

export default function ComparePage() {
  const [origin, setOrigin] = useState("");
  const [dest, setDest] = useState("");
  const [res, setRes] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    const lane = `${origin ? `from ${origin} ` : ""}to ${dest}`.trim();
    try {
      // Force the comparison intent regardless of phrasing.
      setRes(await api.search(`compare rates between vendors ${lane}`, "VENDOR_COMPARISON"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Compare Vendors</h1>
      <form onSubmit={run} className="flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="text-sm text-slate-500">Origin (optional)</span>
          <input value={origin} onChange={(e) => setOrigin(e.target.value)}
                 className="mt-1 block rounded border px-3 py-2" placeholder="Meerut" />
        </label>
        <label className="block">
          <span className="text-sm text-slate-500">Destination</span>
          <input value={dest} onChange={(e) => setDest(e.target.value)}
                 className="mt-1 block rounded border px-3 py-2" placeholder="Kolkata" required />
        </label>
        <button className="rounded bg-brand px-5 py-2 text-white disabled:opacity-50" disabled={busy}>
          {busy ? "…" : "Compare"}
        </button>
      </form>

      {res && (
        <section className="space-y-3">
          {res.answer && (
            <div className="rounded-lg border-l-4 border-band-high bg-white p-4">{res.answer}</div>
          )}
          <table className="w-full overflow-hidden rounded-lg border bg-white text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">Vendor</th>
                <th className="px-4 py-2">Summary</th>
                <th className="px-4 py-2 text-right">Rank</th>
              </tr>
            </thead>
            <tbody>
              {res.hits.map((h, i) => (
                <tr key={`${h.ref_id}-${i}`} className="border-t">
                  <td className="px-4 py-2 font-medium">{h.vendor ?? "—"}</td>
                  <td className="px-4 py-2 text-slate-600">{h.snippet}</td>
                  <td className="px-4 py-2 text-right">{i === 0 ? "🏆 cheapest" : `#${i + 1}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
