"""Workflow routes for discovery, estimation, and execution."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from moral_bench import Config, OpenRouterClient

from ..schemas.workflow import (
    CancelResponse,
    DryRunEstimateResponse,
    FileValidationRequest,
    FileValidationResponse,
    FilesResponse,
    GradeEstimateRequest,
    GraderInfo,
    GradersResponse,
    GraderValidationRequest,
    GraderValidationResponse,
    GradingEstimateResponse,
    JobStartResponse,
    JobStatus,
    PromptsFilesResponse,
    ResponseFileInfo,
    RunEstimateRequest,
    VersionsResponse,
)
from ..services.config_service import ConfigService
from ..services.discovery import DiscoveryService
from ..services.estimation import EstimationService

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Initialize services
# Note: For discovery, we use the project root paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
RESULTS_PATH = PROJECT_ROOT / "results"
PROMPTS_PATH = PROJECT_ROOT / "prompts"

discovery_service = DiscoveryService(
    results_base=RESULTS_PATH,
    prompts_base=PROMPTS_PATH,
)
config_service = ConfigService()


def get_openrouter_client() -> OpenRouterClient:
    """Create an OpenRouter client from environment."""
    try:
        config = Config.from_env()
        return OpenRouterClient(config)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {e}")


# === Discovery Endpoints ===


@router.get("/versions", response_model=VersionsResponse)
def list_versions() -> VersionsResponse:
    """List available result versions."""
    versions = discovery_service.discover_versions()
    return VersionsResponse(
        versions=[
            {
                "name": v.name,
                "response_count": v.response_count,
                "grade_count": v.grade_count,
            }
            for v in versions
        ]
    )


@router.get("/versions/{version}/files", response_model=FilesResponse)
def list_version_files(version: str) -> FilesResponse:
    """List response files in a version."""
    files = discovery_service.list_response_files(version)
    return FilesResponse(
        files=[
            ResponseFileInfo(
                path=f.path,
                filename=f.filename,
                model=f.model,
                date=f.date,
                size=f.size,
                response_count=f.response_count,
            )
            for f in files
        ]
    )


@router.get("/prompts", response_model=PromptsFilesResponse)
def list_prompts() -> PromptsFilesResponse:
    """List available prompts files."""
    files = discovery_service.list_prompts_files()
    return PromptsFilesResponse(
        files=[
            {"path": f.path, "filename": f.filename, "prompt_count": f.prompt_count}
            for f in files
        ]
    )


# === Configuration Endpoints ===


@router.get("/graders", response_model=GradersResponse)
def list_graders() -> GradersResponse:
    """List available graders with their info."""
    graders = config_service.get_available_graders()
    return GradersResponse(
        graders=[
            GraderInfo(
                id=g.id,
                name=g.name,
                description=g.description,
                score_range=g.score_range,
                dependencies=g.dependencies,
            )
            for g in graders
        ]
    )


@router.post("/graders/validate", response_model=GraderValidationResponse)
def validate_graders(request: GraderValidationRequest) -> GraderValidationResponse:
    """Validate grader selection, return with dependencies added."""
    result = config_service.validate_graders(request.grader_ids, request.custom_prompt)
    return GraderValidationResponse(
        valid=result.valid,
        grader_ids=result.grader_ids,
        errors=result.errors,
        warnings=result.warnings,
    )


@router.post("/files/validate", response_model=FileValidationResponse)
def validate_files(request: FileValidationRequest) -> FileValidationResponse:
    """Validate selected files for grading."""
    result = config_service.validate_files(request.files)
    return FileValidationResponse(
        valid=result.valid,
        valid_files=result.valid_files,
        errors=result.errors,
    )


# === Estimation Endpoints (Dry Run) ===


@router.post("/run/estimate", response_model=DryRunEstimateResponse)
def estimate_run(request: RunEstimateRequest) -> DryRunEstimateResponse:
    """Estimate costs for inference run."""
    prompts_path = Path(request.prompts_file)
    if not prompts_path.is_absolute():
        prompts_path = PROJECT_ROOT / prompts_path

    if not prompts_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Prompts file not found: {request.prompts_file}"
        )

    with get_openrouter_client() as client:
        estimation_service = EstimationService(client)
        estimate = estimation_service.estimate_run(request.models, prompts_path)

    return DryRunEstimateResponse(
        prompts_count=estimate.prompts_count,
        total_input_tokens=estimate.total_input_tokens,
        models=[
            {
                "model": m.model,
                "available": m.available,
                "input_cost_per_m": m.input_cost_per_m,
                "output_cost_per_m": m.output_cost_per_m,
                "estimated_min_cost": m.estimated_min_cost,
                "estimated_max_cost": m.estimated_max_cost,
                "error": m.error,
            }
            for m in estimate.models
        ],
        valid_models=estimate.valid_models,
        invalid_models=estimate.invalid_models,
        total_min_cost=estimate.total_min_cost,
        total_max_cost=estimate.total_max_cost,
    )


@router.post("/grade/estimate", response_model=GradingEstimateResponse)
def estimate_grading(request: GradeEstimateRequest) -> GradingEstimateResponse:
    """Estimate costs for grading run."""
    # Resolve file paths
    files = []
    for f in request.files:
        path = Path(f)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {f}")
        files.append(path)

    with get_openrouter_client() as client:
        estimation_service = EstimationService(client)
        estimate = estimation_service.estimate_grading(
            files, request.grader_ids, request.grader_model, request.custom_prompt
        )

    return GradingEstimateResponse(
        files=[
            {"path": f.path, "filename": f.filename, "response_count": f.response_count}
            for f in estimate.files
        ],
        total_responses=estimate.total_responses,
        graders=estimate.graders,
        custom_prompt_included=estimate.custom_prompt_included,
        total_grading_calls=estimate.total_grading_calls,
        estimated_input_tokens=estimate.estimated_input_tokens,
        estimated_output_tokens=estimate.estimated_output_tokens,
        grader_model=estimate.grader_model,
    )


# === Execution Endpoints ===
# Note: Full execution with WebSocket streaming will be added in a later phase
# For now, we provide placeholder endpoints


@router.post("/run/start", response_model=JobStartResponse)
def start_run(request: RunEstimateRequest) -> JobStartResponse:
    """Start inference run (placeholder - full implementation with WebSocket coming)."""
    # TODO: Implement background job execution with WebSocket streaming
    raise HTTPException(
        status_code=501,
        detail="Execution not yet implemented. Use CLI: uv run python main.py run",
    )


@router.post("/grade/start", response_model=JobStartResponse)
def start_grading(request: GradeEstimateRequest) -> JobStartResponse:
    """Start grading run (placeholder - full implementation with WebSocket coming)."""
    # TODO: Implement background job execution with WebSocket streaming
    raise HTTPException(
        status_code=501,
        detail="Execution not yet implemented. Use CLI: uv run python main.py grade",
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str) -> JobStatus:
    """Get status of running job (placeholder)."""
    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


@router.delete("/jobs/{job_id}", response_model=CancelResponse)
def cancel_job(job_id: str) -> CancelResponse:
    """Cancel running job (placeholder)."""
    raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
