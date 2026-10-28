"""Помощник для интеграционных тестов: ведёт партию через REST и WebSocket, как настоящие клиенты."""
from contextlib import ExitStack

from app.engine import dice_provider
from app.engine.dice import DiceRoller


class Game:
    def __init__(self, client, players=("Анна", "Борис"), heroes=("astrid", "eirik"), story="ship_without_crew"):
        self.client = client
        r = client.post("/api/sessions", json={"name": "Тестовая сага", "story_id": story, "player_count": len(players)})
        assert r.status_code == 200, r.text
        data = r.json()
        self.code, self.table_token = data["join_code"], data["table_token"]
        self.tokens: dict[str, str] = {}
        for name, hero in zip(players, heroes):
            tok = client.post(f"/api/sessions/{self.code}/join", json={"player_name": name}).json()["device_token"]
            assert client.post(f"/api/sessions/{self.code}/claim", json={"hero_id": hero, "device_token": tok}).status_code == 200
            self.tokens[hero] = tok
        self.stack = ExitStack()
        self.hands: dict[str, object] = {}
        self.table = None

    def swear_and_ready(self):
        for tok in self.tokens.values():
            assert self.client.post(f"/api/sessions/{self.code}/oath", json={"device_token": tok}).status_code == 200
            assert self.client.post(f"/api/sessions/{self.code}/ready", json={"device_token": tok, "is_ready": True}).status_code == 200

    def start(self):
        self.swear_and_ready()
        return self.client.post(f"/api/sessions/{self.code}/start", headers={"X-Table-Token": self.table_token})

    def connect(self, hero):
        ws = self.stack.enter_context(self.client.websocket_connect(f"/ws/hand/{self.code}?token={self.tokens[hero]}"))
        self.hands[hero] = ws
        return ws

    def connect_table(self):
        self.table = self.stack.enter_context(self.client.websocket_connect(f"/ws/table/{self.code}?token={self.table_token}"))
        return self.table

    def send(self, hero, type_, **payload):
        self.hands[hero].send_json({"type": type_, "payload": payload})

    def drain(self, ws, until=None, limit=60):
        """Читает сообщения до нужного типа (или пока не получено limit)."""
        seen = []
        for _ in range(limit):
            msg = ws.receive_json()
            seen.append(msg)
            if until and msg["type"] == until:
                break
        return seen

    def hand_state(self, hero):
        return self.client.get(f"/api/hand/{self.code}", params={"device_token": self.tokens[hero]}).json()

    def table_state(self):
        return self.client.get(f"/api/table/{self.code}", headers={"X-Table-Token": self.table_token}).json()

    def table_map(self):
        return self.client.get(f"/api/maps/{self.code}/table", headers={"X-Table-Token": self.table_token}).json()

    def hand_map(self, hero):
        return self.client.get(f"/api/maps/{self.code}/hand", params={"device_token": self.tokens[hero]}).json()

    def say(self, hero, text_):
        """Отправить текст, получить карточку, подтвердить."""
        self.send(hero, "action.submit_text", raw_text=text_)
        msgs = self.drain(self.hands[hero], until="action.recognized")
        card_msg = next(m for m in msgs if m["type"] == "action.recognized")
        return card_msg["payload"]

    def confirm(self, hero, action_id):
        self.send(hero, "action.confirm", action_id=action_id)
        self.hands[hero].receive_json()

    def dice(self, *values):
        dice_provider.set_roller(DiceRoller(preset=list(values)))

    def close(self):
        import time
        from app.ws.hub import hub
        self.stack.close()
        for _ in range(100):  # дожидаемся, пока сервер доработает обработчики отключения
            if not hub.hands and not hub.tables.get(self.client.get(f"/api/sessions/{self.code}").json().get("code"), []) and hub.busy == 0:
                break
            time.sleep(0.05)
        time.sleep(0.1)


def until(ws, type_, limit=120):
    """Читает сообщения сокета, пока не встретится нужный тип."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == type_:
            return msg
    raise AssertionError(f"не пришло сообщение {type_}")


def collect_until(ws, type_, limit=200):
    """Возвращает все сообщения до нужного типа включительно."""
    seen = []
    for _ in range(limit):
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == type_:
            return seen
    raise AssertionError(f"не пришло сообщение {type_}")


def wait_disconnected(game, hero, tries=60):
    import time
    from app.ws.hub import hub
    sid = game.client.get(f"/api/sessions/{game.code}").json()
    for _ in range(tries):
        if not any(c.hero_id == hero for c in hub.hands.values()):
            return
        time.sleep(0.05)
    raise AssertionError("отключение не обработано")


def until_state(ws, predicate, limit=200):
    """Читает hero.state, пока состояние не удовлетворит условию (старые состояния в очереди пропускаются)."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == "hero.state" and predicate(msg["payload"]):
            return msg["payload"]
    raise AssertionError("нужное состояние не пришло")


def until_text(ws, fragment, limit=200):
    """Ждёт feed.message или narration.public, текст которого содержит фрагмент."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] in ("feed.message", "narration.public") and fragment in msg["payload"].get("text", ""):
            return msg["payload"]
    raise AssertionError(f"не пришло сообщение с текстом «{fragment}»")
