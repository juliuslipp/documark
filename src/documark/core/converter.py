"""Main converter logic using LiteLLM."""

import json
import os
from pathlib import Path
from typing import Any, Optional, Union, cast

import litellm
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..processors import (
    BaseProcessor,
    DocxProcessor,
    GoogleDocsProcessor,
    ImageProcessor,
    PDFProcessor,
)
from ..utils.image_utils import batch_images_to_base64
from .metadata import ConversionMetadata
from .patterns import parse_output_location

# Load environment variables
load_dotenv()

console = Console()

# JSON Schema for structured output
MARKDOWN_SCHEMA = {
    "type": "object",
    "properties": {
        "markdown_content": {
            "type": "string",
            "description": "The extracted document content in Markdown format",
        }
    },
    "required": ["markdown_content"],
    "additionalProperties": False,
}


class DocumentConverter:
    """Convert documents to markdown using AI."""

    def __init__(
        self,
        model: str = "gemini/gemini-2.5-flash",
        dpi: int = 300,
        cache_metadata: bool = True,
    ):
        """Initialize converter.

        Args:
            model: LiteLLM model string (default: gemini/gemini-2.5-flash)
            dpi: DPI for document rendering (default: 300)
            cache_metadata: Whether to track conversion metadata
        """
        self.model = model
        self.dpi = dpi
        self.cache_metadata = cache_metadata

        # Initialize processors (only binary files that need conversion)
        self.processors: list[BaseProcessor] = [
            PDFProcessor(dpi=dpi),
            DocxProcessor(dpi=dpi),
            ImageProcessor(),
            GoogleDocsProcessor(dpi=dpi),
        ]

        # Initialize metadata tracker
        self.metadata = ConversionMetadata() if cache_metadata else None

        # Configure LiteLLM
        self._setup_litellm()

    def _setup_litellm(self) -> None:
        """Setup LiteLLM configuration."""
        # Set API keys from environment
        if gemini_key := os.getenv("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = gemini_key

        # Optional: Set other provider keys
        if openai_key := os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = openai_key

        if anthropic_key := os.getenv("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key

    def _get_processor(self, source: Union[str, Path]) -> BaseProcessor:
        """Get appropriate processor for source."""
        for processor in self.processors:
            if processor.can_process(source):
                return processor

        # Collect supported types
        supported = []
        for p in self.processors:
            if hasattr(p, "supported_extensions"):
                supported.extend(p.supported_extensions)

        raise ValueError(
            f"No processor found for: {source}. "
            f"Supported types: {', '.join(sorted(set(supported)))}"
        )

    def needs_conversion(
        self, source_path: Path, output_path: Path, force: bool = False
    ) -> bool:
        """Check if a file needs to be converted.

        Args:
            source_path: Source file path
            output_path: Output file path
            force: Force conversion even if up to date

        Returns:
            True if conversion is needed
        """
        if force:
            return True

        if not self.metadata:
            # Without metadata, only check if output exists
            return not output_path.exists()

        return self.metadata.needs_conversion(source_path, output_path)

    def convert(
        self,
        source: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        pattern: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        force: bool = False,
    ) -> str:
        """Convert document to markdown.

        Args:
            source: Path to input document or URL
            output_path: Optional path for output markdown file
            pattern: Optional pattern for output path
            custom_prompt: Optional custom prompt for conversion
            force: Force conversion even if up to date

        Returns:
            Markdown content
        """
        # Resolve paths
        if isinstance(source, str) and not (
            source.startswith("http://") or source.startswith("https://")
        ):
            source = Path(source)

        # Determine output path
        if isinstance(source, Path):
            output_path_parsed = (
                Path(output_path) if isinstance(output_path, str) else output_path
            )
            output_path = parse_output_location(source, output_path_parsed, pattern)
        elif output_path:
            output_path = Path(output_path)
        else:
            # For URLs, require explicit output path
            raise ValueError("Output path required for URL sources")

        # Check if conversion is needed
        if isinstance(source, Path) and not self.needs_conversion(
            source, output_path, force
        ):
            console.print(f"[yellow]Skipping[/yellow] {source.name} (up to date)")
            return output_path.read_text(encoding="utf-8")

        # Get processor
        processor = self._get_processor(source)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Get content from processor
            task = progress.add_task("Processing document...", total=None)
            content = processor.get_content(source)
            progress.update(task, completed=True)

            # Handle based on content type
            if isinstance(content, str):
                # Text-based processor - no LLM needed
                markdown = content
            else:
                # Image-based processor - need LLM
                task = progress.add_task("Encoding images...", total=None)
                image_data = batch_images_to_base64(content, optimize=True)
                progress.update(task, completed=True)

                task = progress.add_task("Converting to markdown...", total=None)
                filename = source.name if isinstance(source, Path) else "document"
                markdown = self._convert_with_llm(image_data, filename, custom_prompt)
                progress.update(task, completed=True)

        # Save output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        console.print(f"[green]✓[/green] Saved to {output_path}")

        # Save metadata
        if self.metadata and isinstance(source, Path):
            self.metadata.save_metadata(source, output_path)

        return markdown

    def _convert_with_llm(
        self, images: list[str], filename: str, custom_prompt: Optional[str] = None
    ) -> str:
        """Convert images to markdown using LLM."""
        # Build messages
        system_prompt = (
            "You are an expert at converting documents to clean, well-formatted Markdown. "
            "Extract all text content, preserve structure, formatting, and semantic meaning. "
            "For tables, use proper Markdown table syntax. "
            "For images/figures, describe them briefly in italics. "
            "Maintain heading hierarchy and list structures. "
            "Return the result in the specified JSON format."
        )

        user_prompt = custom_prompt or (
            f"Convert this document '{filename}' to Markdown. "
            "Extract all content while preserving the structure and formatting."
        )

        # Build message content
        content = [{"type": "text", "text": user_prompt}]
        for i, img_data in enumerate(images):
            img_content: dict[str, Any] = {
                "type": "image_url",
                "image_url": {"url": img_data},
            }
            content.append(img_content)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

        try:
            # Call LLM with structured output
            response = litellm.completion(
                model=self.model,
                messages=messages,
                temperature=0.1,  # Low temperature for accuracy
                max_tokens=32000,  # Generous token limit
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "markdown_extraction",
                        "strict": True,
                        "schema": MARKDOWN_SCHEMA,
                    },
                },
            )

            # Extract content from JSON response
            try:
                result = json.loads(response.choices[0].message.content)
                return cast(str, result["markdown_content"]).strip()
            except (json.JSONDecodeError, KeyError) as e:
                console.print(
                    f"[yellow]Warning: Failed to parse JSON response: {str(e)}[/yellow]"
                )
                # Fall back to raw content
                content = response.choices[0].message.content
                return cast(str, content).strip()

        except Exception as e:
            console.print(f"[red]Error calling LLM: {str(e)}[/red]")
            raise

    def batch_convert(
        self,
        sources: list[Union[str, Path]],
        output_dir: Optional[Union[str, Path]] = None,
        pattern: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        force: bool = False,
    ) -> list[str]:
        """Convert multiple documents to markdown.

        Args:
            sources: List of paths or URLs to input documents
            output_dir: Optional directory for output files
            pattern: Optional pattern for output paths
            custom_prompt: Optional custom prompt for conversion
            force: Force conversion even if up to date

        Returns:
            List of markdown contents
        """
        results = []

        for source in sources:
            # Determine source type
            if isinstance(source, str) and not (
                source.startswith("http://") or source.startswith("https://")
            ):
                source = Path(source)

            # Display source name
            source_name = source.name if isinstance(source, Path) else source
            console.print(f"\n[blue]Processing:[/blue] {source_name}")

            try:
                # Convert with appropriate output handling
                if isinstance(source, Path):
                    markdown = self.convert(
                        source, output_dir, pattern, custom_prompt, force
                    )
                else:
                    # For URLs, need explicit output path
                    if not output_dir:
                        raise ValueError("Output directory required for URL sources")
                    output_path = Path(output_dir) / "converted_document.md"
                    markdown = self.convert(
                        source, output_path, None, custom_prompt, force
                    )

                results.append(markdown)

            except Exception as e:
                console.print(f"[red]Failed:[/red] {str(e)}")
                results.append("")

        return results

    def convert_recursive(
        self,
        directory: Path,
        output_dir: Optional[Path] = None,
        pattern: Optional[str] = None,
        include: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        custom_prompt: Optional[str] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Recursively convert documents in a directory.

        Args:
            directory: Directory to process
            output_dir: Optional output directory
            pattern: Optional output pattern
            include: File patterns to include (e.g., ["*.pdf", "*.docx"])
            exclude: File patterns to exclude (e.g., ["temp/*", "*.tmp"])
            custom_prompt: Optional custom prompt
            force: Force conversion even if up to date

        Returns:
            Summary of conversion results
        """
        from fnmatch import fnmatch

        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Default patterns
        if include is None:
            # Get all supported extensions
            include = []
            for processor in self.processors:
                if hasattr(processor, "supported_extensions"):
                    include.extend(
                        [f"*{ext}" for ext in processor.supported_extensions]
                    )

        if exclude is None:
            exclude = [".*", "*/.*", "__pycache__/*", "*.pyc"]

        # Find all matching files
        all_files = []
        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            # Check include patterns
            rel_path = str(file_path.relative_to(directory))
            if not any(fnmatch(rel_path, pat) for pat in include):
                continue

            # Check exclude patterns
            if any(fnmatch(rel_path, pat) for pat in exclude):
                continue

            all_files.append(file_path)

        # Convert files
        console.print(f"\n[blue]Found {len(all_files)} files to process[/blue]")

        successful = 0
        failed = 0
        skipped = 0

        for file_path in all_files:
            try:
                # Check if needs conversion
                output_path = parse_output_location(
                    file_path, output_dir, pattern, is_batch=True
                )

                if not self.needs_conversion(file_path, output_path, force):
                    skipped += 1
                    continue

                # Convert
                self.convert(
                    file_path,
                    None,  # Let pattern determine output
                    pattern,
                    custom_prompt,
                    force,
                )
                successful += 1

            except Exception as e:
                console.print(f"[red]Failed:[/red] {file_path.name} - {str(e)}")
                failed += 1

        # Summary
        console.print("\n[green]Conversion complete![/green]")
        console.print(f"  Successful: {successful}")
        console.print(f"  Failed: {failed}")
        console.print(f"  Skipped: {skipped}")

        return {
            "total": len(all_files),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
        }
