"use client";

import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { ExtractedTable } from "@/lib/types";

const BAND_BORDER: Record<string, string> = {
  HIGH: "border-band-high/40",
  MEDIUM: "border-band-medium/50",
  LOW: "border-band-low/50",
};

/** Renders the raw extracted table grids — the source the rates came from.
 *  This is the "see what the machine read" half of extraction QA. */
export function ExtractedTables({ tables }: { tables: ExtractedTable[] }) {
  if (tables.length === 0) {
    return <p className="text-sm text-slate-500">No tables extracted from this document.</p>;
  }
  return (
    <div className="space-y-5">
      {tables.map((t) => {
        const [header, ...body] = t.cells.length ? t.cells : [[]];
        return (
          <div key={t.id} className={`overflow-x-auto rounded-lg border-2 ${BAND_BORDER[t.confidence_band]}`}>
            <div className="flex items-center justify-between gap-2 bg-slate-50 px-3 py-2 text-sm">
              <span className="text-slate-500">Page {t.page_number}</span>
              <span className="flex items-center gap-2">
                <span className="rounded bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand">
                  {t.pattern}
                </span>
                <ConfidenceBadge band={t.confidence_band} value={t.classification_confidence} />
              </span>
            </div>
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-100 text-left">
                  {header.map((h, i) => (
                    <th key={i} className="border px-3 py-1.5 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row, r) => (
                  <tr key={r} className="odd:bg-white even:bg-slate-50/50">
                    {row.map((cell, c) => (
                      <td key={c} className="border px-3 py-1.5 text-slate-700">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
