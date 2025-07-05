"""Pattern handling for output file paths."""

import re
from pathlib import Path
from typing import Optional


class OutputPattern:
    """Handle output path pattern substitution."""

    # Available variables for substitution
    VARIABLES = {
        "filename": "Original filename without extension",
        "name": "Alias for filename",
        "ext": "Original file extension",
        "extension": "Alias for ext",
        "dir": "Parent directory name",
        "dirname": "Alias for dir",
        "path": "Full directory path from cwd",
        "date": "Current date (YYYY-MM-DD)",
        "time": "Current time (HH-MM-SS)",
        "timestamp": "Current timestamp (YYYY-MM-DD_HH-MM-SS)",
    }

    def __init__(self, pattern: str = "{filename}.md"):
        """Initialize output pattern.

        Args:
            pattern: Pattern string with variables in {braces}
        """
        self.pattern = pattern
        self._validate_pattern()

    def _validate_pattern(self) -> None:
        """Validate the pattern contains valid variables."""
        # Extract all variables from pattern
        variables = re.findall(r"\{(\w+)\}", self.pattern)

        # Check if all variables are valid
        valid_vars = set(self.VARIABLES.keys())
        invalid_vars = [v for v in variables if v not in valid_vars]

        if invalid_vars:
            raise ValueError(
                f"Invalid variables in pattern: {', '.join(invalid_vars)}. "
                f"Valid variables: {', '.join(sorted(valid_vars))}"
            )

    def apply(self, source_path: Path, base_dir: Optional[Path] = None) -> Path:
        """Apply pattern to generate output path.

        Args:
            source_path: Source file path
            base_dir: Base directory for relative paths (default: cwd)

        Returns:
            Generated output path
        """
        from datetime import datetime

        base_dir = base_dir or Path.cwd()

        # Calculate relative path from base_dir
        try:
            rel_path = source_path.relative_to(base_dir)
        except ValueError:
            # If source is outside base_dir, use absolute path
            rel_path = source_path

        # Prepare substitution values
        now = datetime.now()
        values = {
            "filename": source_path.stem,
            "name": source_path.stem,
            "ext": source_path.suffix.lstrip("."),
            "extension": source_path.suffix.lstrip("."),
            "dir": source_path.parent.name,
            "dirname": source_path.parent.name,
            "path": str(rel_path.parent),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H-%M-%S"),
            "timestamp": now.strftime("%Y-%m-%d_%H-%M-%S"),
        }

        # Apply substitutions
        output_path = self.pattern
        for key, value in values.items():
            output_path = output_path.replace(f"{{{key}}}", value)

        # Handle absolute vs relative paths
        result = Path(output_path)
        if not result.is_absolute():
            # For relative patterns, maintain directory structure
            if "{path}" in self.pattern:
                # Path was explicitly included, use as-is
                result = base_dir / result
            else:
                # Preserve original directory structure
                result = source_path.parent / result

        return result

    @classmethod
    def common_patterns(cls) -> dict[str, str]:
        """Return common useful patterns."""
        return {
            "suffix": "{filename}.md",
            "hidden": ".{filename}.md",
            "directory": ".documark/{filename}.md",
            "nested": "{path}/.documark/{filename}.md",
            "flat": "converted/{filename}.md",
            "timestamp": "{filename}_{timestamp}.md",
            "preserve": "{path}/{filename}.md",
        }


def parse_output_location(
    source_path: Path,
    output: Optional[Path] = None,
    pattern: Optional[str] = None,
    is_batch: bool = False,
) -> Path:
    """Determine output location based on various inputs.

    Args:
        source_path: Source file path
        output: Explicit output path or directory
        pattern: Output pattern to use
        is_batch: Whether this is part of batch processing

    Returns:
        Resolved output path
    """
    # If explicit output file is given (and not batch mode), use it
    if output and not is_batch:
        if output.suffix:  # It's a file
            return output

    # If pattern is given, use it
    if pattern:
        pattern_obj = OutputPattern(pattern)
        result = pattern_obj.apply(source_path)

        # If output directory is specified, combine with pattern
        if output and output.is_dir():
            # Make pattern relative to output directory
            result = output / result.name

        return result

    # Default behavior
    if output:
        if output.is_dir() or is_batch:
            # Output is directory
            return output / f"{source_path.stem}.md"
        else:
            # Output is file
            return output
    else:
        # Default: same directory, .md extension
        return source_path.parent / f"{source_path.stem}.md"
