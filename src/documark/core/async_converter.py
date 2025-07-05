"""Async converter for concurrent document processing."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.progress import Progress, TaskID

from .converter import DocumentConverter
from .patterns import parse_output_location

console = Console()


class AsyncDocumentConverter:
    """Async wrapper for concurrent document conversion."""

    def __init__(
        self, converter: Optional[DocumentConverter] = None, max_workers: int = 4
    ):
        """Initialize async converter.

        Args:
            converter: DocumentConverter instance (creates default if None)
            max_workers: Maximum concurrent conversions
        """
        self.converter = converter or DocumentConverter()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def convert_file_async(
        self,
        file_path: Path,
        output_dir: Optional[Path] = None,
        pattern: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        force: bool = False,
        progress: Optional[Progress] = None,
        task_id: Optional[TaskID] = None,
    ) -> dict[str, Any]:
        """Convert a single file asynchronously.

        Returns:
            Dict with status and result
        """
        loop = asyncio.get_event_loop()

        try:
            # Check if needs conversion first (fast operation)
            output_path = parse_output_location(
                file_path, output_dir, pattern, is_batch=True
            )

            if not self.converter.needs_conversion(file_path, output_path, force):
                return {
                    "status": "skipped",
                    "file": str(file_path),
                    "output": str(output_path),
                }

            # Update progress
            if progress and task_id is not None:
                progress.update(task_id, description=f"Converting {file_path.name}...")

            # Run conversion in thread pool
            result = await loop.run_in_executor(
                self.executor,
                self.converter.convert,
                file_path,
                None,  # Let pattern determine output
                pattern,
                custom_prompt,
                force,
            )

            return {
                "status": "success",
                "file": str(file_path),
                "output": str(output_path),
                "content": result,
            }

        except Exception as e:
            return {
                "status": "failed",
                "file": str(file_path),
                "error": str(e),
            }

    async def convert_recursive_async(
        self,
        directory: Path,
        output_dir: Optional[Path] = None,
        pattern: Optional[str] = None,
        include: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
        custom_prompt: Optional[str] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Recursively convert documents with concurrency.

        Args:
            directory: Directory to process
            output_dir: Optional output directory
            pattern: Optional output pattern
            include: File patterns to include
            exclude: File patterns to exclude
            custom_prompt: Optional custom prompt
            force: Force conversion even if up to date

        Returns:
            Summary of conversion results
        """
        from fnmatch import fnmatch

        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory}")

        # Default patterns for binary files
        if include is None:
            include = [
                "*.pdf",
                "*.PDF",
                "*.docx",
                "*.DOCX",
                "*.doc",
                "*.DOC",
                "*.png",
                "*.PNG",
                "*.jpg",
                "*.JPG",
                "*.jpeg",
                "*.JPEG",
                "*.gif",
                "*.GIF",
                "*.bmp",
                "*.BMP",
                "*.tiff",
                "*.TIFF",
                "*.tif",
                "*.TIF",
                "*.webp",
                "*.WEBP",
                "*.gdoc",
                "*.gsheet",
                "*.gslides",
            ]

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

        console.print(f"\n[blue]Found {len(all_files)} files to process[/blue]")

        # Create progress bar
        with Progress(console=console) as progress:
            main_task = progress.add_task(
                "[green]Converting files...", total=len(all_files)
            )

            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(self.max_workers)

            async def convert_with_semaphore(file_path: Path) -> dict[str, Any]:
                async with semaphore:
                    result = await self.convert_file_async(
                        file_path,
                        output_dir,
                        pattern,
                        custom_prompt,
                        force,
                        progress,
                        main_task,
                    )
                    progress.advance(main_task)
                    return result

            # Convert all files concurrently
            tasks = [convert_with_semaphore(file_path) for file_path in all_files]

            results = await asyncio.gather(*tasks)

        # Count results
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "failed")
        skipped = sum(1 for r in results if r["status"] == "skipped")

        # Show failures
        failures = [r for r in results if r["status"] == "failed"]
        if failures:
            console.print("\n[red]Failed conversions:[/red]")
            for failure in failures:
                console.print(f"  • {failure['file']}: {failure['error']}")

        # Summary
        console.print("\n[green]Conversion complete![/green]")
        console.print(f"  Successful: {successful}")
        console.print(f"  Failed: {failed}")
        console.print(f"  Skipped: {skipped}")
        console.print(f"  Total time: {progress.elapsed_time:.1f}s")

        return {
            "total": len(all_files),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    def __del__(self) -> None:
        """Clean up thread pool."""
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False)
