"""Pydantic schemas for workflow API endpoints."""

from pydantic import BaseModel, Field


# === Discovery Schemas ===


class VersionInfo(BaseModel):
    """Information about a result version."""

    name: str
    response_count: int
    grade_count: int


class VersionsResponse(BaseModel):
    """Response for listing versions."""

    versions: list[VersionInfo]


class ResponseFileInfo(BaseModel):
    """Information about a response file."""

    path: str
    filename: str
    model: str
    date: str
    size: str
    response_count: int


class FilesResponse(BaseModel):
    """Response for listing files."""

    files: list[ResponseFileInfo]


class PromptsFileInfo(BaseModel):
    """Information about a prompts file."""

    path: str
    filename: str
    prompt_count: int


class PromptsFilesResponse(BaseModel):
    """Response for listing prompts files."""

    files: list[PromptsFileInfo]


# === Grader Schemas ===


class GraderInfo(BaseModel):
    """Information about a grader."""

    id: str
    name: str
    description: str
    score_range: str
    dependencies: list[str]


class GradersResponse(BaseModel):
    """Response for listing graders."""

    graders: list[GraderInfo]


class GraderValidationRequest(BaseModel):
    """Request to validate grader selection."""

    grader_ids: list[str]
    custom_prompt: str | None = None


class GraderValidationResponse(BaseModel):
    """Response for grader validation."""

    valid: bool
    grader_ids: list[str] = Field(description="Grader IDs with dependencies added")
    errors: list[str] = []
    warnings: list[str] = []


class FileValidationRequest(BaseModel):
    """Request to validate files."""

    files: list[str]


class FileValidationResponse(BaseModel):
    """Response for file validation."""

    valid: bool
    valid_files: list[str]
    errors: list[str] = []


# === Estimation Schemas ===


class RunEstimateRequest(BaseModel):
    """Request for inference cost estimate."""

    models: list[str]
    prompts_file: str


class ModelEstimate(BaseModel):
    """Cost estimate for a single model."""

    model: str
    available: bool
    input_cost_per_m: float | None = None
    output_cost_per_m: float | None = None
    estimated_min_cost: float | None = None
    estimated_max_cost: float | None = None
    error: str | None = None


class DryRunEstimateResponse(BaseModel):
    """Response for inference dry-run estimate."""

    prompts_count: int
    total_input_tokens: int
    models: list[ModelEstimate]
    valid_models: list[str]
    invalid_models: list[str]
    total_min_cost: float
    total_max_cost: float


class GradeEstimateRequest(BaseModel):
    """Request for grading cost estimate."""

    files: list[str]
    grader_ids: list[str]
    grader_model: str = "openai/gpt-4o"
    custom_prompt: str | None = None


class FileEstimate(BaseModel):
    """Estimate for a single file."""

    path: str
    filename: str
    response_count: int


class GradingEstimateResponse(BaseModel):
    """Response for grading dry-run estimate."""

    files: list[FileEstimate]
    total_responses: int
    graders: list[str]
    custom_prompt_included: bool
    total_grading_calls: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    grader_model: str


# === Execution Schemas ===


class RunStartRequest(BaseModel):
    """Request to start inference run."""

    models: list[str]
    prompts_file: str
    output_dir: str | None = None


class GradeStartRequest(BaseModel):
    """Request to start grading run."""

    files: list[str]
    grader_ids: list[str]
    grader_model: str = "openai/gpt-4o"
    custom_prompt: str | None = None
    output_dir: str | None = None


class JobStartResponse(BaseModel):
    """Response for starting a job."""

    job_id: str
    status: str = "pending"


class JobStatus(BaseModel):
    """Status of a running job."""

    job_id: str
    status: str = Field(description="pending, running, completed, failed")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_step: str | None = None
    total_steps: int | None = None
    current_step_index: int | None = None
    result: dict | None = None
    error: str | None = None


class CancelResponse(BaseModel):
    """Response for cancelling a job."""

    job_id: str
    cancelled: bool
    message: str
