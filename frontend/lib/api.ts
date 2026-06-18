// Typed client for the FastAPI backend. All calls go through Next.js rewrites
// (/api/* -> backend), so no base URL is needed in the browser.
import type {
  AgreementMetadata,
  ExportResponse,
  ExtractedTable,
  Job,
  Rate,
  RateProvenance,
  ReviewTask,
  SearchIntent,
  SearchResponse,
  UploadResponse,
} from "./types";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.error || detail;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
  get isReviewBlocked() {
    return this.status === 409;
  }
}

export const api = {
  uploadAgreement(file: File, vendorName: string): Promise<UploadResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("vendor_name", vendorName);
    // FormData must not set Content-Type manually (boundary is auto-added).
    return fetch("/api/agreements/upload", { method: "POST", body: form }).then((r) => {
      if (!r.ok) throw new ApiError(r.status, "upload failed");
      return r.json();
    });
  },

  getJob(jobId: string): Promise<Job> {
    return http(`/api/jobs/${jobId}`);
  },

  getMetadata(agreementId: string): Promise<AgreementMetadata> {
    return http(`/api/agreements/${agreementId}/metadata`);
  },

  getTables(agreementId: string): Promise<ExtractedTable[]> {
    return http(`/api/agreements/${agreementId}/tables`);
  },

  listRates(params: {
    origin?: string;
    destination?: string;
    mode?: string;
    vendorId?: string;
  }): Promise<Rate[]> {
    const q = new URLSearchParams();
    if (params.origin) q.set("origin", params.origin);
    if (params.destination) q.set("destination", params.destination);
    if (params.mode) q.set("mode", params.mode);
    if (params.vendorId) q.set("vendor_id", params.vendorId);
    return http(`/api/rates?${q.toString()}`);
  },

  getRateProvenance(rateId: string): Promise<RateProvenance> {
    return http(`/api/rates/${rateId}/provenance`);
  },

  listReviewTasks(jobId: string, onlyOpen = true): Promise<ReviewTask[]> {
    return http(`/api/review/jobs/${jobId}/tasks?only_open=${onlyOpen}`);
  },

  correctItem(taskId: string, field: string, newValue: string, correctedBy: string) {
    return http<ReviewTask>(`/api/review/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify({ field, new_value: newValue, corrected_by: correctedBy }),
    });
  },

  approveJob(jobId: string, approvedBy: string) {
    return http<{ job_id: string; status: string }>(`/api/review/jobs/${jobId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
    });
  },

  search(query: string, intent?: SearchIntent, topK = 10): Promise<SearchResponse> {
    return http(`/api/search`, {
      method: "POST",
      body: JSON.stringify({ query, intent, top_k: topK }),
    });
  },

  exportExcel(agreementId: string, includeFlagged = false): Promise<ExportResponse> {
    return http(`/api/agreements/${agreementId}/export`, {
      method: "POST",
      body: JSON.stringify({ template: "mankind_default_v2", include_flagged: includeFlagged }),
    });
  },

  // Fetch the Excel as a blob so the UI can let the user choose where to save it.
  async downloadExcel(
    agreementId: string,
    includeFlagged = false
  ): Promise<{ blob: Blob; filename: string }> {
    const res = await fetch(
      `/api/agreements/${agreementId}/export/download?include_flagged=${includeFlagged}`,
      { cache: "no-store" }
    );
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        /* binary or empty */
      }
      throw new ApiError(res.status, detail);
    }
    const cd = res.headers.get("Content-Disposition") || "";
    const match = cd.match(/filename="?([^"]+)"?/);
    return { blob: await res.blob(), filename: match ? match[1] : "Mankind_Freight.xlsx" };
  },
};
