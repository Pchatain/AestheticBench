"""Serve every grader's prompt text to the UI's Prompts page.

Read straight from prompts/graders/ via the same loader the graders use, so
what the page shows is what the judge is sent. Current generation first.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from aestheticbench.benchmark.prompts import load_grader_prompt
from aestheticbench.benchmark.rubric import CURRENT_GRADER_IDS, LEGACY_GRADER_IDS, SPECS

router = APIRouter(tags=["prompts"])


class GraderPrompt(BaseModel):
    id: str
    title: str
    prompt: str


class GraderPromptsResponse(BaseModel):
    prompts: list[GraderPrompt]


@router.get("/grader-prompts", response_model=GraderPromptsResponse)
def get_grader_prompts() -> GraderPromptsResponse:
    """Return all grader prompts for display in the UI."""
    prompts = []
    for grader_id in CURRENT_GRADER_IDS + LEGACY_GRADER_IDS:
        spec = SPECS[grader_id]
        prompts.append(
            GraderPrompt(
                id=grader_id,
                title=f"{grader_id} — {spec.name} · {spec.score_hint}",
                prompt=load_grader_prompt(grader_id),
            )
        )
    return GraderPromptsResponse(prompts=prompts)
