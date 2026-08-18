"""Discovery service for finding versions, files, and prompts."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class VersionInfo:
    """Information about a result version."""

    name: str
    response_count: int
    grade_count: int


@dataclass
class ResponseFileInfo:
    """Information about a response file."""

    path: str
    filename: str
    model: str
    date: str
    size: str
    response_count: int


@dataclass
class PromptsFileInfo:
    """Information about a prompts file."""

    path: str
    filename: str
    prompt_count: int


class DiscoveryService:
    """Service for discovering versions, files, and prompts."""

    def __init__(
        self,
        results_base: Path = Path("results"),
        prompts_base: Path = Path("prompts"),
    ):
        self.results_base = results_base
        self.prompts_base = prompts_base

    def discover_versions(self) -> list[VersionInfo]:
        """List available result versions with metadata.

        Returns:
            List of VersionInfo sorted newest first.
        """
        if not self.results_base.exists():
            return []

        versions = []
        for item in self.results_base.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                # Check for responses subdirectory first, otherwise look at root
                responses_dir = item / "responses"
                grades_dir = item / "grades"

                if responses_dir.exists():
                    response_count = len(list(responses_dir.glob("*.csv")))
                else:
                    # CSVs directly in version folder (excluding combined files)
                    response_count = len([
                        f for f in item.glob("*.csv")
                        if not f.name.startswith("combined")
                    ])

                grade_count = (
                    len(list(grades_dir.glob("*.csv")))
                    if grades_dir.exists()
                    else 0
                )

                if response_count > 0 or grade_count > 0:
                    versions.append(
                        VersionInfo(
                            name=item.name,
                            response_count=response_count,
                            grade_count=grade_count,
                        )
                    )

        # Sort versions: extract numeric parts for proper ordering
        def version_key(v: VersionInfo) -> tuple:
            parts = v.name.lstrip("v").split(".")
            return tuple(int(p) if p.isdigit() else 0 for p in parts)

        return sorted(versions, key=version_key, reverse=True)

    def list_response_files(self, version: str) -> list[ResponseFileInfo]:
        """List response files for a version with metadata.

        Args:
            version: Version name (e.g., 'v2')

        Returns:
            List of ResponseFileInfo sorted by date (newest first).
        """
        version_dir = self.results_base / version
        responses_dir = version_dir / "responses"

        # Check for responses subdirectory first, otherwise use version root
        if responses_dir.exists():
            search_dir = responses_dir
        elif version_dir.exists():
            search_dir = version_dir
        else:
            return []

        files = []
        for file_path in search_dir.glob("*.csv"):
            # Skip combined files
            if file_path.name.startswith("combined"):
                continue
            info = self._get_file_info(file_path)
            files.append(info)

        # Sort by date (newest first)
        return sorted(files, key=lambda f: f.date, reverse=True)

    def list_grade_files(self, version: str) -> list[ResponseFileInfo]:
        """List graded files for a version with metadata.

        Args:
            version: Version name (e.g., 'v2')

        Returns:
            List of ResponseFileInfo sorted by date (newest first).
        """
        grades_dir = self.results_base / version / "grades"

        if not grades_dir.exists():
            return []

        files = []
        for file_path in grades_dir.glob("*.csv"):
            info = self._get_file_info(file_path)
            files.append(info)

        return sorted(files, key=lambda f: f.date, reverse=True)

    def list_prompts_files(self) -> list[PromptsFileInfo]:
        """List available prompts files.

        Returns:
            List of PromptsFileInfo.
        """
        if not self.prompts_base.exists():
            return []

        files = []
        for file_path in self.prompts_base.iterdir():
            if file_path.suffix in (".csv", ".tsv"):
                prompt_count = self._count_prompts(file_path)
                files.append(
                    PromptsFileInfo(
                        path=str(file_path),
                        filename=file_path.name,
                        prompt_count=prompt_count,
                    )
                )

        return sorted(files, key=lambda f: f.filename)

    def _get_file_info(self, file_path: Path) -> ResponseFileInfo:
        """Extract info from a response/grade file.

        Args:
            file_path: Path to CSV file

        Returns:
            ResponseFileInfo with metadata
        """
        name = file_path.stem
        # Parse filename: {provider}_{model}_{date}_{time}.csv
        parts = name.rsplit("_", 2)

        if len(parts) >= 3:
            model_name = parts[0]
            date_str = parts[1]
            time_str = parts[2]
            try:
                timestamp = datetime.strptime(
                    f"{date_str}_{time_str}", "%Y-%m-%d_%H-%M-%S"
                )
                date_display = timestamp.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                date_display = "Unknown date"
        else:
            model_name = name
            date_display = "Unknown date"

        # Get file size
        size_bytes = file_path.stat().st_size
        if size_bytes > 1024 * 1024:
            size_display = f"{size_bytes / (1024 * 1024):.1f}MB"
        elif size_bytes > 1024:
            size_display = f"{size_bytes / 1024:.1f}KB"
        else:
            size_display = f"{size_bytes}B"

        # Count responses
        response_count = self._count_csv_rows(file_path)

        return ResponseFileInfo(
            path=str(file_path),
            filename=file_path.name,
            model=model_name,
            date=date_display,
            size=size_display,
            response_count=response_count,
        )

    def _count_csv_rows(self, file_path: Path) -> int:
        """Count data rows in a CSV file (excluding header)."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                return sum(1 for _ in reader)
        except Exception:
            return 0

    def _count_prompts(self, file_path: Path) -> int:
        """Count prompts in a prompts file."""
        delimiter = "\t" if file_path.suffix == ".tsv" else ","
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=delimiter)
                next(reader, None)  # Skip header
                return sum(1 for _ in reader)
        except Exception:
            return 0

    def derive_output_dir(
        self, prompts_file: Path, subdir: str = "responses"
    ) -> Path:
        """Derive output directory from prompt file name.

        Args:
            prompts_file: Path to the prompt file (e.g., prompts/v2.tsv)
            subdir: Subdirectory within results/{version}/

        Returns:
            Path to output directory (e.g., results/v2/responses)
        """
        version = prompts_file.stem
        return self.results_base / version / subdir

    def derive_grades_output_dir(self, results_file: Path) -> Path:
        """Derive grades output directory from results file path.

        Args:
            results_file: Path to input results CSV

        Returns:
            Path to grades output directory
        """
        parts = results_file.parts

        if "results" in parts:
            results_idx = parts.index("results")
            if len(parts) > results_idx + 1:
                version = parts[results_idx + 1]
                return self.results_base / version / "grades"

        return self.results_base / "grades"
