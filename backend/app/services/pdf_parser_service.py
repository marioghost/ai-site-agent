"""PDF text extraction using pypdf."""
from __future__ import annotations

import io

from pypdf import PdfReader

from app.core.logging import get_logger
from app.services.text_cleaner_service import TextCleanerService

logger = get_logger(__name__)


class PdfParserService:
    def __init__(self) -> None:
        self.cleaner = TextCleanerService()

    def extract(self, content: bytes) -> str:
        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Could not read PDF: {exc}") from exc

        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed extracting a PDF page: %s", exc)
        return self.cleaner.clean("\n".join(parts))
