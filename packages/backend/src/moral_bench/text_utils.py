"""Text utilities for MoralBench prompt processing."""

import re

_ENTITY_PATTERN = re.compile(r"\[([^\]]*)\]")


def strip_entity_brackets(text: str) -> str:
    """Remove entity annotation brackets from question text.

    Questions in the prompts TSV use [brackets] to mark entities,
    e.g. "Who is greater, [Beethoven] or [Lizzo]?"
    This strips them before sending to models.
    """
    return _ENTITY_PATTERN.sub(r"\1", text)


def swap_entities(text: str) -> str:
    """Swap the two [bracketed] entities in a question.

    E.g. "Who is greater, [Beethoven] or [Lizzo]?"
      -> "Who is greater, [Lizzo] or [Beethoven]?"

    If the text doesn't contain exactly 2 bracketed entities,
    returns it unchanged.
    """
    entities = _ENTITY_PATTERN.findall(text)
    if len(entities) != 2:
        return text

    spans = list(_ENTITY_PATTERN.finditer(text))
    first, second = spans[0], spans[1]

    return (
        text[: first.start()]
        + f"[{entities[1]}]"
        + text[first.end() : second.start()]
        + f"[{entities[0]}]"
        + text[second.end() :]
    )
