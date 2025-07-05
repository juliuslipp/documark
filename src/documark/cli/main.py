"""CLI interface for DocuMark."""

import asyncio
import os
from pathlib import Path
from typing import Any, Optional, Union

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .. import __version__
from ..core.async_converter import AsyncDocumentConverter
from ..core.converter import DocumentConverter
from ..core.metadata import ConversionMetadata

app = typer.Typer(
    name="documark",
    help="Convert documents to markdown using AI",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"DocuMark version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """DocuMark - Convert documents to markdown using AI."""
    pass


@app.command()
def convert(
    paths: list[Path] = typer.Argument(
        ...,
        help="Path(s) to document files or directories to convert",
        exists=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (single file) or directory (multiple files)",
    ),
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern",
        help="Output path pattern (e.g., '{path}/.{filename}.md')",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Recursively convert files in directories",
    ),
    model: str = typer.Option(
        "gemini/gemini-2.5-flash",
        "--model",
        "-m",
        help="LiteLLM model string to use",
    ),
    dpi: int = typer.Option(
        300,
        "--dpi",
        "-d",
        help="DPI for document rendering",
        min=72,
        max=600,
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "--prompt",
        "-p",
        help="Custom prompt for conversion",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force conversion even if files are up to date",
    ),
    workers: int = typer.Option(
        4,
        "--workers",
        "-w",
        help="Number of concurrent workers for recursive conversion",
        min=1,
        max=16,
    ),
    include: Optional[str] = typer.Option(
        None,
        "--include",
        help="Comma-separated file patterns to include (e.g., '*.pdf,*.docx')",
    ),
    exclude: Optional[str] = typer.Option(
        None,
        "--exclude",
        help="Comma-separated file patterns to exclude (e.g., 'temp/*,*.tmp')",
    ),
) -> None:
    """Convert documents to markdown."""
    # Show banner
    console.print(
        Panel.fit(
            f"[bold blue]DocuMark v{__version__}[/bold blue]\n"
            "Converting documents to markdown using AI",
            border_style="blue",
        )
    )

    # Check API key
    if not os.getenv("GEMINI_API_KEY") and model.startswith("gemini/"):
        console.print("[red]Error:[/red] GEMINI_API_KEY not found in environment")
        console.print("Please set your API key: export GEMINI_API_KEY=your_key_here")
        raise typer.Exit(1)

    # Parse include/exclude patterns
    include_patterns = include.split(",") if include else None
    exclude_patterns = exclude.split(",") if exclude else None

    # Initialize converter
    try:
        converter = DocumentConverter(model=model, dpi=dpi)
    except Exception as e:
        console.print(f"[red]Error initializing converter:[/red] {str(e)}")
        raise typer.Exit(1)

    # Separate files and directories
    files = []
    directories = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            directories.append(path)

    # Handle recursive directory conversion
    if directories and recursive:
        async_converter = AsyncDocumentConverter(converter, max_workers=workers)

        async def convert_all_dirs() -> list[dict[str, Any]]:
            tasks = []
            for directory in directories:
                tasks.append(
                    async_converter.convert_recursive_async(
                        directory,
                        output,
                        pattern,
                        include_patterns,
                        exclude_patterns,
                        prompt,
                        force,
                    )
                )
            results = await asyncio.gather(*tasks)
            return results  # type: ignore

        results = asyncio.run(convert_all_dirs())

        # Show combined summary
        total_files = sum(r["total"] for r in results)  # type: ignore
        total_success = sum(r["successful"] for r in results)  # type: ignore
        total_failed = sum(r["failed"] for r in results)  # type: ignore
        total_skipped = sum(r["skipped"] for r in results)  # type: ignore

        if len(directories) > 1:
            console.print("\n[bold]Overall Summary:[/bold]")
            console.print(f"  Total files: {total_files}")
            console.print(f"  Successful: {total_success}")
            console.print(f"  Failed: {total_failed}")
            console.print(f"  Skipped: {total_skipped}")

        # Exit with error if any failed
        if total_failed > 0:
            raise typer.Exit(1)

    # Handle non-recursive directory conversion
    elif directories and not recursive:
        console.print(
            "[yellow]Note:[/yellow] Use --recursive to convert files in directories"
        )
        for directory in directories:
            console.print(f"  Skipping directory: {directory}")

    # Handle file conversion
    if files:
        # Single file conversion
        if len(files) == 1 and not directories:
            file_path = files[0]

            try:
                converter.convert(file_path, output, pattern, prompt, force)
                console.print("\n[green]✓[/green] Conversion complete!")
            except Exception as e:
                console.print(f"[red]Error during conversion:[/red] {str(e)}")
                raise typer.Exit(1)

        # Multiple file conversion
        else:
            try:
                files_union: list[Union[str, Path]] = files  # type: ignore
                batch_results = converter.batch_convert(
                    files_union, output, pattern, prompt, force
                )

                # Show summary
                console.print("\n[green]✓[/green] Batch conversion complete!")

                table = Table(title="Conversion Results")
                table.add_column("File", style="cyan")
                table.add_column("Status", style="green")

                for file_path, result in zip(files, batch_results):
                    status = "✓ Success" if result else "✗ Failed"
                    table.add_row(file_path.name, status)

                console.print(table)

            except Exception as e:
                console.print(f"[red]Error during batch conversion:[/red] {str(e)}")
                raise typer.Exit(1)


@app.command()
def status(
    directory: Path = typer.Argument(
        Path("."),
        help="Directory to check status for",
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern",
        help="Output path pattern to check",
    ),
    include: Optional[str] = typer.Option(
        None,
        "--include",
        help="Comma-separated file patterns to include",
    ),
    exclude: Optional[str] = typer.Option(
        None,
        "--exclude",
        help="Comma-separated file patterns to exclude",
    ),
) -> None:
    """Check conversion status of files in a directory."""
    from fnmatch import fnmatch

    from ..core.patterns import parse_output_location

    # Parse patterns
    include_patterns = (
        include.split(",")
        if include
        else ["*.pdf", "*.docx", "*.gdoc", "*.png", "*.jpg", "*.jpeg"]
    )
    exclude_patterns = exclude.split(",") if exclude else [".*", "*/.*"]

    # Initialize metadata tracker
    metadata = ConversionMetadata()

    # Find all matching files
    needs_conversion = []
    up_to_date = []

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue

        # Check patterns
        rel_path = str(file_path.relative_to(directory))
        if not any(fnmatch(rel_path, pat) for pat in include_patterns):
            continue
        if any(fnmatch(rel_path, pat) for pat in exclude_patterns):
            continue

        # Check conversion status
        output_path = parse_output_location(file_path, None, pattern, is_batch=True)
        if metadata.needs_conversion(file_path, output_path):
            needs_conversion.append((file_path, output_path))
        else:
            up_to_date.append((file_path, output_path))

    # Display results
    console.print(
        Panel.fit(
            f"[bold blue]Conversion Status[/bold blue]\n" f"Directory: {directory}",
            border_style="blue",
        )
    )

    if needs_conversion:
        console.print(
            f"\n[yellow]Files needing conversion ({len(needs_conversion)}):[/yellow]"
        )
        for src, dst in needs_conversion[:10]:  # Show first 10
            console.print(f"  • {src.relative_to(directory)} → {dst.name}")
        if len(needs_conversion) > 10:
            console.print(f"  ... and {len(needs_conversion) - 10} more")

    if up_to_date:
        console.print(f"\n[green]Files up to date ({len(up_to_date)}):[/green]")
        for src, dst in up_to_date[:5]:  # Show first 5
            console.print(f"  • {src.relative_to(directory)} → {dst.name}")
        if len(up_to_date) > 5:
            console.print(f"  ... and {len(up_to_date) - 5} more")

    # Summary
    total = len(needs_conversion) + len(up_to_date)
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total files: {total}")
    console.print(f"  Need conversion: {len(needs_conversion)}")
    console.print(f"  Up to date: {len(up_to_date)}")


@app.command()
def clean(
    directory: Path = typer.Argument(
        Path("."),
        help="Directory to clean metadata for",
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    older_than: Optional[int] = typer.Option(
        None,
        "--older-than",
        help="Remove metadata older than N days",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Clean conversion metadata and optionally old conversions."""
    metadata = ConversionMetadata()

    # Show what will be cleaned
    console.print(
        Panel.fit(
            f"[bold blue]Clean Metadata[/bold blue]\n" f"Directory: {directory}",
            border_style="blue",
        )
    )

    if older_than:
        console.print(f"Will remove metadata older than {older_than} days")
    else:
        console.print("Will remove metadata for deleted source files")

    # Confirm
    if not yes:
        confirm = typer.confirm("Continue?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit()

    # Clean
    removed = metadata.clean_metadata(older_than)
    console.print(f"\n[green]✓[/green] Removed {removed} metadata entries")


@app.command()
def list_models() -> None:
    """List commonly used LiteLLM model strings."""
    console.print(
        Panel.fit(
            "[bold blue]Common LiteLLM Model Strings[/bold blue]",
            border_style="blue",
        )
    )

    models = [
        (
            "Gemini",
            [
                "gemini/gemini-2.5-flash",
                "gemini/gemini-1.5-pro",
                "gemini/gemini-1.5-flash",
            ],
        ),
        (
            "OpenAI",
            [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        ),
        (
            "Anthropic",
            [
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
        ),
    ]

    for provider, model_list in models:
        console.print(f"\n[yellow]{provider}:[/yellow]")
        for model in model_list:
            console.print(f"  • {model}")

    console.print("\n[dim]Set API keys as environment variables:[/dim]")
    console.print("[dim]  • GEMINI_API_KEY[/dim]")
    console.print("[dim]  • OPENAI_API_KEY[/dim]")
    console.print("[dim]  • ANTHROPIC_API_KEY[/dim]")


@app.command()
def supported() -> None:
    """Show supported file types."""
    console.print(
        Panel.fit(
            "[bold blue]Supported File Types[/bold blue]",
            border_style="blue",
        )
    )

    file_types = [
        ("Documents", [".pdf", ".docx", ".doc"]),
        ("Images", [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"]),
        ("Google Docs", [".gdoc", ".gsheet", ".gslides"]),
    ]

    table = Table()
    table.add_column("Category", style="cyan")
    table.add_column("Extensions", style="green")

    for category, extensions in file_types:
        table.add_row(category, ", ".join(extensions))

    console.print(table)

    console.print(
        "\n[dim]Note: DocuMark focuses on binary files that Claude Code cannot read directly.[/dim]"
    )
    console.print(
        "[dim]Text files (.txt, .md, .py, etc.) can be read directly by Claude Code.[/dim]"
    )


if __name__ == "__main__":
    app()
