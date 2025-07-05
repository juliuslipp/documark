"""Base processor classes for document conversion."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union

from PIL import Image


class BaseProcessor(ABC):
    """Abstract base class for all document processors."""

    @abstractmethod
    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given source.

        Args:
            source: Path to file or URL to process

        Returns:
            True if this processor can handle the source
        """
        pass

    @abstractmethod
    def get_content(
        self, source: Union[str, Path], **kwargs: Any
    ) -> Union[list[Image.Image], str]:
        """Get content from the source.

        Args:
            source: Path to file or URL to process
            **kwargs: Additional processor-specific options

        Returns:
            Either list of images or extracted text
        """
        pass

    @property
    @abstractmethod
    def processor_type(self) -> str:
        """Return the type of processor (file, cloud, web)."""
        pass

    @property
    @abstractmethod
    def requires_llm(self) -> bool:
        """Whether this processor requires LLM for text extraction."""
        pass


class FileProcessor(BaseProcessor):
    """Base class for local file processors."""

    @property
    def processor_type(self) -> str:
        return "file"

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (with dots)."""
        pass

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file."""
        if isinstance(source, str) and (
            source.startswith("http://") or source.startswith("https://")
        ):
            return False

        path = Path(source)
        return path.suffix.lower() in self.supported_extensions

    def validate_file(self, file_path: Path) -> None:
        """Validate that the file exists and can be processed.

        Args:
            file_path: Path to validate

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file type is not supported
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.can_process(file_path):
            raise ValueError(
                f"Unsupported file type: {file_path.suffix}. "
                f"Supported types: {', '.join(self.supported_extensions)}"
            )


class CloudFileProcessor(BaseProcessor):
    """Base class for cloud file processors (Google Drive, etc)."""

    @property
    def processor_type(self) -> str:
        return "cloud"

    @abstractmethod
    def extract_document_id(self, source: Union[str, Path]) -> str:
        """Extract document ID from file or URL."""
        pass


class WebProcessor(BaseProcessor):
    """Base class for web-based processors."""

    @property
    def processor_type(self) -> str:
        return "web"

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given URL."""
        if isinstance(source, Path):
            return False
        return isinstance(source, str) and (
            source.startswith("http://") or source.startswith("https://")
        )


class ImageBasedProcessor(FileProcessor):
    """Base class for processors that convert documents to images."""

    @property
    def requires_llm(self) -> bool:
        return True

    @abstractmethod
    def process(self, file_path: Path) -> list[Image.Image]:
        """Process the document and return a list of images.

        Args:
            file_path: Path to the document to process

        Returns:
            List of PIL Image objects, one per page

        Raises:
            ValueError: If the file cannot be processed
        """
        pass

    def get_content(self, source: Union[str, Path], **kwargs: Any) -> list[Image.Image]:
        """Get content as images."""
        file_path = Path(source)
        self.validate_file(file_path)
        return self.process(file_path)


class TextBasedProcessor(FileProcessor):
    """Base class for processors that extract text directly."""

    @property
    def requires_llm(self) -> bool:
        return False

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """Extract text content from the file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text content
        """
        pass

    def get_content(self, source: Union[str, Path], **kwargs: Any) -> str:
        """Get content as text."""
        file_path = Path(source)
        self.validate_file(file_path)
        return self.extract_text(file_path)
