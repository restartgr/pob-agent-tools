"""The EasyFarm scheme must not apply two classifications to one map stat."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/pob/references/easyfarm_map_affixes.py"
spec = importlib.util.spec_from_file_location("easyfarm_map_affixes", SCRIPT)
easyfarm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(easyfarm)


def mark(stat_id="map_player_no_regeneration", severity="skip"):
    return {
        "severity": severity,
        "statId": stat_id,
        "statPath": "Metadata/StatDescriptions/stat_descriptions.csd",
        "reason": "test warning",
    }


def request(*marks):
    return {"name": "test scheme", "marks": list(marks)}


def test_exact_base_match_moves_to_warning_and_keeps_colour():
    base = easyfarm.read_base(easyfarm.DEFAULT_BASE)
    scheme = easyfarm.build_scheme(request(mark()), base)

    assert base["rules"][1]["matchValues"] != scheme["rules"][1]["matchValues"]
    assert sum(v["value"] == "map_player_no_regeneration"
               for rule in scheme["rules"][:-1] for v in rule.get("matchValues", [])) == 0
    assert len(scheme["rules"][1]["matchValues"]) == len(base["rules"][1]["matchValues"]) - 1
    warning = scheme["rules"][-1]
    assert warning["textFix"]["prefix"] == "[跳过] "
    assert (warning["colorMode"], warning["colorId"]) == ("line", "efarmVeryDangerous")
    assert scheme["essentialColours"] == base["essentialColours"]
    assert scheme["version"] == base["version"]


def test_next_generation_restores_removed_base_match():
    base = easyfarm.read_base(easyfarm.DEFAULT_BASE)
    reflected = mark("map_monsters_reflect_%_elemental_damage")
    first = easyfarm.build_scheme(request(mark(), reflected), base)
    changed = easyfarm.build_scheme(request(mark(severity="caution"), reflected), first)
    assert changed["rules"][-2]["textFix"]["prefix"] == "[慎打] "
    assert changed["rules"][-2]["colorId"] == "efarmVeryDangerous"

    removed = easyfarm.build_scheme(
        request(mark("map_monsters_additional_elemental_resistance", "caution")), changed
    )
    assert removed["rules"][:len(base["rules"])] == base["rules"]
    assert len(removed["rules"]) == len(base["rules"]) + 1


def test_broad_base_pattern_fails_instead_of_overlapping():
    base = easyfarm.read_base(easyfarm.DEFAULT_BASE)
    with pytest.raises(ValueError, match="Broad base pattern"):
        easyfarm.build_scheme(request(mark("map_boss_damage_foo")), base)
