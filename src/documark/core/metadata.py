"""Metadata tracking for document conversions."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast


class ConversionMetadata:
    """Track metadata about document conversions."""

    def __init__(self, metadata_dir: Optional[Path] = None):
        """Initialize metadata tracker.

        Args:
            metadata_dir: Directory to store metadata files (default: .documark_cache)
        """
        self.metadata_dir = metadata_dir or Path.cwd() / ".documark_cache"
        self.metadata_dir.mkdir(exist_ok=True)

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_metadata_path(self, source_path: Path) -> Path:
        """Get the metadata file path for a source file."""
        # Use hash of absolute path to avoid collisions
        path_hash = hashlib.md5(str(source_path.absolute()).encode()).hexdigest()
        return self.metadata_dir / f"{path_hash}.json"

    def get_metadata(self, source_path: Path) -> Optional[dict[str, Any]]:
        """Get metadata for a source file.

        Args:
            source_path: Path to the source file

        Returns:
            Metadata dict or None if not found
        """
        metadata_path = self._get_metadata_path(source_path)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path) as f:
                data = json.load(f)
                return cast(dict[str, Any], data)
        except (OSError, json.JSONDecodeError):
            return None

    def save_metadata(
        self, source_path: Path, output_path: Path, source_hash: Optional[str] = None
    ) -> dict[str, Any]:
        """Save metadata for a conversion.

        Args:
            source_path: Path to the source file
            output_path: Path to the output file
            source_hash: Optional pre-calculated hash

        Returns:
            The saved metadata
        """
        metadata = {
            "source": str(source_path.absolute()),
            "output": str(output_path.absolute()),
            "source_mtime": source_path.stat().st_mtime,
            "source_hash": source_hash or self._get_file_hash(source_path),
            "converted_at": datetime.now().isoformat(),
            "documark_version": "0.1.0",
        }

        metadata_path = self._get_metadata_path(source_path)
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def needs_conversion(self, source_path: Path, output_path: Path) -> bool:
        """Check if a file needs to be converted.

        Args:
            source_path: Path to the source file
            output_path: Path to the output file

        Returns:
            True if conversion is needed, False otherwise
        """
        # Always convert if output doesn't exist
        if not output_path.exists():
            return True

        # Get stored metadata
        metadata = self.get_metadata(source_path)
        if not metadata:
            return True

        # Check if source file has changed
        current_mtime = source_path.stat().st_mtime
        if current_mtime > metadata.get("source_mtime", 0):
            return True

        # Optionally check hash for extra safety
        # This is slower but more reliable
        # current_hash = self._get_file_hash(source_path)
        # if current_hash != metadata.get("source_hash"):
        #     return True

        return False

    def clean_metadata(self, older_than_days: Optional[int] = None) -> int:
        """Clean old metadata files.

        Args:
            older_than_days: Remove metadata older than this many days

        Returns:
            Number of files removed
        """
        count = 0
        now = datetime.now()

        for metadata_file in self.metadata_dir.glob("*.json"):
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)

                # Check if source file still exists
                source_path = Path(metadata.get("source", ""))
                if not source_path.exists():
                    metadata_file.unlink()
                    count += 1
                    continue

                # Check age if specified
                if older_than_days:
                    converted_at = datetime.fromisoformat(
                        metadata.get("converted_at", "")
                    )
                    age_days = (now - converted_at).days
                    if age_days > older_than_days:
                        metadata_file.unlink()
                        count += 1

            except (OSError, json.JSONDecodeError, ValueError):
                # Remove corrupted metadata
                metadata_file.unlink()
                count += 1

        return count
