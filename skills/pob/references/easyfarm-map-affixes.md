# EasyFarm map modifiers for a PoE1 build

Use this workflow only when the user explicitly asks to modify EasyFarm (易刷 / 易泥 / E-farm) map-modifier rules or requests an EasyFarm map scheme/code. Resolve the build from the PoB code or share URL in the current request, the build the user identified earlier in the conversation, or an explicitly selected slot. Ask for a build source when none is available. A PoB code alone, a generic build or map question, or mentioning EasyFarm only in attached material does not trigger the workflow.

For example, “这是我的 PoB，帮我改一下易刷地图词缀” triggers PoB analysis, web research, map recommendations, and code generation in that order. “帮我预览要改的易刷地图词缀，暂时别生成” stops after the recommendations. EasyFarm handles the user's later preview and application.

## Identify how this build plays

Run `pob diagnose SOURCE --no-rank -q "<user request>"` or run `pob diagnose --target SLOT --no-rank -q "<user request>"` for the explicitly selected slot. Use the active loadout to identify the main skill, damage type and delivery, trigger or resource loop, ascendancy, enabling items or keystones, and the actual recovery and defense layers. Check whether the build depends on conditions such as flask uptime, being hit, aura effect, block, or killing monsters. Record a brief build profile with PoB evidence. A skill or ascendancy alone can describe several different builds.

## Research the matching archetype

Search the web after identifying the build. Use the main skill or trigger with its ascendancy and an enabling item or mechanic, scoped to PoE1 and the build's patch. Look for a matching build guide, written build showcase, or author notes that describe strengths, weaknesses, and map modifiers. For example, the query `PoE1 3.30 Cast when Stunned Chieftain Bloodnotch map modifiers` is more specific than `Chieftain map modifiers`. For individual mechanics or modifiers, use `pob research` with short entity names, or check official patch notes and the PoE Wiki/PoEDB.

Compare each source's patch, setup, and content to the active PoB. A guide can identify likely failure modes, while the loaded build determines whether they apply. Check the actual enabling gear, auras, and recovery before using a guide's avoid list. Cite the sources behind the relevant strengths and weaknesses. If no comparable guide is available, say so and use verified mechanics and PoB evidence for the recommendations. Keep disagreements or unverified interactions visible.

## Recommend map modifiers for the loaded build

1. Summarize what the build is good at and the conditions that make it fail. Show the relationship between each important strength or weakness and the map modifier that preserves or disrupts it.
2. Present the researched effects as **can run**, **caution**, or **skip**. Use **can run** when the current setup can handle the effect, **caution** when it amplifies a meaningful risk, and **skip** when it breaks a core damage, sustain, or defense dependency. Keep unevaluated effects separate from the can-run list. For each marked effect, give the reason for this build. Call out thresholds, map modifier effect, and relevant combinations when they matter. For example, no regeneration is high risk when regeneration is a primary source of sustain, while reflect depends on the damage actually dealt and the build's defenses. Character sheet values alone do not prove uptime.
3. For the import code, verify the exact stat identifier and resource path against the target PoE1 version using a user-provided or otherwise verified stat-description export. Check every display variant associated with the ID. For example, if the same ID covers increased and reduced aura effect, keep the reduced effect in the recommendations until a variant-aware rule can encode that reduction alone.
4. Return the build profile, sourced strengths and weaknesses, and map recommendations. Then generate the import code with verified skip and caution markers unless the user requested a preview only. The request to modify EasyFarm rules already authorizes generation. Leave can-run effects unmarked and keep unverified IDs, paths, or conditions in the written recommendations. If no eligible markers can be verified, report what is missing and do not emit an empty code.

## Generate an EasyFarm import code

Save a UTF-8 JSON request. The following is an example for a build that relies on life regeneration. The same classification need not apply to other builds.

```json
{
  "name": "Example build map warnings",
  "marks": [
    {
      "severity": "skip",
      "statId": "map_player_no_regeneration",
      "statPath": "Metadata/StatDescriptions/stat_descriptions.csd",
      "reason": "Life regeneration is the build's primary recovery source."
    }
  ]
}
```

Run from the repository root with Python 3.10+.

```text
python skills/pob/references/easyfarm_map_affixes.py map-marks.json
```

The default base is the adjacent `easyfarm-system-default-poe1.json` snapshot. The output is one new EasyFarm scheme that preserves the base version, colours and all unrelated rules. Redirect stdout to save the import code. To continue from a user's existing scheme, pass its JSON file or exported share-code text as the base:

```text
python skills/pob/references/easyfarm_map_affixes.py map-marks.json --base current-scheme.txt
```

For a selected exact stat ID already in a base affix group, the generator removes that ID from the old group and gives its original colour and text suffix to the dedicated warning rule. It leaves the other IDs in the group alone. When a prior generated scheme is the base, it restores the old entries before applying the new mark list, so removing a mark restores its old classification. Broad base patterns that also match a selected ID require a manual split; the generator stops instead of emitting overlapping rules. Each new mark adds `[跳过]` or `[慎打]` as a plain prefix and preserves placeholders and skill links. Omit identifiers that also match unwanted variants of the same effect.

## Check formatting before delivery

Use a plain-text prefix for warning-only edits to CSD variants containing numeric placeholders such as `{0}` and `{0:+d}`. Keep the original template byte-for-byte after the prefix, including existing color tags. Preserve the variant selector and suffix (for example `#|-1` and `negate 1`). Do not add a color wrapper to the prefix or combine the edit with automatic tier recoloring. For each edited variant, check that stripping the new prefix yields the original text, substitute a representative numeric value, and check that the neighboring variants are untouched. An offline check does not establish that the game renders the line. Report the in-game verification status explicitly.

Import the single new scheme in EasyFarm and preview its matches before applying. Check that reclassified IDs appear only under the new warning and retain their original colour. If source validation fails, reload the current game resources and regenerate the preview. This workflow has no game-writing step or hook.
