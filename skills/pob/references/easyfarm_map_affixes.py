"""Merge verified PoE1 map warnings into an EasyFarm scheme and encode it."""

import argparse
import base64
import copy
import gzip
import json
import re
import sys
import time
import uuid
import zlib
from pathlib import Path

DEFAULT_BASE = Path(__file__).with_name("easyfarm-system-default-poe1.json")
GENERATED_RULE = "pob4agents:map-affix-warning"
PREFIXES = {"skip": "[\u8df3\u8fc7] ", "caution": "[\u614e\u6253] "}
STAT_PATHS = {
    f"metadata/statdescriptions/{name}.csd"
    for name in ("stat_descriptions", "map_stat_descriptions")
}
STAT_ID = re.compile(r"map_[a-z0-9_+%]+")


def read_base(path):
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw.startswith("{"):
        raw = gzip.decompress(base64.b64decode(raw, validate=True)).decode("utf-8")
    base = json.loads(raw)
    if not isinstance(base, dict):
        raise TypeError("Expected an EasyFarm scheme object")
    for key in ("rules", "essentialColours"):
        entries = base.get(key)
        if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
            raise ValueError(f"Expected EasyFarm {key} to be a list of objects")
    if type(base.get("version")) is not int or base["version"] < 1:
        raise ValueError("Expected a positive EasyFarm scheme version")
    return base


def _is_generated(rule):
    remark = rule.get("remark", "")
    return rule.get("type") == "affix" and isinstance(remark, str) and (
        remark == GENERATED_RULE or remark.startswith(GENERATED_RULE + "|")
    )


def _backups(rule):
    remark = rule["remark"]
    if "|" not in remark:
        return []  # Schemes made by the first version did not keep restoration data.
    try:
        return json.loads(base64.urlsafe_b64decode(remark.split("|", 1)[1]))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid saved EasyFarm rule backup") from exc


def _restore_original_rules(kept_rules, previous_rules):
    # Undo removals in reverse order so match positions return to their original order.
    for generated in reversed(previous_rules):
        for backup in reversed(_backups(generated)):
            found = [rule for rule in kept_rules if rule.get("type") == "affix"
                     and rule.get("name") == backup["name"]]
            if len(found) == 1:
                matches = found[0]["matchValues"]
                matches.insert(min(backup["matchIndex"], len(matches)), backup["match"])
            elif not found and backup.get("rule"):
                kept_rules.insert(min(backup["ruleIndex"], len(kept_rules)), backup["rule"])
            else:
                raise ValueError(f"Cannot restore original EasyFarm rule: {backup['name']}")


def build_scheme(request, base):
    if not isinstance(request, dict):
        raise TypeError("Expected a JSON object")
    name, marks = request.get("name"), request.get("marks")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Expected a nonempty scheme name")
    if not isinstance(marks, list) or not marks:
        raise ValueError("Expected at least one verified map modifier")

    kept_rules = [
        copy.deepcopy(rule) for rule in base["rules"]
        if not _is_generated(rule)
    ]
    previous_rules = [
        rule for rule in base["rules"] if _is_generated(rule)
    ]
    _restore_original_rules(kept_rules, previous_rules)
    rules = []
    seen = set()
    for mark in marks:
        if not isinstance(mark, dict):
            raise TypeError("Each mark must be an object")
        severity, stat_id, path, reason = (
            mark.get(key) for key in ("severity", "statId", "statPath", "reason")
        )
        if not all(isinstance(value, str) for value in (severity, stat_id, path, reason)):
            raise ValueError("Each mark requires severity, statId, statPath and reason")
        if severity not in PREFIXES or not STAT_ID.fullmatch(stat_id) or not reason.strip():
            raise ValueError(f"Invalid map mark: {stat_id}")
        path = path.lower()
        if path not in STAT_PATHS:
            raise ValueError(f"Unsupported map stat path: {path}")
        key = (path, stat_id)
        if key in seen:
            raise ValueError(f"Duplicate map mark: {stat_id} in {path}")
        seen.add(key)
        match_value = rf"(?:^|\s){re.escape(stat_id)}(?:\s|$)"
        style = None
        backups = []
        for old_rule in previous_rules:
            if any(value.get("value") == match_value for value in old_rule.get("matchValues", [])):
                old_prefix = old_rule.get("textFix", {}).get("prefix", "")
                for warning_prefix in PREFIXES.values():
                    if old_prefix.startswith(warning_prefix):
                        old_prefix = old_prefix[len(warning_prefix):]
                        break
                style = (
                    old_rule.get("colorMode", "none"),
                    old_rule.get("colorId", ""),
                    old_prefix,
                    old_rule.get("textFix", {}).get("suffix", ""),
                )

        for rule_index, old_rule in enumerate(kept_rules):
            if (old_rule.get("type") != "affix" or old_rule.get("matchType") != "idLine"
                    or not old_rule.get("enabled", True)):
                continue
            old_path = old_rule.get("statPath")
            if old_path and old_path.lower() != path:
                continue
            matches = old_rule.get("matchValues", [])
            for match_index, value in reversed(list(enumerate(matches))):
                pattern = value.get("value", "")
                if pattern == stat_id:
                    if old_rule.get("colorMatchValues"):
                        raise ValueError(f"Cannot preserve conditional colour for {stat_id}")
                    text_fix = old_rule.get("textFix") or {}
                    old_style = (
                        old_rule.get("colorMode", "none"),
                        old_rule.get("colorId", ""),
                        text_fix.get("prefix", ""),
                        text_fix.get("suffix", ""),
                    )
                    if style is not None and style != old_style:
                        raise ValueError(f"Conflicting base styles for {stat_id}")
                    style = old_style
                    backups.append({
                        "name": old_rule.get("name"),
                        "ruleIndex": rule_index,
                        "matchIndex": match_index,
                        "match": copy.deepcopy(value),
                        "rule": copy.deepcopy(old_rule) if len(matches) == 1 else None,
                    })
                    matches.pop(match_index)
                else:
                    try:
                        overlaps = re.search(pattern, stat_id) is not None
                    except re.error as exc:
                        raise ValueError(f"Cannot inspect base pattern {pattern!r}: {exc}") from exc
                    if overlaps:
                        raise ValueError(
                            f"Broad base pattern {pattern!r} also matches {stat_id}; split it manually"
                        )
        kept_rules = [rule for rule in kept_rules if rule.get("type") != "affix" or rule.get("matchValues")]
        color_mode, color_id, old_prefix, old_suffix = style or ("none", "", "", "")
        rules.append({
            "type": "affix",
            "name": f"{PREFIXES[severity].strip()} {stat_id}",
            "enabled": True,
            "matchType": "idLine",
            "matchValues": [{"value": match_value, "remark": reason.strip()}],
            "colorMatchValues": [],
            "textFix": {"prefix": PREFIXES[severity] + old_prefix, "suffix": old_suffix},
            "colorMode": color_mode,
            "colorId": color_id,
            "statPath": path,
            "remark": GENERATED_RULE + "|" + base64.urlsafe_b64encode(
                json.dumps(backups, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).decode("ascii"),
        })
    return {
        **base,
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "description": "PoE1 build-specific map modifier warnings",
        "author": "pob4agents",
        "createdAt": int(time.time() * 1000),
        "rules": kept_rules + rules,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON with verified map modifier marks")
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE, help="EasyFarm JSON or share code")
    args = parser.parse_args()
    try:
        request = json.loads(args.input.read_text(encoding="utf-8-sig"))
        scheme = build_scheme(request, read_base(args.base))
    except (TypeError, ValueError, OSError, EOFError, zlib.error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    data = json.dumps(scheme, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    print(base64.b64encode(gzip.compress(data, mtime=0)).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
