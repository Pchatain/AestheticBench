"""Execution service for running inference and grading jobs."""

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from moral_bench import Config, OpenRouterClient
from moral_bench.grading import GradingProcessor
from moral_bench.processor import PromptProcessor


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a background job."""

    id: str
    job_type: str  # "run" or "grade"
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    current_step: str | None = None
    total_steps: int | None = None
    current_step_index: int | None = None
    result: dict | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    # Job config
    config: dict = field(default_factory=dict)


class JobManager:
    """Manages background jobs."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, job_type: str, config: dict) -> Job:
        """Create a new job."""
        job_id = str(uuid.uuid4())[:8]
        job = Job(id=job_id, job_type=job_type, config=config)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: JobStatus | None = None,
        progress: float | None = None,
        current_step: str | None = None,
        total_steps: int | None = None,
        current_step_index: int | None = None,
        result: dict | None = None,
        error: str | None = None,
    ):
        """Update job status."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                if status is not None:
                    job.status = status
                    if status == JobStatus.RUNNING and job.started_at is None:
                        job.started_at = datetime.now()
                    elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                        job.completed_at = datetime.now()
                if progress is not None:
                    job.progress = progress
                if current_step is not None:
                    job.current_step = current_step
                if total_steps is not None:
                    job.total_steps = total_steps
                if current_step_index is not None:
                    job.current_step_index = current_step_index
                if result is not None:
                    job.result = result
                if error is not None:
                    job.error = error

    def cancel_job(self, job_id: str) -> bool:
        """Mark job as cancelled."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return True
            return False

    def list_jobs(self) -> list[Job]:
        """List all jobs."""
        with self._lock:
            return list(self._jobs.values())


# Global job manager instance
job_manager = JobManager()


class ExecutionService:
    """Service for executing inference and grading jobs."""

    def __init__(self, project_root: Path, results_base: Path):
        self.project_root = project_root
        self.results_base = results_base

    def start_inference_job(
        self,
        models: list[str],
        prompts_file: Path,
        output_dir: Path | None = None,
    ) -> Job:
        """Start an inference job in the background."""
        config = {
            "models": models,
            "prompts_file": str(prompts_file),
            "output_dir": str(output_dir) if output_dir else None,
        }
        job = job_manager.create_job("run", config)

        # Start background thread
        thread = threading.Thread(
            target=self._run_inference,
            args=(job.id, models, prompts_file, output_dir),
            daemon=True,
        )
        thread.start()

        return job

    def start_grading_job(
        self,
        files: list[Path],
        grader_ids: list[str],
        grader_model: str,
        output_dir: Path | None = None,
        custom_prompt: str | None = None,
    ) -> Job:
        """Start a grading job in the background."""
        config = {
            "files": [str(f) for f in files],
            "grader_ids": grader_ids,
            "grader_model": grader_model,
            "output_dir": str(output_dir) if output_dir else None,
            "custom_prompt": custom_prompt,
        }
        job = job_manager.create_job("grade", config)

        # Start background thread
        thread = threading.Thread(
            target=self._run_grading,
            args=(job.id, files, grader_ids, grader_model, output_dir, custom_prompt),
            daemon=True,
        )
        thread.start()

        return job

    def _run_inference(
        self,
        job_id: str,
        models: list[str],
        prompts_file: Path,
        output_dir: Path | None,
    ):
        """Run inference in background thread."""
        try:
            job_manager.update_job(job_id, status=JobStatus.RUNNING)

            config = Config.from_env()
            total_models = len(models)

            results = []
            for i, model in enumerate(models):
                job = job_manager.get_job(job_id)
                if job and job.status == JobStatus.CANCELLED:
                    return

                job_manager.update_job(
                    job_id,
                    current_step=f"Processing {model}",
                    current_step_index=i,
                    total_steps=total_models,
                    progress=(i / total_models),
                )

                with OpenRouterClient(config) as client:
                    processor = PromptProcessor(client)
                    result = processor.process_prompts(
                        prompts_file,
                        output_dir or (self.results_base / prompts_file.stem / "responses"),
                        model=model,
                    )
                    results.append({"model": model, "output_file": str(result)})

            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=1.0,
                current_step="Completed",
                result={"outputs": results},
            )

        except Exception as e:
            job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=str(e),
            )

    def _run_grading(
        self,
        job_id: str,
        files: list[Path],
        grader_ids: list[str],
        grader_model: str,
        output_dir: Path | None,
        custom_prompt: str | None,
    ):
        """Run grading in background thread."""
        try:
            job_manager.update_job(job_id, status=JobStatus.RUNNING)

            config = Config.from_env()
            total_files = len(files)

            results = []
            for i, file_path in enumerate(files):
                job = job_manager.get_job(job_id)
                if job and job.status == JobStatus.CANCELLED:
                    return

                job_manager.update_job(
                    job_id,
                    current_step=f"Grading {file_path.name}",
                    current_step_index=i,
                    total_steps=total_files,
                    progress=(i / total_files),
                )

                with OpenRouterClient(config) as client:
                    processor = GradingProcessor(client=client)

                    # Determine output directory
                    if output_dir:
                        out_dir = output_dir
                    else:
                        # Derive from input file path
                        parts = file_path.parts
                        if "results" in parts:
                            results_idx = parts.index("results")
                            if len(parts) > results_idx + 1:
                                version = parts[results_idx + 1]
                                out_dir = self.results_base / version / "grades"
                            else:
                                out_dir = self.results_base / "grades"
                        else:
                            out_dir = self.results_base / "grades"

                    result = processor.grade_responses(
                        file_path,
                        out_dir,
                        grader_ids,
                        grader_model=grader_model,
                        custom_prompt=custom_prompt,
                    )
                    results.append({"input_file": str(file_path), "output_file": str(result)})

            job_manager.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=1.0,
                current_step="Completed",
                result={"outputs": results},
            )

        except Exception as e:
            job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                error=str(e),
            )
