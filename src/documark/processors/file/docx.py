"""Word document processor."""

import os
import tempfile
from pathlib import Path
from typing import Union

from PIL import Image

from ..base import ImageBasedProcessor
from .pdf import PDFProcessor


class DocxProcessor(ImageBasedProcessor):
    """Process Word documents by converting to PDF first."""

    def __init__(self, dpi: int = 300):
        """Initialize Word processor.

        Args:
            dpi: Resolution for image conversion (default: 300)
        """
        self.dpi = dpi
        self.pdf_processor = PDFProcessor(dpi=dpi)

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return [".docx", ".doc"]

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file."""
        if isinstance(source, str):
            source = Path(source)
        return source.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[Image.Image]:
        """Process Word document and return list of page images.

        Args:
            file_path: Path to the Word file

        Returns:
            List of PIL Image objects, one per page

        Raises:
            ValueError: If the file cannot be processed
        """
        self.validate_file(file_path)

        # Create temporary PDF file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf_path = Path(tmp_pdf.name)

        try:
            # Check if we're on macOS
            if os.name == "posix" and os.uname().sysname == "Darwin":
                # Use macOS-specific conversion
                self._convert_with_macos(file_path, tmp_pdf_path)
            else:
                # Use docx2pdf for Windows/Linux
                self._convert_with_docx2pdf(file_path, tmp_pdf_path)

            # Process the PDF
            images = self.pdf_processor.process(tmp_pdf_path)

        finally:
            # Clean up temporary file
            if tmp_pdf_path.exists():
                tmp_pdf_path.unlink()

        return images

    def _convert_with_docx2pdf(self, input_path: Path, output_path: Path) -> None:
        """Convert using docx2pdf library."""
        try:
            from docx2pdf import convert

            convert(str(input_path), str(output_path))
        except Exception as e:
            raise ValueError(f"Failed to convert Word document with docx2pdf: {str(e)}")

    def _convert_with_macos(self, input_path: Path, output_path: Path) -> None:
        """Convert using macOS built-in tools."""
        import subprocess

        # Use textutil to convert to HTML, then wkhtmltopdf or similar
        # For now, we'll try to use docx2pdf which should work on macOS too
        try:
            self._convert_with_docx2pdf(input_path, output_path)
        except Exception:
            # Fallback: try using LibreOffice if installed
            try:
                subprocess.run(
                    [
                        "soffice",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(output_path.parent),
                        str(input_path),
                    ],
                    check=True,
                    capture_output=True,
                )

                # Move the file to the correct location
                converted_name = input_path.stem + ".pdf"
                converted_path = output_path.parent / converted_name
                if converted_path != output_path:
                    converted_path.rename(output_path)

            except Exception as e:
                raise ValueError(
                    f"Failed to convert Word document. "
                    f"Please install LibreOffice or ensure docx2pdf is working: {str(e)}"
                )
