"""Google Docs processor for .gdoc files and URLs."""

import json
import re
import tempfile
from pathlib import Path
from typing import Any, Union

import requests
from PIL import Image

from ..base import CloudFileProcessor
from ..file.pdf import PDFProcessor


class GoogleDocsProcessor(CloudFileProcessor):
    """Process Google Docs from .gdoc files or direct URLs."""

    # Regex patterns for Google Docs URLs
    DOCS_URL_PATTERN = re.compile(
        r"docs\.google\.com/(?:document|spreadsheets|presentation)/d/([a-zA-Z0-9-_]+)"
    )

    # Export format mappings
    EXPORT_FORMATS = {
        "document": "pdf",  # Google Docs
        "spreadsheets": "pdf",  # Google Sheets
        "presentation": "pdf",  # Google Slides
    }

    def __init__(self, dpi: int = 300):
        """Initialize Google Docs processor.

        Args:
            dpi: Resolution for PDF conversion (default: 300)
        """
        self.dpi = dpi
        self.pdf_processor = PDFProcessor(dpi=dpi)

    @property
    def requires_llm(self) -> bool:
        """Google Docs require LLM for text extraction."""
        return True

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given source."""
        # Check if it's a Google Docs URL
        if isinstance(source, str) and self.DOCS_URL_PATTERN.search(source):
            return True

        # Check if it's a .gdoc, .gsheet, or .gslides file
        if isinstance(source, (str, Path)):
            path = Path(source)
            return path.suffix.lower() in [".gdoc", ".gsheet", ".gslides"]

        return False

    def extract_document_id(self, source: Union[str, Path]) -> str:
        """Extract document ID from file or URL."""
        if isinstance(source, str) and self.DOCS_URL_PATTERN.search(source):
            # Extract from URL
            match = self.DOCS_URL_PATTERN.search(source)
            if match:
                return match.group(1)

        # Extract from .gdoc file
        path = Path(source)
        if path.suffix.lower() in [".gdoc", ".gsheet", ".gslides"]:
            try:
                with open(path) as f:
                    data = json.load(f)
                    # Google Drive shortcut files contain doc_id
                    doc_id = data.get("doc_id", "")
                    if doc_id:
                        return str(doc_id)
                    return ""
            except (json.JSONDecodeError, KeyError):
                # Try alternative format (sometimes it's just a text file with URL)
                with open(path) as f:
                    content = f.read()
                    match = self.DOCS_URL_PATTERN.search(content)
                    if match:
                        return match.group(1)

        raise ValueError(f"Could not extract document ID from: {source}")

    def _determine_doc_type(self, source: Union[str, Path]) -> str:
        """Determine the type of Google document."""
        source_str = str(source)

        if "spreadsheets" in source_str or source_str.endswith(".gsheet"):
            return "spreadsheets"
        elif "presentation" in source_str or source_str.endswith(".gslides"):
            return "presentation"
        else:
            return "document"

    def _build_export_url(self, doc_id: str, doc_type: str, format: str = "pdf") -> str:
        """Build the export URL for a Google document."""
        base_urls = {
            "document": f"https://docs.google.com/document/d/{doc_id}/export?format={format}",
            "spreadsheets": f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format={format}",
            "presentation": f"https://docs.google.com/presentation/d/{doc_id}/export?format={format}",
        }
        return base_urls.get(doc_type, base_urls["document"])

    def get_content(self, source: Union[str, Path], **kwargs: Any) -> list[Image.Image]:
        """Download and process Google Docs content."""
        # Extract document ID
        doc_id = self.extract_document_id(source)
        doc_type = self._determine_doc_type(source)

        # Build export URL
        export_url = self._build_export_url(doc_id, doc_type, "pdf")

        # Download PDF
        try:
            response = requests.get(export_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to download Google Doc: {str(e)}")

        # Save to temporary file and process
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = Path(tmp_file.name)

        try:
            # Use PDF processor to convert to images
            images = self.pdf_processor.process(tmp_path)
            return images
        finally:
            # Clean up temporary file
            if tmp_path.exists():
                tmp_path.unlink()
