"""Тесты базовых правил. Идентификаторы R-xx соответствуют docs/TEST_PLAN.md."""
import inspect
import itertools

import pytest

from engine import rules as r
from engine.rules import (BodyPart, Outcome, Severity, Wound)

ADJ = {
    "deck": ["pier", "hold", "mast", "cabin"], "hold": ["deck"], "mast": ["deck"],
    "cabin": ["deck"], "pier": ["deck", "rocks"], "rocks": ["pier", "trail"],
    "trail": ["rocks"], "island": [],
}


# ------------------------------------------------ R-01 таблица исходов
@pytest.mark.parametrize("natural,mod,dc,expected", [
    (1, 10, 5, Outcome.CRITICAL_FAIL),          # натуральная 1 бьёт любой бонус
    (20, -5, 25, Outcome.GREAT_SUCCESS),        # натуральная 20 всегда большой успех
    (10, 3, 13, Outcome.MINIMAL_SUCCESS),       # ровно
    (10, 3, 11, Outcome.MINIMAL_SUCCESS),       # +2
    (10, 3, 10, Outcome.SUCCESS),               # +3
    (10, 3, 6, Outcome.SUCCESS),                # +7
    (10, 3, 5, Outcome.GREAT_SUCCESS),          # +8
    (10, 3, 14, Outcome.FAIL),                  # -1
    (10, 3, 17, Outcome.FAIL),                  # -4
    (10, 3, 18, Outcome.FAIL_WITH_CONSEQUENCE),  # -5
])
def test_roll_outcome_table(natural, mod, dc, expected):
    assert r.roll_outcome(natural, mod, dc) == expected


@pytest.mark.parametrize("bad", [0, 21, -3])
def test_roll_outcome_rejects_invalid_d20(bad):
    with pytest.raises(ValueError):
        r.roll_outcome(bad, 0, 10)


def test_outcome_is_monotonic_in_modifier():
    order = list(Outcome)
    rank = {o: i for i, o in enumerate(
        [Outcome.CRITICAL_FAIL, Outcome.FAIL_WITH_CONSEQUENCE, Outcome.FAIL,
         Outcome.MINIMAL_SUCCESS, Outcome.SUCCESS, Outcome.GREAT_SUCCESS])}
    for natural in range(2, 20):
        prev = -1
        for mod in range(-10, 15):
            cur = rank[r.roll_outcome(natural, mod, 12)]
            assert cur >= prev
            prev = cur
    assert len(order) == 6


# ------------------------------------------------ R-02 сложность
def test_difficulty_examples():
    assert r.compute_difficulty("normal", []) == 11
    assert r.compute_difficulty("normal", ["dark", "prepared"]) == 11
    assert r.compute_difficulty("hard", ["dark", "no_light", "fog"]) == 17
    assert r.compute_difficulty("easy", ["prepared", "careful", "with_partner"]) == 6
    assert r.compute_difficulty("normal", ["dark", "dark"]) == 12  # дубли не суммируются


def test_difficulty_never_depends_on_player_count():
    params = inspect.signature(r.compute_difficulty).parameters
    assert not any("player" in p for p in params)


def test_difficulty_stays_in_bounds_for_all_combinations():
    tags = list(r.TAG_MODS)
    for base in r.BASE_DC:
        for n in range(len(tags) + 1):
            for combo in itertools.combinations(tags, n):
                assert r.DC_MIN <= r.compute_difficulty(base, combo) <= r.DC_MAX


def test_difficulty_rejects_unknown_input():
    with pytest.raises(ValueError):
        r.compute_difficulty("impossible", [])
    with pytest.raises(ValueError):
        r.compute_difficulty("normal", ["shiny"])


# ------------------------------------------------ R-03 раны
@pytest.mark.parametrize("shortfall,natural,expected", [
    (1, 10, Severity.LIGHT), (4, 10, Severity.LIGHT),
    (5, 10, Severity.MEDIUM), (9, 10, Severity.MEDIUM),
    (10, 10, Severity.HEAVY), (25, 10, Severity.HEAVY),
    (0, 10, None), (-3, 10, None),
    (3, 1, Severity.HEAVY),                       # натуральная 1 всегда тяжёлое
])
def test_severity_from_shortfall(shortfall, natural, expected):
    assert r.severity_from_shortfall(shortfall, natural) == expected


@pytest.mark.parametrize("sev,part,expected", [
    (Severity.LIGHT, BodyPart.HEAD, Severity.MEDIUM),
    (Severity.MEDIUM, BodyPart.TORSO, Severity.HEAVY),
    (Severity.HEAVY, BodyPart.HEAD, Severity.HEAVY),     # потолок
    (Severity.LIGHT, BodyPart.ARM, Severity.LIGHT),
    (Severity.HEAVY, BodyPart.LEG, Severity.HEAVY),
])
def test_body_part_adjustment(sev, part, expected):
    assert r.adjust_for_body_part(sev, part) == expected


def test_body_part_from_d6_covers_all_faces():
    mapping = [r.body_part_from_d6(i) for i in range(1, 7)]
    assert mapping == [BodyPart.HEAD, BodyPart.TORSO, BodyPart.TORSO,
                       BodyPart.ARM, BodyPart.ARM, BodyPart.LEG]
    for bad in (0, 7):
        with pytest.raises(ValueError):
            r.body_part_from_d6(bad)


def test_wound_cells_and_penalty():
    assert Wound(Severity.LIGHT, BodyPart.ARM).cells == 1
    assert Wound(Severity.MEDIUM, BodyPart.ARM).cells == 1
    assert Wound(Severity.HEAVY, BodyPart.ARM).cells == 2
    assert [Wound(s, BodyPart.LEG).penalty for s in Severity] == [-1, -2, -3]


def test_total_penalty_is_capped():
    heavy = Wound(Severity.HEAVY, BodyPart.TORSO)
    medium = Wound(Severity.MEDIUM, BodyPart.ARM)
    assert r.total_wound_penalty([]) == 0
    assert r.total_wound_penalty([Wound(Severity.LIGHT, BodyPart.ARM)]) == -1
    assert r.total_wound_penalty([heavy, heavy, medium]) == -5


def test_downed_when_all_cells_filled():
    wounds = [Wound(Severity.HEAVY, BodyPart.TORSO), Wound(Severity.MEDIUM, BodyPart.ARM)]
    assert r.cells_used(wounds) == 3
    assert r.is_downed(3, 3) is True
    assert r.is_downed(2, 3) is False
    assert r.is_downed(0, 5) is False      # на старте все здоровы


# ------------------------------------------------ R-04 защита и контратака
def test_defend_parries_example_from_design():
    res = r.resolve_defend(natural=8, stat=4, wound_mod=0, level=12, d6=1)
    assert res.parried and res.wound is None      # 8+4+2 = 14 >= 12


def test_defend_position_bonus_turns_fail_into_parry():
    assert not r.resolve_defend(5, 3, 0, 12, d6=4).parried   # 10 < 12
    assert r.resolve_defend(5, 3, 0, 12, d6=4, position_bonus=2).parried  # 12


def test_defend_failure_gives_wound_by_shortfall_and_part():
    res = r.resolve_defend(natural=2, stat=1, wound_mod=0, level=14, d6=4)  # 5 vs 14, -9
    assert (res.wound.severity, res.wound.body_part, res.wound.cells) == (
        Severity.MEDIUM, BodyPart.ARM, 1)
    head = r.resolve_defend(2, 1, 0, 14, d6=1)
    assert (head.wound.severity, head.wound.cells) == (Severity.HEAVY, 2)


def test_defend_natural_extremes():
    assert r.resolve_defend(20, 0, -5, 30, d6=1).parried            # 20 всегда отбивает
    res = r.resolve_defend(1, 10, 0, 5, d6=4)                        # 1 всегда проваливает
    assert not res.parried and res.wound.severity == Severity.HEAVY


def test_defend_uses_wound_penalty():
    assert r.resolve_defend(9, 3, 0, 14, d6=4).parried               # 9+3+2 = 14
    assert not r.resolve_defend(9, 3, -2, 14, d6=4).parried          # 12 < 14


def test_counter_success_blocks_strike_and_hits_back():
    res = r.resolve_counter(natural=8, stat=4, wound_mod=0, level=12, d6=1)  # ровно 12
    assert res.success and res.enemy_cells_lost == 1 and res.wound is None


def test_counter_great_success_costs_enemy_two_cells():
    assert r.resolve_counter(15, 4, 0, 10, d6=1).enemy_cells_lost == 2   # +9
    assert r.resolve_counter(20, 0, 0, 30, d6=1).enemy_cells_lost == 2


def test_counter_failure_is_one_step_heavier_than_defense():
    # пример из дизайна: 5+4 = 9 против 12, лёгкое ранение становится средним
    res = r.resolve_counter(natural=5, stat=4, wound_mod=0, level=12, d6=4)
    assert not res.success and res.wound.severity == Severity.MEDIUM


def test_counter_failure_caps_at_heavy_and_nat1_is_heavy():
    res = r.resolve_counter(2, 0, 0, 16, d6=4)
    assert res.wound.severity == Severity.HEAVY and res.wound.cells == 2
    res = r.resolve_counter(1, 10, 0, 5, d6=4)
    assert not res.success and res.wound.severity == Severity.HEAVY


def test_defend_is_never_worse_than_counter_for_same_roll():
    # Защита безопаснее: при одинаковом броске и статах раны не тяжелее, чем у контратаки.
    order = [Severity.LIGHT, Severity.MEDIUM, Severity.HEAVY]
    for natural in range(2, 20):
        for level in (10, 12, 14, 16):
            d = r.resolve_defend(natural, 3, 0, level, d6=4)
            c = r.resolve_counter(natural, 3, 0, level, d6=4)
            if not d.parried and c.wound is not None:
                assert order.index(d.wound.severity) <= order.index(c.wound.severity)
            if not d.parried:
                assert not c.success            # если защита провалена, контратака тоже


def test_attack_basics():
    hit = r.resolve_attack(11, 3, 0, 12, bonus=2)                    # терраин: 16 против 12
    assert hit.hit and hit.enemy_cells_lost == 1
    assert r.resolve_attack(20, 0, 0, 30).enemy_cells_lost == 2
    miss = r.resolve_attack(1, 10, 0, 5)
    assert not miss.hit and miss.enemy_counterstrike
    assert not r.resolve_attack(5, 1, 0, 12).enemy_counterstrike


def test_astrid_rage_example():
    res = r.resolve_attack(natural=9, stat=4, wound_mod=0, level=12, bonus=4)
    assert res.hit                                                    # 17 против 12


def test_strike_limit_per_round():
    assert r.strikes_allowed(0) and r.strikes_allowed(2)
    assert not r.strikes_allowed(3)


def test_melee_planning_by_zone_distance():
    assert r.plan_melee(ADJ, "pier", "pier") == "in_zone"
    assert r.plan_melee(ADJ, "deck", "pier") == "needs_move"
    assert r.plan_melee(ADJ, "deck", "rocks") == "impossible"
    assert r.plan_melee(ADJ, "deck", "island") == "impossible"


def test_interrogation_only_for_captives_in_same_zone():
    assert r.interrogation_allowed("captive", "deck", "deck")
    assert not r.interrogation_allowed("free", "deck", "deck")
    assert not r.interrogation_allowed("captive", "hold", "deck")


# ------------------------------------------------ R-05 лечение и «при смерти»
def test_heal_dc_table():
    assert r.heal_dc(Severity.LIGHT, self_heal=True, has_kit=False) == 12
    assert r.heal_dc(Severity.LIGHT, self_heal=True, has_kit=True) == 8
    assert r.heal_dc(Severity.MEDIUM, self_heal=True, has_kit=False) == 16
    assert r.heal_dc(Severity.HEAVY, self_heal=False, has_kit=False) == 16
    assert r.heal_dc(Severity.HEAVY, self_heal=True, has_kit=False) == 20


def test_apply_heal_steps():
    assert r.apply_heal(Severity.MEDIUM, 10, 14, 12) == Severity.LIGHT
    assert r.apply_heal(Severity.LIGHT, 10, 14, 12) is None
    assert r.apply_heal(Severity.HEAVY, 10, 5, 16) == Severity.HEAVY
    assert r.apply_heal(Severity.HEAVY, 10, 18, 16) == Severity.MEDIUM   # тяжёлую самому — только до средней
    assert r.apply_heal(Severity.MEDIUM, 1, 30, 12) == Severity.HEAVY    # натуральная 1 ухудшает
    assert r.apply_heal(Severity.HEAVY, 1, 30, 12) == Severity.HEAVY
    assert r.apply_heal(Severity.HEAVY, 20, 5, 16) == Severity.MEDIUM


def test_dying_clock_runs_three_rounds():
    clock = r.DYING_CLOCK_START
    expired = False
    rounds = 0
    while not expired:
        clock, expired = r.tick_dying(clock)
        rounds += 1
    assert rounds == 3 and clock == 0


def test_rescue_dc_constants():
    assert r.RESCUE_DC["stabilize"] == 10
    assert r.RESCUE_DC["drag"] == 10 and r.RESCUE_DC["drag_armored"] == 12
    assert r.RESCUE_DC["return_from_beyond"] == 14


# ------------------------------------------------ R-06 часы угроз
@pytest.mark.parametrize("filled,segments,stage", [
    (0, 4, "quiet"), (1, 6, "quiet"), (1, 3, "uneasy"), (2, 6, "uneasy"),
    (3, 6, "uneasy"), (2, 3, "near_doom"), (4, 6, "near_doom"), (4, 4, "near_doom"),
])
def test_clock_stage(filled, segments, stage):
    assert r.clock_stage(filled, segments) == stage


def test_clock_view_hides_unknown_threats():
    assert r.clock_view(False, 3, 2, 4) == {"visible": False}   # локация не посещена
    assert r.clock_view(True, 0, 2, 4) == {"visible": False}    # никто ничего не знает


def test_clock_view_hint_has_no_name_and_no_numbers():
    view = r.clock_view(True, 1, 2, 6)
    assert view == {"visible": True, "named": False, "stage": "uneasy"}
    assert "filled" not in view and "segments" not in view


def test_clock_view_scouted_shows_numbers():
    assert r.clock_view(True, 2, 3, 4) == {"visible": True, "named": True, "filled": 3, "segments": 4}
    assert r.clock_view(True, 3, 3, 4)["named"] is True


def test_clocks_do_not_tick_until_location_is_visited():
    clocks = [{"id": "anchor", "location": "ship", "filled": 0, "segments": 4},
              {"id": "frost", "location": "bay", "filled": 0, "segments": 4}]
    new, full = r.tick_clocks(clocks, active_locations={"ship"})
    assert new[0]["filled"] == 1 and new[1]["filled"] == 0 and full == []
    assert clocks[0]["filled"] == 0               # исходные данные не мутируют
    new, _ = r.tick_clocks(new, active_locations={"ship", "bay"})
    assert new[1]["filled"] == 1                  # после посещения пошли


def test_clocks_stop_at_full_and_report_once():
    clocks = [{"id": "x", "location": "ship", "filled": 2, "segments": 3}]
    clocks, full = r.tick_clocks(clocks, {"ship"})
    assert full == ["x"] and clocks[0]["filled"] == 3
    clocks, full = r.tick_clocks(clocks, {"ship"})
    assert full == [] and clocks[0]["filled"] == 3


def test_resolved_clocks_do_not_tick():
    clocks = [{"id": "x", "location": "ship", "filled": 1, "segments": 3, "resolved": True}]
    new, _ = r.tick_clocks(clocks, {"ship"})
    assert new[0]["filled"] == 1


def test_empty_visited_location_keeps_ticking():
    clocks = [{"id": "x", "location": "ship", "filled": 0, "segments": 3}]
    active = {"ship"}           # герои ушли, но локация уже активирована ранее
    for _ in range(2):
        clocks, _ = r.tick_clocks(clocks, active)
    assert clocks[0]["filled"] == 2


# ------------------------------------------------ R-07 зоны, окрик, шёпот
def test_zone_distance():
    assert r.zone_distance(ADJ, "deck", "deck") == 0
    assert r.zone_distance(ADJ, "deck", "pier") == 1
    assert r.zone_distance(ADJ, "deck", "rocks") == 2
    assert r.zone_distance(ADJ, "hold", "trail") == 4
    assert r.zone_distance(ADJ, "deck", "island") is None


def test_shout_dc():
    assert r.shout_dc(1, False) == 10
    assert r.shout_dc(1, True) == 12
    assert r.shout_dc(2, True) == 14
    with pytest.raises(ValueError):
        r.shout_dc(0, False)


def test_whisper_only_inside_zone():
    assert r.can_whisper("deck", "deck")
    assert not r.can_whisper("deck", "pier")


def test_location_cap_of_five():
    full = {"a", "b", "c", "d", "e"}
    assert r.can_open_location({"a", "b", "c", "d"}, "f")
    assert not r.can_open_location(full, "f")
    assert r.can_open_location(full, "f", leaving_last=True)
    assert r.can_open_location(full, "a")                        # уже занята


# ------------------------------------------------ R-08 согласие, ход, голосования
def test_consent_status():
    assert r.consent_status(["eirik"], {}) == "pending"
    assert r.consent_status(["eirik"], {"eirik": "accept"}) == "confirmed"
    assert r.consent_status(["eirik"], {"eirik": "decline"}) == "declined"
    assert r.consent_status(["a", "b"], {"a": "accept"}) == "pending"
    assert r.consent_status(["a", "b"], {"a": "accept", "b": "decline"}) == "declined"
    assert r.consent_status([], {}) == "confirmed"


def test_round_ready_rules():
    assert r.all_ready({"a": "turn_ended", "b": "turn_ended"})
    assert not r.all_ready({"a": "turn_ended", "b": "thinking"})
    assert not r.all_ready({"a": "action_chosen", "b": "turn_ended"})
    assert r.all_ready({"a": "turn_ended", "b": "downed"})
    assert r.all_ready({"a": "turn_ended", "b": "ai"})
    assert r.all_ready({"a": "turn_ended", "b": "away"})
    assert not r.all_ready({})


def test_unanimous_vote():
    assert r.vote_passes("unanimous", {"a": True, "b": True, "c": True, "d": True}, 4) is True
    assert r.vote_passes("unanimous", {"a": True, "b": True, "c": True}, 4) is None
    assert r.vote_passes("unanimous", {"a": True, "b": False}, 4) is False


def test_majority_vote():
    assert r.vote_passes("majority", {"a": True, "b": True, "c": True}, 5) is True
    assert r.vote_passes("majority", {"a": False, "b": False, "c": False}, 5) is False
    assert r.vote_passes("majority", {"a": True, "b": True, "c": False, "d": False}, 5) is None
    assert r.vote_passes("majority", {"a": True, "b": True, "c": False, "d": False}, 4) is False
    assert r.vote_passes("majority", {"a": True, "b": True, "c": True}, 4) is True
    assert r.vote_passes("majority", {"a": True, "b": True, "c": False}, 4) is None
    with pytest.raises(ValueError):
        r.vote_passes("dictator", {}, 4)


def test_vote_rules_match_design():
    assert r.SETTING_VOTE_RULE["cruelty"] == "unanimous"
    assert r.SETTING_VOTE_RULE["save_and_exit"] == "unanimous"
    assert r.SETTING_VOTE_RULE["reader"] == "majority"
    assert r.SETTING_VOTE_RULE["ambience"] == "majority"
    assert r.SETTING_VOTE_RULE["skip_cutscene"] == "majority"


# ------------------------------------------------ R-09 знание и утечки
FACTS = [
    {"id": "hold_noise", "level": 1, "known_by": ["astrid", "eirik"]},
    {"id": "letter", "level": 2, "known_by": ["sigrid"]},
]


def test_hero_sees_only_own_facts():
    assert [f["id"] for f in r.visible_facts(FACTS, "astrid")] == ["hold_noise"]
    assert [f["id"] for f in r.visible_facts(FACTS, "sigrid")] == ["letter"]
    assert r.visible_facts(FACTS, "vald") == []


def test_share_fact_requires_same_zone_and_knowledge():
    zones = {"astrid": "deck", "eirik": "deck", "sigrid": "rocks", "vald": "deck"}
    shared = r.share_fact(FACTS[0], "astrid", ["vald"], zones)
    assert shared["known_by"] == ["astrid", "eirik", "vald"]
    assert FACTS[0]["known_by"] == ["astrid", "eirik"]          # оригинал не изменён
    with pytest.raises(ValueError):
        r.share_fact(FACTS[0], "astrid", ["sigrid"], zones)       # далеко
    with pytest.raises(ValueError):
        r.share_fact(FACTS[1], "astrid", ["vald"], zones)         # не знает сам


def test_info_level_never_decreases_and_has_cap():
    assert r.raise_level(2, 1) == 2
    assert r.raise_level(1, 2) == 2
    assert r.raise_level(2, 9) == 3


@pytest.mark.parametrize("outcome,personal,ally", [
    (Outcome.CRITICAL_FAIL, 0, 0), (Outcome.FAIL_WITH_CONSEQUENCE, 0, 0),
    (Outcome.FAIL, 0, 0), (Outcome.MINIMAL_SUCCESS, 1, 1),
    (Outcome.SUCCESS, 2, 2), (Outcome.GREAT_SUCCESS, 3, 2),
])
def test_info_gain_personal_and_ally(outcome, personal, ally):
    assert r.info_gain(outcome, is_ally=False) == personal
    assert r.info_gain(outcome, is_ally=True) == ally


def test_minimal_success_gives_hint_only():
    assert r.info_gain(Outcome.MINIMAL_SUCCESS, False) == 1


@pytest.mark.parametrize("visited,scouted,rumored,state", [
    (True, 2, True, "visited"), (False, 1, True, "scouted"),
    (False, 0, True, "rumor"), (False, 0, False, "unknown"),
])
def test_location_state_precedence(visited, scouted, rumored, state):
    assert r.location_state(visited, scouted, rumored) == state


TASKS = [
    {"id": "hold", "level": 2, "known_by": ["astrid"], "updated_round": 3,
     "phrases": {1: "Прислушаться к стуку", 2: "Спуститься в трюм"}},
    {"id": "shore", "level": 1, "known_by": ["astrid", "eirik"], "updated_round": 1,
     "phrases": {1: "Следить за тенями", 2: "Осмотреть берег"}},
    {"id": "anchor", "level": 0, "known_by": ["astrid"], "updated_round": 5,
     "phrases": {1: "Проверить канат"}},
    {"id": "secret", "level": 3, "known_by": ["eirik"], "updated_round": 9,
     "phrases": {3: "Вскрыть печать"}},
]


def test_chips_use_only_known_things_in_hero_words():
    chips = r.build_chips(TASKS, "astrid", ["Осмотреться", "Прислушаться", "Подождать"])
    assert chips["story"] == ["Спуститься в трюм", "Следить за тенями"]
    assert "Проверить канат" not in chips["story"]            # уровень 0: герой не знает
    assert "Вскрыть печать" not in chips["story"]             # чужая тайна


def test_chips_are_limited_and_simple_chip_rotates():
    many = [{"id": str(i), "level": 1, "known_by": ["a"], "updated_round": i,
             "phrases": {1: f"Фраза {i}"}} for i in range(6)]
    chips = r.build_chips(many, "a", ["x", "y"], rotation=3)
    assert len(chips["story"]) == 3 and chips["simple"] == "y"
    assert chips["story"][0] == "Фраза 5"                       # свежие сверху
