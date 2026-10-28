-- Сага Мьёльнира: схема SQLite для MVP
-- Принципы: сервер хранит правду; клиент получает только то, что знает его герой.

PRAGMA foreign_keys = ON;

-- ---------- Каталог (заполняется из heroes.json) ----------
CREATE TABLE IF NOT EXISTS hero_template (
  id TEXT PRIMARY KEY,            -- 'astrid'
  data_json TEXT NOT NULL         -- весь объект героя из heroes.json
);

-- ---------- Сессия ----------
CREATE TABLE IF NOT EXISTS game_session (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL CHECK (length(name) BETWEEN 3 AND 60),
  story_id TEXT NOT NULL,
  join_code TEXT NOT NULL UNIQUE,
  table_token TEXT,
  player_count INTEGER NOT NULL DEFAULT 2,
  round_phase TEXT NOT NULL DEFAULT 'declaring',
  status TEXT NOT NULL CHECK (status IN ('lobby','hero_select','oath','playing','paused','finished')),
  evening_no INTEGER NOT NULL DEFAULT 1,
  chapter TEXT,
  round_no INTEGER NOT NULL DEFAULT 0,
  scene_no INTEGER NOT NULL DEFAULT 1,
  settings_json TEXT NOT NULL,    -- reader_mode, cruelty, ambience
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Игроки и герои (хост = обычный игрок) ----------
CREATE TABLE IF NOT EXISTS player_binding (
  session_id TEXT NOT NULL REFERENCES game_session(id),
  hero_id TEXT REFERENCES hero_template(id),
  player_name TEXT NOT NULL,
  device_token TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK (status IN ('active','away','ai')),
  turn_status TEXT NOT NULL DEFAULT 'idle'
    CHECK (turn_status IN ('idle','thinking','action_chosen','turn_ended',
                           'proposing','awaiting_confirmation','in_group_action',
                           'downed','unconscious')),
  is_reader INTEGER NOT NULL DEFAULT 0,
  sworn_oath INTEGER NOT NULL DEFAULT 0,
  ready INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, hero_id)
);

CREATE TABLE IF NOT EXISTS hero_state (
  session_id TEXT NOT NULL,
  hero_id TEXT NOT NULL,
  stats_json TEXT NOT NULL,       -- с учётом роста
  endurance INTEGER NOT NULL,     -- число ячеек
  fate INTEGER NOT NULL DEFAULT 1,
  location_id TEXT,
  zone_id TEXT,
  abilities_json TEXT NOT NULL,   -- {minor_ready: true, growth: [...]}
  inventory_json TEXT NOT NULL,   -- слоты, предметы
  secrets_json TEXT NOT NULL,     -- {story: sealed|known, personal: sealed|known}
  goal_progress INTEGER NOT NULL DEFAULT 0,
  pending_zone TEXT,
  dying_clock INTEGER,            -- NULL, пока не при смерти
  PRIMARY KEY (session_id, hero_id)
);

CREATE TABLE IF NOT EXISTS injury (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  hero_id TEXT NOT NULL,
  body_part TEXT NOT NULL CHECK (body_part IN ('head','torso','arm','leg')),
  side TEXT CHECK (side IN ('left','right')),
  severity TEXT NOT NULL CHECK (severity IN ('light','medium','heavy')),
  cells INTEGER NOT NULL,         -- 1 или 2
  bleeding_clock INTEGER,         -- для тяжёлого ранения торса
  round_no INTEGER NOT NULL
);

-- ---------- Мир ----------
CREATE TABLE IF NOT EXISTS location (
  session_id TEXT NOT NULL,
  id TEXT NOT NULL,               -- 'ship', 'dock', 'longhouse'
  discovered INTEGER NOT NULL DEFAULT 0,     -- видна на общей карте
  visited_by_any INTEGER NOT NULL DEFAULT 0,
  known_status_round INTEGER,     -- «известно на раунд N»
  PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS task (
  session_id TEXT NOT NULL,
  id TEXT NOT NULL,               -- 'check_hold', 'hold_ship', 'scout_shore'
  location_id TEXT NOT NULL,
  zone_id TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open','resolved','escalated')),
  world_truth_json TEXT NOT NULL, -- что есть на самом деле (три уровня раскрытия)
  consequence_if_ignored TEXT NOT NULL,
  public_level INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS clock (
  session_id TEXT NOT NULL,
  id TEXT NOT NULL,               -- 'anchor', 'shore_shadows', 'third_strike'
  location_id TEXT,
  segments INTEGER NOT NULL,
  filled INTEGER NOT NULL DEFAULT 0,
  resolved INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS settlement (
  session_id TEXT PRIMARY KEY,
  food INTEGER, wood INTEGER, iron INTEGER, gold INTEGER,
  faith INTEGER, safety INTEGER, morale INTEGER
);

CREATE TABLE IF NOT EXISTS building (
  session_id TEXT NOT NULL,
  type TEXT NOT NULL,             -- 'longhouse', 'forge', 'dock'
  level INTEGER NOT NULL DEFAULT 0,
  condition TEXT,
  PRIMARY KEY (session_id, type)
);

CREATE TABLE IF NOT EXISTS npc (
  session_id TEXT NOT NULL,
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  attitude TEXT NOT NULL DEFAULT 'neutral'
    CHECK (attitude IN ('hostile','wary','neutral','friendly')),  -- отношения только к отряду
  state_json TEXT,
  PRIMARY KEY (session_id, id)
);

-- ---------- Знания (фильтрация на сервере) ----------
CREATE TABLE IF NOT EXISTS fact (
  session_id TEXT NOT NULL,
  id TEXT NOT NULL,
  text TEXT NOT NULL,
  level INTEGER NOT NULL CHECK (level BETWEEN 1 AND 3),
  source TEXT NOT NULL,           -- own_action | whisper | ally | shout | narrator
  round_no INTEGER NOT NULL,
  PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS fact_known_by (      -- телефон получает факты только по этой таблице
  session_id TEXT NOT NULL,
  fact_id TEXT NOT NULL,
  hero_id TEXT NOT NULL,
  PRIMARY KEY (session_id, fact_id, hero_id)
);

CREATE TABLE IF NOT EXISTS player_note (
  session_id TEXT NOT NULL,
  hero_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('private_scene','my_notes')),
  text TEXT NOT NULL,
  round_no INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Ход, кубики, события ----------
CREATE TABLE IF NOT EXISTS action (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  round_no INTEGER NOT NULL,
  hero_id TEXT NOT NULL,
  raw_text TEXT,
  parsed_json TEXT,               -- ответ Gemini после валидации
  status TEXT NOT NULL CHECK (status IN ('draft','confirmed','resolved','rejected')),
  group_id TEXT                   -- совместное действие
);

CREATE TABLE IF NOT EXISTS dice_roll (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  round_no INTEGER NOT NULL,
  hero_id TEXT NOT NULL,
  kind TEXT NOT NULL,             -- check | defense | heal | shout | ally
  stat TEXT, natural INTEGER NOT NULL, modifier INTEGER NOT NULL,
  difficulty INTEGER NOT NULL, outcome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_event (        -- журнал событий (Event Log)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  round_no INTEGER,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  public_text TEXT,               -- то, что может прочитать Чтец
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saga_book (          -- память диктора между вечерами
  session_id TEXT NOT NULL,
  evening_no INTEGER NOT NULL,
  entry TEXT NOT NULL,
  consequence_json TEXT
);

-- ---------- Сохранения ----------
CREATE TABLE IF NOT EXISTS save_slot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('auto','evening','manual','crash')),
  slot_no INTEGER,                -- 1..3 для manual
  label TEXT NOT NULL,            -- авто: «Глава, раунд, дата»
  chapter TEXT, round_no INTEGER,
  save_version INTEGER NOT NULL DEFAULT 1,
  snapshot_json TEXT NOT NULL,
  event_log_cursor INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------- Добавлено при аудите MVP ----------
CREATE TABLE IF NOT EXISTS zone_state (
  session_id TEXT NOT NULL,
  zone_id TEXT NOT NULL,
  visited INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, zone_id)
);

CREATE TABLE IF NOT EXISTS hero_zone_visit (
  session_id TEXT NOT NULL,
  hero_id TEXT NOT NULL,
  zone_id TEXT NOT NULL,
  PRIMARY KEY (session_id, hero_id, zone_id)
);

CREATE TABLE IF NOT EXISTS ws_event (          -- журнал рассылки: seq = id, нужен для переподключения
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  audience TEXT NOT NULL,                      -- table | hero:<id> | all
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ws_event_session ON ws_event(session_id, id);

CREATE TABLE IF NOT EXISTS setting_vote (       -- голосования за настройки вечера
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  proposer TEXT NOT NULL,
  votes_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'open'          -- open | passed | rejected
);

