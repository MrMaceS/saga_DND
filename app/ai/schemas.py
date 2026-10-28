from typing import Literal
from pydantic import BaseModel, Field


class InterpreterSideAction(BaseModel):
    """Побочное действие (шёпот или окрик)."""
    type: Literal["shout", "whisper"]
    target_hero: str
    content: str


class InterpreterResponse(BaseModel):
    """Ответ интерпретатора действий."""
    hero_id: str
    action_type: Literal[
        "investigate", "sneak", "talk", "use_ability", "use_item", "give_item",
        "build", "ritual", "heal", "rescue", "move", "wait", "propose",
        "combat", "custom"
    ]
    target_zone: str | None = None
    target_task: str | None = None
    target_hero: str | None = None
    target_item: str | None = None
    intent: str
    required_stat: Literal["strength", "agility", "wits", "spirit"]
    base: Literal["easy", "normal", "hard"]
    difficulty_tags: list[str] = Field(default_factory=list)
    resources_required: list[str] = Field(default_factory=list)
    uses_ability: str | None = None
    trigger_condition: str | None = None
    requires_move_to: str | None = None
    side_action: InterpreterSideAction | None = None
    free_actions: list[str] = Field(default_factory=list)
    needs_consent_from: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarifying_question: str | None = None
    is_possible: bool = True
    rejection_reason: str | None = None
    alternative: str | None = None


class NarratorResponse(BaseModel):
    """Ответ диктора."""
    public: str
    private: dict[str, str] = Field(default_factory=dict)