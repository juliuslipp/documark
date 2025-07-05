"""Image utility functions."""

import base64
import io

from PIL import Image


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 encoded string.

    Args:
        image: PIL Image object
        format: Image format (default: PNG)

    Returns:
        Base64 encoded string
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)

    # Get base64 string
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Return with data URL prefix for easy use
    mime_type = f"image/{format.lower()}"
    return f"data:{mime_type};base64,{img_base64}"


def resize_image_if_needed(image: Image.Image, max_size: int = 2048) -> Image.Image:
    """Resize image if it exceeds maximum dimensions.

    Args:
        image: PIL Image object
        max_size: Maximum width or height in pixels

    Returns:
        Resized image or original if within limits
    """
    width, height = image.size

    if width <= max_size and height <= max_size:
        return image

    # Calculate new dimensions maintaining aspect ratio
    if width > height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))

    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def optimize_image_for_llm(
    image: Image.Image, max_size: int = 2048, quality: int = 85
) -> str:
    """Optimize image for LLM processing.

    Args:
        image: PIL Image object
        max_size: Maximum dimension in pixels
        quality: JPEG quality (1-100)

    Returns:
        Base64 encoded optimized image
    """
    # Resize if needed
    image = resize_image_if_needed(image, max_size)

    # Convert to RGB if necessary
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Save as JPEG for better compression
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    buffer.seek(0)

    # Return base64
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_base64}"


def batch_images_to_base64(
    images: list[Image.Image], optimize: bool = True
) -> list[str]:
    """Convert list of images to base64 strings.

    Args:
        images: List of PIL Image objects
        optimize: Whether to optimize images for LLM processing

    Returns:
        List of base64 encoded strings
    """
    if optimize:
        return [optimize_image_for_llm(img) for img in images]
    else:
        return [image_to_base64(img) for img in images]
