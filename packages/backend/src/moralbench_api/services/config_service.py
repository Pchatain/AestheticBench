"""Configuration service for validation and configuration resolution."""

import csv
from dataclasses import dataclass, field
from pathlib import Path


class ServiceError(Exception):
    """Structured error for services."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


@dataclass
class GraderInfo:
    """Information about a grader."""

    id: str
    name: str
    description: str
    score_range: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class GraderValidationResult:
    """Result of grader validation."""

    valid: bool
    grader_ids: list[str]  # With dependencies added
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class FileValidationResult:
    """Result of file validation."""

    valid: bool
    valid_files: list[str]
    errors: list[str] = field(default_factory=list)


class ConfigService:
    """Service for validation and configuration resolution."""

    VALID_GRADERS = {"preference1", "preference2", "justification", "relativism", "whimsical", "factual_depth"}

    GRADER_DEPENDENCIES = {
        "justification": ["preference1"],
    }

    GRADER_INFO = {
        "preference1": GraderInfo(
            id="preference1",
            name="Preference 1",
            description="Categorical preference scoring",
            score_range="-1, 0, 1",
            dependencies=[],
        ),
        "preference2": GraderInfo(
            id="preference2",
            name="Preference 2",
            description="Continuous preference scoring",
            score_range="-1.0 to 1.0",
            dependencies=[],
        ),
        "justification": GraderInfo(
            id="justification",
            name="Justification",
            description="Quality of justification rating",
            score_range="1 to 5",
            dependencies=["preference1"],
        ),
    }

    REQUIRED_CSV_COLUMNS = {"Topic", "Question", "Model Response", "Timestamp"}

    def get_available_graders(self) -> list[GraderInfo]:
        """Get list of all available graders with their info."""
        return list(self.GRADER_INFO.values())

    def parse_graders(self, graders_str: str) -> list[str]:
        """Parse comma-separated grader string.

        Args:
            graders_str: Comma-separated grader names (e.g., "preference1,justification")

        Returns:
            List of validated grader identifiers

        Raises:
            ServiceError: If any grader name is invalid
        """
        graders = [g.strip().lower() for g in graders_str.split(",") if g.strip()]

        invalid = [g for g in graders if g not in self.VALID_GRADERS]
        if invalid:
            raise ServiceError(
                "INVALID_GRADER",
                f"Invalid grader(s): {', '.join(invalid)}",
                {"valid_graders": list(self.VALID_GRADERS)},
            )

        return graders

    def ensure_dependencies(self, grader_ids: list[str]) -> list[str]:
        """Ensure required dependencies are included for each grader.

        Args:
            grader_ids: List of grader identifiers

        Returns:
            Updated list with dependencies added in proper order
        """
        result = list(grader_ids)
        added = []

        for grader in grader_ids:
            if grader in self.GRADER_DEPENDENCIES:
                for dep in self.GRADER_DEPENDENCIES[grader]:
                    if dep not in result:
                        result.insert(0, dep)
                        added.append(dep)

        return result

    def validate_graders(
        self,
        grader_ids: list[str],
        custom_prompt: str | None = None,
    ) -> GraderValidationResult:
        """Validate grader selection and add dependencies.

        Args:
            grader_ids: List of grader identifiers
            custom_prompt: Optional custom grader prompt

        Returns:
            GraderValidationResult with validation status
        """
        errors = []
        warnings = []

        # Check for invalid graders
        invalid = [g for g in grader_ids if g not in self.VALID_GRADERS]
        if invalid:
            errors.append(f"Invalid grader(s): {', '.join(invalid)}")

        # Filter to valid graders
        valid_graders = [g for g in grader_ids if g in self.VALID_GRADERS]

        # Add dependencies
        original_count = len(valid_graders)
        valid_graders = self.ensure_dependencies(valid_graders)
        if len(valid_graders) > original_count:
            added = [g for g in valid_graders if g not in grader_ids]
            warnings.append(f"Auto-added required grader(s): {', '.join(added)}")

        # Check for empty selection
        if not valid_graders and not custom_prompt:
            errors.append("No valid graders selected")

        return GraderValidationResult(
            valid=len(errors) == 0,
            grader_ids=valid_graders,
            errors=errors,
            warnings=warnings,
        )

    def validate_results_csv(self, file_path: Path) -> tuple[bool, str]:
        """Validate that results CSV has expected structure.

        Args:
            file_path: Path to results CSV

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = set(reader.fieldnames or [])

                missing = self.REQUIRED_CSV_COLUMNS - fieldnames
                if missing:
                    return False, f"Missing required columns: {', '.join(missing)}"

                return True, ""
        except Exception as e:
            return False, f"Error reading CSV: {e}"

    def validate_files(self, files: list[str]) -> FileValidationResult:
        """Validate multiple result files.

        Args:
            files: List of file paths

        Returns:
            FileValidationResult with validation status
        """
        valid_files = []
        errors = []

        for file_path in files:
            path = Path(file_path)
            if not path.exists():
                errors.append(f"File not found: {file_path}")
                continue

            is_valid, error_msg = self.validate_results_csv(path)
            if is_valid:
                valid_files.append(file_path)
            else:
                errors.append(f"{file_path}: {error_msg}")

        return FileValidationResult(
            valid=len(errors) == 0,
            valid_files=valid_files,
            errors=errors,
        )

    def read_models_from_file(self, file_path: Path) -> list[str]:
        """Read model names from a text file (one per line).

        Args:
            file_path: Path to text file containing model names

        Returns:
            List of model names

        Raises:
            ServiceError: If file not found or empty
        """
        if not file_path.exists():
            raise ServiceError(
                "FILE_NOT_FOUND",
                f"Models file not found: {file_path}",
                {"path": str(file_path)},
            )

        models = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    models.append(line)

        if not models:
            raise ServiceError(
                "EMPTY_FILE",
                f"No models found in file: {file_path}",
                {"path": str(file_path)},
            )

        return models
