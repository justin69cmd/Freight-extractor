"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [vendor, setVendor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.uploadAgreement(file, vendor || "Unknown Vendor");
      router.push(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "upload failed");
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="mb-4 text-xl font-semibold">Upload Agreement</h1>
      <form onSubmit={submit} className="space-y-4 rounded-lg border bg-white p-6">
        <label className="block">
          <span className="text-sm font-medium">Vendor name</span>
          <input
            value={vendor}
            onChange={(e) => setVendor(e.target.value)}
            placeholder="e.g. Safexpress"
            className="mt-1 w-full rounded border px-3 py-2"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Agreement PDF</span>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 w-full rounded border px-3 py-2"
            required
          />
        </label>
        {error && <p className="text-sm text-band-low">{error}</p>}
        <button
          type="submit"
          disabled={busy || !file}
          className="rounded bg-brand px-4 py-2 text-white disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Upload & process"}
        </button>
      </form>
      <p className="mt-3 text-sm text-slate-500">
        Processing runs asynchronously; you’ll be taken to a live progress view.
      </p>
    </div>
  );
}
