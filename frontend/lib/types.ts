// TypeScript mirror of the backend Pydantic schemas (app/canonical/schemas.py).
// Kept in sync by hand; the canonical source of truth is the FastAPI OpenAPI doc.

export type ConfidenceBand = "HIGH" | "MEDIUM" | "LOW";
export type TransportMode = "ROAD" | "AIR" | "COURIER" | "COLD_CHAIN";
export type ValidationStatus = "AUTO" | "AI_VALIDATED" | "HUMAN_VERIFIED" | "FLAGGED";
export type SearchIntent =
  | "FREIGHT_SEARCH"
  | "CLAUSE_SEARCH"
  | "VENDOR_COMPARISON"
  | "AGREEMENT_ANALYTICS";

export type JobStatus =
  | "QUEUED" | "INGESTING" | "EXTRACTING" | "CLASSIFYING" | "VALIDATING"
  | "NORMALIZING" | "REVIEW_PENDING" | "REVIEW_APPROVED" | "EXPORTING"
  | "SUCCEEDED" | "SUCCEEDED_WITH_FLAGS" | "FAILED";

export interface UploadResponse {
  job_id: string;
  agreement_id: string;
  status: JobStatus;
}

export interface Job {
  id: string;
  agreement_id: string;
  status: JobStatus;
  stage_detail: string | null;
  progress: number;
  flags_count: number;
  error: string | null;
}

export interface Clause {
  id: string;
  clause_type: "FUEL" | "INSURANCE" | "PENALTY" | "PAYMENT_TERMS" | "OTHER";
  text: string;
  summary: string | null;
}

export interface AgreementMetadata {
  vendor_name: string | null;
  effective_date: string | null;
  expiry_date: string | null;
  payment_terms: string | null;
  clauses: Clause[];
}

export interface Rate {
  id: string;
  transport_mode: TransportMode;
  source_pattern: string;
  origin: string | null;
  destination: string | null;
  destination_zone: string | null;
  rate_basis: string;
  rate_value: number | null;
  currency: string;
  vehicle_type: string | null;
  service_level: string | null;
  temperature_band: string | null;
  confidence_band: ConfidenceBand;
  extraction_confidence: number;
}

export interface RateProvenance extends Rate {
  agreement_id: string;
  table_id: string | null;
  source_page: number | null;
  source_bbox: Record<string, number> | null;
  source_cell: Record<string, number> | null;
  ai_explanation: string | null;
}

export interface ExtractedTable {
  id: string;
  page_number: number;
  pattern: string;
  classification_confidence: number;
  confidence_band: ConfidenceBand;
  cells: string[][];
}

export interface ReviewTask {
  id: string;
  item_kind: "RATE" | "CLAUSE" | "METADATA";
  item_id: string;
  reason: string;
  resolved: boolean;
}

export interface SearchHit {
  kind: string;
  score: number;
  vendor: string | null;
  snippet: string;
  ref_id: string;
}

export interface SearchResponse {
  intent: SearchIntent;
  answer: string | null;
  hits: SearchHit[];
}

export interface ExportResponse {
  download_uri: string;
  generated_at: string;
}
