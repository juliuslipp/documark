"""File-based document processors."""

from .docx import DocxProcessor
from .image import ImageProcessor
from .pdf import PDFProcessor

__all__ = [
    "PDFProcessor",
    "DocxProcessor",
    "ImageProcessor",
]
