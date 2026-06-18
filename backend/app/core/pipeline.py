"""Pipeline orchestrator — runs L0..L6 with checkpointed job status.

Phase 3 implements L0 (ingest) and L1 (extract) end-to-end and persists
ExtractedTable rows. L1.5/L2..L6 are sequenced here as explicit, resumable
stages; each later phase fills in its stage without disturbing the others.

Design: degrade, never crash silently (§17). A page that fails extraction is
logged into job.error context and skipped; the job continues with partial,
still-valuable results.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.canonical import repository as repo
from app.classification.classifier import classify_table
from app.config import settings
from app.core.enums import JobStatus, PageKind, ReviewItemKind
from app.core.exceptions import FreightError
from app.extraction.extractor import extract_tables
from app.ingestion.page_classifier import classify_page
from app.ingestion.pdf_loader import load_document
from app.metadata.metadata_extractor import extract_metadata
from app.normalization.normalizer import TableInput, collect_zone_maps, normalize_one
from app.search.indexer import index_agreement
from app.storage import storage
from app.validation.ai_gate import validate_table
from app.validation.schema_validator import validate_rows

log = logging.getLogger("freight.pipeline")


def run_pipeline(db: Session, job_id: uuid.UUID) -> None:
    """Execute the extraction pipeline for one job. Idempotent per stage."""
    job = repo.get_job(db, job_id)
    if job is None:
        raise FreightError(f"job {job_id} not found")
    agreement = job.agreement

    try:
        # --- L0 INGEST ----------------------------------------------------- #
        repo.update_job(db, job, status=JobStatus.INGESTING, stage_detail="loading PDF", progress=0.05)
        db.commit()
        path = str(storage.open_path(agreement.storage_uri))
        doc = load_document(path)
        agreement.page_count = doc.page_count
        db.add(agreement)
        db.commit()

        # --- L1 EXTRACT ---------------------------------------------------- #
        repo.update_job(db, job, status=JobStatus.EXTRACTING, stage_detail="extracting tables", progress=0.25)
        db.commit()
        profile_keywords = _profile_keywords(agreement)
        tables = extract_tables(doc, profile_keywords=profile_keywords)

        persisted: list = []
        low_conf = 0
        for t in tables:
            row = repo.persist_extracted_table(db, agreement, t)
            persisted.append((t, row))
            if t.confidence_band.value == "LOW":
                low_conf += 1
        db.commit()
        log.info("job %s extracted %d tables (%d low-confidence)", job_id, len(tables), low_conf)

        # --- L2 CLASSIFY --------------------------------------------------- #
        repo.update_job(db, job, status=JobStatus.CLASSIFYING, stage_detail="classifying patterns", progress=0.4)
        db.commit()
        ai_budget = [settings.ai_per_job_call_budget]  # shared cap across the job
        classified: list = []  # (raw_table, row, result) — keeps column_mapping in memory
        ambiguous = 0
        for raw_table, row in persisted:
            result = classify_table(db, raw_table, vendor_id=agreement.vendor_id, ai_budget=ai_budget)
            row.pattern = result.pattern
            row.classification_confidence = result.confidence
            row.confidence_band = result.band
            db.add(row)
            classified.append((raw_table, row, result))
            if result.band.value == "LOW" or result.pattern.value == "UNKNOWN":
                ambiguous += 1
        db.commit()
        log.info("job %s classified %d tables (%d ambiguous/unknown)", job_id, len(classified), ambiguous)

        # --- L1.5 METADATA + CLAUSES (Enhancement #1) ---------------------- #
        repo.update_job(db, job, status=JobStatus.NORMALIZING, stage_detail="extracting metadata & clauses", progress=0.55)
        db.commit()
        legal_pages = [
            (p.number, p.text)
            for p in doc.pages
            if classify_page(p) in (PageKind.LEGAL, PageKind.MIXED)
        ]
        meta = extract_metadata(legal_pages)
        meta_row = repo.persist_metadata(db, agreement=agreement, meta=meta)
        repo.maybe_flag_for_review(
            db, job=job, kind=ReviewItemKind.METADATA, item_id=meta_row.id,
            confidence=meta.extraction_confidence,
        )
        db.commit()

        # --- L3 AI VALIDATION GATE (gated, budgeted; Enhancement #6) ------- #
        repo.update_job(db, job, status=JobStatus.VALIDATING, stage_detail="AI validation gate", progress=0.65)
        db.commit()
        aliases = (agreement.vendor.aliases or {}) if agreement.vendor else {}

        validated: list = []  # (table_row, TableInput, ai_touched, ai_explanation)
        for raw_table, row, result in classified:
            vres = validate_table(raw_table, result, ai_budget=ai_budget)
            ti = TableInput(
                pattern=result.pattern,
                grid=vres.grid,  # repaired grid if the gate touched it
                column_mapping=result.column_mapping,
                page_number=raw_table.page_number,
                extraction_confidence=vres.new_confidence or raw_table.extraction_confidence,
                bbox=raw_table.bbox.model_dump() if raw_table.bbox else None,
            )
            validated.append((row, ti, vres.ai_touched, vres.explanation))

        # --- L4 NORMALIZE + ROUTE EXPAND + ZONE RESOLVE -------------------- #
        repo.update_job(db, job, status=JobStatus.NORMALIZING, stage_detail="normalizing rates", progress=0.75)
        db.commit()

        # pass 1: zone index across all tables (needed before resolving rates)
        zone_rows, zone_index = collect_zone_maps([ti for _, ti, _, _ in validated], aliases)
        for z in zone_rows:
            repo.persist_zone_mapping(db, agreement=agreement, zmap=z)

        # passes 2+3: normalize each table (keeps table_id), persist, validate, flag
        rate_count = flagged_rates = 0
        for table_row, ti, ai_touched, ai_explanation in validated:
            crows = normalize_one(ti, aliases, zone_index)
            violations = {v.index for v in validate_rows(crows)}  # gate G3 (deterministic)
            for idx, crow in enumerate(crows):
                crow.ai_touched = ai_touched
                crow.ai_explanation = ai_explanation
                rate = repo.persist_canonical_rate(
                    db, agreement=agreement, table_id=table_row.id, row=crow
                )
                rate_count += 1
                flagged = repo.maybe_flag_for_review(
                    db, job=job, kind=ReviewItemKind.RATE, item_id=rate.id,
                    confidence=crow.extraction_confidence, ai_touched=ai_touched,
                )
                if idx in violations:
                    repo.create_review_task(
                        db, job=job, kind=ReviewItemKind.RATE, item_id=rate.id,
                        reason="schema validation (G3): invalid/missing field",
                    )
                    flagged = True
                if flagged:
                    flagged_rates += 1
        job.flags_count = low_conf + ambiguous + flagged_rates
        db.commit()
        log.info("job %s normalized %d rates (%d flagged) + %d zone maps",
                 job_id, rate_count, flagged_rates, len(zone_rows))

        # --- L5 EMBED (RAG index, Enhancement #3) -------------------------- #
        # Index rates + clauses + metadata into pgvector so search works even
        # while review is pending (internal querying). Degrade gracefully: an
        # embedding-provider hiccup must not fail the whole job.
        repo.update_job(db, job, stage_detail="indexing for search", progress=0.82)
        db.commit()
        try:
            db.refresh(agreement)
            chunks = index_agreement(db, agreement)
            db.commit()
            log.info("job %s indexed %d search chunks", job_id, chunks)
        except Exception as exc:  # noqa: BLE001 — search index is non-critical
            db.rollback()
            log.warning("job %s embedding index failed (non-fatal): %s", job_id, exc)

        # --- L5.5 HUMAN REVIEW GATE (Enhancement #2) ----------------------- #
        # Excel export (Phase 6) sits behind this gate; nothing exports until a
        # reviewer approves.
        repo.update_job(
            db, job,
            status=JobStatus.REVIEW_PENDING,
            stage_detail=f"awaiting review — {job.flags_count} flagged item(s)",
            progress=0.85,
        )
        db.commit()

    except FreightError as exc:
        log.exception("pipeline failed for job %s", job_id)
        repo.update_job(db, job, status=JobStatus.FAILED, error=str(exc))
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("unexpected pipeline error for job %s", job_id)
        repo.update_job(db, job, status=JobStatus.FAILED, error=f"unexpected: {exc}")
        db.commit()
        raise


def _profile_keywords(agreement) -> list[str]:
    """Pull page_keywords from the vendor YAML profile if present (no-code hints)."""
    # Phase 3 stub: profile loading wired in Phase 4 alongside classification.
    return []
