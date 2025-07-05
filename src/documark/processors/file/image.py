"""Direct image file processor."""

from pathlib import Path
from typing import Union

from PIL import Image

from ..base import ImageBasedProcessor


class ImageProcessor(ImageBasedProcessor):
    """Process image files directly."""

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"]

    def can_process(self, source: Union[str, Path]) -> bool:
        """Check if this processor can handle the given file."""
        if isinstance(source, str):
            source = Path(source)
        return source.suffix.lower() in self.supported_extensions

    def process(self, file_path: Path) -> list[Image.Image]:
        """Process image file and return as list.

        Args:
            file_path: Path to the image file

        Returns:
            List containing single PIL Image object

        Raises:
            ValueError: If the file cannot be processed
        """
        self.validate_file(file_path)

        try:
            # Open and return image
            img = Image.open(file_path)
            # Convert to RGB if necessary (for consistency)
            if img.mode != "RGB":
                img = img.convert("RGB")
            return [img]

        except Exception as e:
            raise ValueError(f"Failed to process image: {str(e)}")
