from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from engine import rules


class RoundPhase(str, Enum):
    DECLARING = "declaring"
    RESOLVING = "resolving"
    NARRATING = "narrating"
    SAVED = "saved"


@dataclass
class ActionDraft:
    """Заявка действия от игрока."""
    hero_id: str
    raw_text: str | None = None
    parsed: dict[str, Any] | None = None
    confirmed: bool = False


@dataclass
class RoundState:
    """Состояние одного раунда."""
    round_no: int
    phase: RoundPhase = RoundPhase.DECLARING
    actions: dict[str, ActionDraft] = field(default_factory=dict)  # hero_id -> draft
    turn_status: dict[str, str] = field(default_factory=dict)      # hero_id -> status
    results: list[dict[str, Any]] = field(default_factory=list)

    def can_save(self) -> bool:
        """Сохранение запрещено в resolving и narrating."""
        return self.phase in (RoundPhase.DECLARING, RoundPhase.SAVED)

    def submit_action(self, hero_id: str, draft: ActionDraft) -> None:
        if self.phase != RoundPhase.DECLARING:
            raise RuntimeError("нельзя подавать действия вне declaring")
        self.actions[hero_id] = draft
        self.turn_status[hero_id] = "action_chosen"

    def cancel_action(self, hero_id: str) -> None:
        if self.phase != RoundPhase.DECLARING:
            raise RuntimeError("нельзя отменить вне declaring")
        if hero_id in self.actions:
            del self.actions[hero_id]
        self.turn_status[hero_id] = "thinking"

    def end_turn(self, hero_id: str) -> None:
        if self.phase != RoundPhase.DECLARING:
            raise RuntimeError("нельзя закончить ход вне declaring")
        self.turn_status[hero_id] = "turn_ended"

    def unend_turn(self, hero_id: str) -> None:
        if self.phase != RoundPhase.DECLARING:
            raise RuntimeError("нельзя отменить готовность вне declaring")
        if self.turn_status.get(hero_id) == "turn_ended":
            self.turn_status[hero_id] = "action_chosen" if hero_id in self.actions else "thinking"

    def is_all_ready(self) -> bool:
        """Проверяет, готовы ли все (с учётом AUTO_READY_STATUSES)."""
        return rules.all_ready(self.turn_status)

    def transition_to_resolving(self) -> None:
        if self.phase != RoundPhase.DECLARING:
            raise RuntimeError("переход в resolving возможен только из declaring")
        if not self.is_all_ready():
            raise RuntimeError("не все игроки готовы")
        self.phase = RoundPhase.RESOLVING

    def transition_to_narrating(self) -> None:
        if self.phase != RoundPhase.RESOLVING:
            raise RuntimeError("переход в narrating возможен только из resolving")
        self.phase = RoundPhase.NARRATING

    def transition_to_saved(self) -> None:
        if self.phase != RoundPhase.NARRATING:
            raise RuntimeError("переход в saved возможен только из narrating")
        self.phase = RoundPhase.SAVED


class RoundManager:
    """Управляет последовательностью раундов."""

    def __init__(self) -> None:
        self._current: RoundState | None = None
        self._history: list[RoundState] = []

    @property
    def current(self) -> RoundState | None:
        return self._current

    def start_round(self, turn_status: dict[str, str]) -> RoundState:
        round_no = (self._history[-1].round_no + 1) if self._history else 1
        self._current = RoundState(
            round_no=round_no,
            phase=RoundPhase.DECLARING,
            turn_status=dict(turn_status),
        )
        return self._current

    def finish_round(self) -> RoundState:
        if self._current is None:
            raise RuntimeError("нет текущего раунда")
        if self._current.phase != RoundPhase.SAVED:
            raise RuntimeError("раунд не завершён")
        self._history.append(self._current)
        finished = self._current
        self._current = None
        return finished