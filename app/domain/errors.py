ERROR_CODES = {
    "session_full": "Сессия заполнена",
    "hero_taken": "Этот герой уже выбран другим игроком",
    "lobby_closed": "Лобби закрыто, подключение невозможно",
    "invalid_state": "Недопустимое состояние сессии для этого действия",
    "not_your_turn": "Сейчас не ваш ход",
    "forbidden": "Доступ запрещён",
    "unauthorized": "Неверный токен",
    "invalid_phase": "Действие недоступно в текущей фазе раунда",
    "invalid_save_version": "Версия сохранения не поддерживается",
    "session_not_found": "Сессия не найдена",
    "story_unavailable": "Эта история пока недоступна",
    "unknown_hero": "Такого героя нет",
    "not_ready": "Не все игроки готовы к началу",
    "invalid_name": "Некорректное имя",
    "not_found": "Не найдено",
    "action_unavailable": "Это действие пока недоступно",
    "slots_full": "Все слоты ручного сохранения заняты",
}

STATUS_BY_CODE = {"session_not_found": 404, "not_found": 404, "unauthorized": 401, "forbidden": 403}


class SagaError(Exception):
    def __init__(self, code: str, detail: str | None = None):
        self.code = code
        self.detail = detail or ERROR_CODES.get(code, "Неизвестная ошибка")
        super().__init__(f"{code}: {self.detail}")

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE.get(self.code, 400)
