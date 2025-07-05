"""PDF document processor using PyMuPDF."""

import io
from pathlib import Path
from typing import Union

import fitz  # PyMuPDF
from PIL import Image

from ..base import ImageBasedProcessor


class PDFProcessor(ImageBasedProcessor):
    """Process PDF documents by converting pages to images."""

    def __init__(self, dpi: int = 300):
        """Initialize PDF processor.

        Args:
            dpi: Resolution for image conversion (default: 300)
        """
        self.dpi = dpi
        self.zoom = dpi / 72.0  # PDF points are 72 dpi

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return [".pdf"]

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file."""
        if isinstance(source, str):
            source = Path(source)
        return source.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[Image.Image]:
        """Process PDF and return list of page images.

        Args:
            file_path: Path to the PDF file

        Returns:
            List of PIL Image objects, one per page

        Raises:
            ValueError: If the file cannot be processed
        """
        self.validate_file(file_path)

        images = []
        try:
            # Open PDF document
            doc = fitz.open(str(file_path))

            # Convert each page to image
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # Create transformation matrix for desired DPI
                mat = fitz.Matrix(self.zoom, self.zoom)

                # Render page to pixmap
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)

            doc.close()

        except Exception as e:
            raise ValueError(f"Failed to process PDF: {str(e)}")

        return images
