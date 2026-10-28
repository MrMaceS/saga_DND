from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Any

SessionStatus = Literal["lobby", "hero_select", "oath", "playing", "paused", "finished"]

class SessionCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=60)
    story_id: str
    player_count: int = Field(..., ge=2, le=10)


class SessionResponse(BaseModel):
    session_id: str
    join_code: str
    table_token: str


class JoinRequest(BaseModel):
    player_name: str


class JoinResponse(BaseModel):
    device_token: str


class ClaimRequest(BaseModel):
    hero_id: str
    device_token: str


class ReadyRequest(BaseModel):
    device_token: str
    is_ready: bool


class HeroPublic(BaseModel):
    id: str
    name: str
    title: str
    archetype: str
    stats: dict[str, int]
    endurance: int
    gift_name: str
    action_ability_name: str

    model_config = ConfigDict(from_attributes=True)


# Действия Руки → Сервер
class ActionSubmitText(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=500)


class MoveStep(BaseModel):
    target_zone: str


class WhisperSend(BaseModel):
    target_hero: str
    content: str = Field(..., min_length=1, max_length=500)


class ShoutSend(BaseModel):
    target_hero: str
    content: str = Field(..., min_length=1, max_length=500)


class TurnEnd(BaseModel):
    pass


class TurnUnend(BaseModel):
    pass


class CombatChoose(BaseModel):
    """Выбор действия в бою."""
    category: Literal["attack", "terrain", "ability", "cover_ally"]
    variant: str  # Например: "strike", "push", "height", "fire"
    target_hero: str | None = None  # Для "cover_ally"
    target_enemy: str | None = None # ID врага или "nearest"
    terrain_id: str | None = None   # ID объекта местности, если выбран


class ReactionChoose(BaseModel):
    """Выбор реакции на удар врага."""
    choice: Literal["defend", "counter"]


class InterrogateChoose(BaseModel):
    """Выбор метода допроса."""
    method: Literal["persuade", "bribe", "intimidate", "deceive", "torture", "deal"]
    target_npc: str


class CaptiveFate(BaseModel):
    """Судьба допрошенного пленного."""
    fate: Literal["free", "keep", "kill"]
    target_npc: str


class SaveMetadata(BaseModel):
    id: int
    kind: str  # 'auto', 'evening', 'manual', 'crash'
    slot_no: int | None
    label: str
    chapter: str | None
    round_no: int | None
    save_version: int
    created_at: str


class SaveExportResponse(BaseModel):
    filename: str
    data: dict[str, Any]


class SaveImportRequest(BaseModel):
    data: dict[str, Any]