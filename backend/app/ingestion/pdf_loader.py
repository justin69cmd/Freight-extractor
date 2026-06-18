"""L0 — PDF ingestion and page segmentation.

Loads a PDF and, per page, decides whether it is born-digital (has a real text
layer) or scanned (image only). This routing is critical: running OCR on a
digital page *destroys* accuracy, so the extractor picks its path from here.

Heavy deps (pdfplumber, pypdfium2) are imported lazily so the API process can
boot without them; only worker processes need them installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import IngestionError


@dataclass
class PageInfo:
    number: int                 # 1-based
    is_digital: bool            # has an extractable text layer
    text: str = ""              # text layer (empty for scanned)
    char_count: int = 0
    width: float = 0.0
    height: float = 0.0


@dataclass
class LoadedDocument:
    path: str
    page_count: int
    pages: list[PageInfo] = field(default_factory=list)

    @property
    def has_scanned_pages(self) -> bool:
        return any(not p.is_digital for p in self.pages)


# A page with fewer extractable chars than this is treated as scanned.
_DIGITAL_CHAR_THRESHOLD = 40


def load_document(path: str) -> LoadedDocument:
    """Open a PDF and classify each page as digital vs scanned."""
    try:
        import pdfplumber  # lazy
    except ImportError as exc:  # pragma: no cover
        raise IngestionError("pdfplumber not installed (worker dependency)") from exc

    try:
        pages: list[PageInfo] = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                char_count = len((page.chars or []))
                pages.append(
                    PageInfo(
                        number=i,
                        is_digital=char_count >= _DIGITAL_CHAR_THRESHOLD,
                        text=text,
                        char_count=char_count,
                        width=float(page.width or 0),
                        height=float(page.height or 0),
                    )
                )
        if not pages:
            raise IngestionError("PDF has no pages")
        return LoadedDocument(path=path, page_count=len(pages), pages=pages)
    except IngestionError:
        raise
    except Exception as exc:  # noqa: BLE001 — wrap any pdf library failure
        raise IngestionError(f"failed to load PDF: {exc}") from exc
