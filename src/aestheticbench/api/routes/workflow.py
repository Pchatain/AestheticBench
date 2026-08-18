"""Workflow routes for discovery, estimation, and execution."""

import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from aestheticbench import Config, OpenRouterClient
from aestheticbench.paths import CACHE_DIR, PROJECT_ROOT, PROMPTS_DIR, RESULTS_DIR

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
    ModelsResponse,
    OpenRouterModel,
    PromptsFilesResponse,
    ResponseFileInfo,
    RunEstimateRequest,
    VersionsResponse,
)
from ..services.config_service import ConfigService
from ..services.discovery import DiscoveryService
from ..services.estimation import EstimationService
from ..services.execution import ExecutionService, job_manager, JobStatus as ExecJobStatus

router = APIRouter(prefix="/workflow", tags=["workflow"])

# Initialize services
RESULTS_PATH = RESULTS_DIR
PROMPTS_PATH = PROMPTS_DIR
BACKEND_DATA_PATH = CACHE_DIR
MODELS_CACHE_FILE = BACKEND_DATA_PATH / "openrouter_models.json"
MODELS_CACHE_MAX_AGE = 3600  # 1 hour

discovery_service = DiscoveryService(
    results_base=RESULTS_PATH,
    prompts_base=PROMPTS_PATH,
)
config_service = ConfigService()
execution_service = ExecutionService(
    project_root=PROJECT_ROOT,
    results_base=RESULTS_PATH,
)


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


@router.get("/models", response_model=ModelsResponse)
def list_models(refresh: bool = False) -> ModelsResponse:
    """List available OpenRouter models with caching."""
    cache_age = None
    use_cache = False

    # Check cache
    if not refresh and MODELS_CACHE_FILE.exists():
        try:
            with open(MODELS_CACHE_FILE, "r") as f:
                cache_data = json.load(f)
            cache_time = cache_data.get("timestamp", 0)
            cache_age = int(time.time() - cache_time)
            if cache_age < MODELS_CACHE_MAX_AGE:
                use_cache = True
                models = [OpenRouterModel(**m) for m in cache_data.get("models", [])]
                return ModelsResponse(models=models, cached=True, cache_age_seconds=cache_age)
        except (json.JSONDecodeError, KeyError):
            pass  # Invalid cache, fetch fresh

    # Fetch from OpenRouter
    with get_openrouter_client() as client:
        raw_models = client.get_available_models()

    if raw_models is None:
        raise HTTPException(status_code=502, detail="Failed to fetch models from OpenRouter")

    # Transform to our schema
    models = []
    for m in raw_models:
        pricing = m.get("pricing", {})
        models.append(
            OpenRouterModel(
                id=m.get("id", ""),
                name=m.get("name", m.get("id", "")),
                description=m.get("description"),
                context_length=m.get("context_length"),
                pricing_prompt=float(pricing.get("prompt", 0)) * 1_000_000 if pricing.get("prompt") else None,
                pricing_completion=float(pricing.get("completion", 0)) * 1_000_000 if pricing.get("completion") else None,
                top_provider=m.get("id", "").split("/")[0] if "/" in m.get("id", "") else None,
            )
        )

    # Sort by provider then name
    models.sort(key=lambda x: (x.top_provider or "", x.name))

    # Save to cache
    BACKEND_DATA_PATH.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "timestamp": time.time(),
        "models": [m.model_dump() for m in models],
    }
    with open(MODELS_CACHE_FILE, "w") as f:
        json.dump(cache_data, f)

    return ModelsResponse(models=models, cached=False, cache_age_seconds=None)


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


@router.post("/run/start", response_model=JobStartResponse)
def start_run(request: RunEstimateRequest) -> JobStartResponse:
    """Start inference run in background."""
    prompts_path = Path(request.prompts_file)
    if not prompts_path.is_absolute():
        prompts_path = PROJECT_ROOT / prompts_path

    if not prompts_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Prompts file not found: {request.prompts_file}"
        )

    job = execution_service.start_inference_job(
        models=request.models,
        prompts_file=prompts_path,
        output_dir=None,  # Use default
    )

    return JobStartResponse(job_id=job.id, status=job.status.value)


@router.post("/grade/start", response_model=JobStartResponse)
def start_grading(request: GradeEstimateRequest) -> JobStartResponse:
    """Start grading run in background."""
    # Resolve file paths
    files = []
    for f in request.files:
        path = Path(f)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {f}")
        files.append(path)

    job = execution_service.start_grading_job(
        files=files,
        grader_ids=request.grader_ids,
        grader_model=request.grader_model,
        output_dir=None,  # Use default
        custom_prompt=request.custom_prompt,
    )

    return JobStartResponse(job_id=job.id, status=job.status.value)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def get_job_status(job_id: str) -> JobStatus:
    """Get status of running job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobStatus(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        current_step=job.current_step,
        total_steps=job.total_steps,
        current_step_index=job.current_step_index,
        result=job.result,
        error=job.error,
    )


@router.delete("/jobs/{job_id}", response_model=CancelResponse)
def cancel_job(job_id: str) -> CancelResponse:
    """Cancel running job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    cancelled = job_manager.cancel_job(job_id)
    return CancelResponse(
        job_id=job_id,
        cancelled=cancelled,
        message="Job cancelled" if cancelled else "Job could not be cancelled (already completed or failed)",
    )
