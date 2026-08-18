"""Routes for grader prompts - single source of truth shared with frontend."""

from fastapi import APIRouter
from pydantic import BaseModel

from aestheticbench.benchmark.prompts import (
    GRADER_FACTUAL_DEPTH_PROMPT,
    GRADER_JUSTIFICATION_PROMPT,
    GRADER_PREFERENCE_PROMPT_1,
    GRADER_PREFERENCE_PROMPT_2,
    GRADER_RELATIVISM_PROMPT,
    GRADER_WHIMSICAL_PROMPT,
)

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
    return GraderPromptsResponse(
        prompts=[
            GraderPrompt(
                id="preference1",
                title="Preference 1 (-1, 0, 1)",
                prompt=GRADER_PREFERENCE_PROMPT_1,
            ),
            GraderPrompt(
                id="preference2",
                title="Preference 2 (continuous -1 to 1)",
                prompt=GRADER_PREFERENCE_PROMPT_2,
            ),
            GraderPrompt(
                id="justification",
                title="Justification (1 to 5) [requires preference1]",
                prompt=GRADER_JUSTIFICATION_PROMPT,
            ),
            GraderPrompt(
                id="relativism",
                title="Relativism (0 or 1)",
                prompt=GRADER_RELATIVISM_PROMPT,
            ),
            GraderPrompt(
                id="whimsical",
                title="Whimsical Reasoning (1 to 5)",
                prompt=GRADER_WHIMSICAL_PROMPT,
            ),
            GraderPrompt(
                id="factual_depth",
                title="Factual Depth (1 to 5)",
                prompt=GRADER_FACTUAL_DEPTH_PROMPT,
            ),
        ]
    )
