"""Closed-world invocation classification for source-derived move behavior.

Every CIL invocation reachable directly from a registered move is assigned one
of the four semantic outcomes required by the source artifact.  Local gameplay
helpers are traversed (including compiler generated async MoveNext methods),
framework plumbing recognizers are deliberately exact, and an unknown command
or call fails with a stable evidence identifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping

from .canonical import witness_sha256
from .cil_eval import CilDataFlow, Invocation
from .errors import SourceExtractionError

_COMMAND_PREFIX = "MegaCrit.Sts2.Core.Commands."
_HELPER_PREFIXES = (
    "MegaCrit.Sts2.Core.Models.Monsters.",
    "MegaCrit.Sts2.Core.Models.Powers.",
    "MegaCrit.Sts2.Core.Models.Cards.",
)
_LOCAL_GAMEPLAY_HELPERS = frozenset({
    ("MegaCrit.Sts2.Core.Localization.DynamicVars.DynamicVar", "UpgradeValueBy"),
    ("MegaCrit.Sts2.Core.Runs.PlayerMapPointHistoryEntry", "MarkLootStolen"),
})

# These are semantic boundaries, not an ignore list.  New command declarations
# do not match and therefore abort extraction until a normalizer is added.
GAMEPLAY_COMMANDS: dict[tuple[str, str], str] = {
    ("MegaCrit.Sts2.Core.Commands.DamageCmd", "Attack"): "attack",
    ("MegaCrit.Sts2.Core.Commands.Builders.AttackCommand", "WithHitCount"): "attackHitCount",
    ("MegaCrit.Sts2.Core.Commands.PowerCmd", "Apply"): "applyPower",
    ("MegaCrit.Sts2.Core.Commands.PowerCmd", "Remove"): "removePower",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "GainBlock"): "gainBlock",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "Add"): "summon",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "Escape"): "escape",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "Heal"): "heal",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "Kill"): "kill",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "Stun"): "stun",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "SetMaxHp"): "setMaxHp",
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "SetMaxAndCurrentHp"): "setMaxAndCurrentHp",
    ("MegaCrit.Sts2.Core.Commands.CardPileCmd", "AddToCombatAndPreview"): "addStatusCard",
    ("MegaCrit.Sts2.Core.Commands.CardPileCmd", "AddGeneratedCardToCombat"): "addGeneratedCard",
    ("MegaCrit.Sts2.Core.Commands.CardPileCmd", "RemoveFromCombat"): "removeCard",
    ("MegaCrit.Sts2.Core.Commands.CardPileCmd", "RemoveFromDeck"): "removeDeckCard",
    ("MegaCrit.Sts2.Core.Commands.CardSelectCmd", "FromChooseACardScreen"): "chooseCard",
    ("MegaCrit.Sts2.Core.Commands.PlayerCmd", "LoseGold"): "loseGold",
}

_ATTACK_BUILDER_SUPPORT = frozenset({
    "AfterAttackerAnim", "BeforeDamage", "Execute", "FromMonster",
    "OnlyPlayAnimOnce", "SpawningHitVfxOnEachCreature", "WithAttackerAnim",
    "WithAttackerFx", "WithHitFx", "WithHitVfxNode",
    "WithHitVfxSpawnedAtBase", "WithNoAttackerAnim", "WithWaitBeforeHit",
})

# Exact source declarations whose documented role is presentation or waiting.
# They remain in the census with their declaration/signature as evidence.
PRESENTATION_COMMANDS = frozenset({
    ("MegaCrit.Sts2.Core.Commands.CardCmd", "PreviewCardPileAdd"),
    ("MegaCrit.Sts2.Core.Commands.Cmd", "CustomScaledWait"),
    ("MegaCrit.Sts2.Core.Commands.Cmd", "Wait"),
    ("MegaCrit.Sts2.Core.Commands.CreatureCmd", "TriggerAnim"),
    ("MegaCrit.Sts2.Core.Commands.SfxCmd", "Play"),
    ("MegaCrit.Sts2.Core.Commands.SfxCmd", "PlayLoop"),
    ("MegaCrit.Sts2.Core.Commands.SfxCmd", "SetParam"),
    ("MegaCrit.Sts2.Core.Commands.SfxCmd", "StopLoop"),
    ("MegaCrit.Sts2.Core.Commands.TalkCmd", "Play"),
    ("MegaCrit.Sts2.Core.Commands.ThinkCmd", "Play"),
    ("MegaCrit.Sts2.Core.Commands.VfxCmd", "PlayOnCreatureCenter"),
    ("MegaCrit.Sts2.Core.Commands.VfxCmd", "PlayOnCreatureCenters"),
})

_SYSTEM_PLUMBING: dict[str, frozenset[str]] = {
    "System.Collections.IEnumerator": frozenset({"MoveNext"}),
    "System.Decimal": frozenset({
        ".ctor", "op_Addition", "op_Division", "op_Equality", "op_Explicit",
        "op_GreaterThan", "op_GreaterThanOrEqual", "op_Implicit",
        "op_Inequality", "op_LessThan", "op_LessThanOrEqual",
        "op_Multiply", "op_Subtraction",
    }),
    "System.InvalidOperationException": frozenset({".ctor"}),
    "System.Linq.Enumerable": frozenset({
        "Any", "First", "FirstOrDefault", "LastOrDefault", "Max", "OfType",
        "Select", "ToList", "Where", "Except", "All",
    }),
    "System.Math": frozenset({"Max", "Min"}),
    "System.Runtime.CompilerServices.AsyncTaskMethodBuilder": frozenset({
        "AwaitUnsafeOnCompleted", "Create", "SetException", "SetResult", "Start", "get_Task",
    }),
    "System.Runtime.CompilerServices.DefaultInterpolatedStringHandler": frozenset({
        ".ctor", "AppendFormatted", "AppendLiteral", "ToStringAndClear",
    }),
    "System.Runtime.CompilerServices.TaskAwaiter": frozenset({"GetResult", "get_IsCompleted"}),
    "System.String": frozenset({"IsNullOrEmpty"}),
    "System.Threading.Tasks.Task": frozenset({"GetAwaiter", "WhenAll", "get_CompletedTask"}),
}

_GODOT_PRESENTATION: dict[str, frozenset[str]] = {
    "Godot.CanvasItem": frozenset({"GetViewportRect", "SetSelfModulate"}),
    "Godot.Color": frozenset({".ctor"}),
    "Godot.Colors": frozenset({"get_White"}),
    "Godot.Control": frozenset({"get_GlobalPosition", "get_Position", "get_Size", "set_Position"}),
    "Godot.Mathf": frozenset({"Clamp", "FloorToInt", "Log"}),
    "Godot.Node": frozenset({"GetNode"}),
    "Godot.Node2D": frozenset({"get_GlobalPosition", "get_Scale", "set_GlobalPosition", "set_Position"}),
    "Godot.NodePath": frozenset({"op_Implicit"}),
    "Godot.PackedScene": frozenset({"Instantiate"}),
    "Godot.Rect2": frozenset({"get_Size"}),
    "Godot.ResourceLoader": frozenset({"Load"}),
    "Godot.Sprite2D": frozenset({"set_Texture"}),
    "Godot.Vector2": frozenset({".ctor", "get_Left", "op_Addition", "op_Multiply"}),
}

_TYPESPEC_PLUMBING = frozenset({
    ".ctor", "Add", "ForEach", "GetAwaiter", "GetEnumerator", "GetResult",
    "MoveNext", "get_Count", "get_Current", "get_IsCompleted", "get_Item",
})


def invocation_identity(symbol: str) -> tuple[str, str, str]:
    """Return exact declaring type, member, and raw metadata signature."""
    if not isinstance(symbol, str) or "::" not in symbol or " sig:" not in symbol:
        raise SourceExtractionError(f"invocation has no exact source identity: {symbol!r}")
    before_generic = re.split(r" (?:generic|methodspec):", symbol, maxsplit=1)[0]
    owner, tail = before_generic.split("::", 1)
    member, signature = tail.split(" sig:", 1)
    if not owner or not member or not re.fullmatch(r"[0-9a-fA-F]+", signature):
        raise SourceExtractionError(f"malformed invocation identity: {symbol}")
    return owner, member, signature.lower()


def stable_unresolved_id(move_id: str, method_symbol: str, invocation: Invocation, reason: str) -> str:
    witness = "\x1f".join((move_id, method_symbol, str(invocation.index), invocation.symbol, reason))
    return "UNRESOLVED.INVOCATION." + hashlib.sha256(witness.encode("utf-8")).hexdigest()


def _base_symbol(symbol: str) -> str:
    return re.split(r" (?:generic|methodspec):", symbol, maxsplit=1)[0]


@dataclass(frozen=True)
class _LocalMethod:
    index: int
    owner: str
    member: str
    symbol: str
    special_name: bool
    abstract: bool


class ClosedWorldInvocationAudit:
    """Classify all direct sites and recursively inspect local behavior helpers."""

    def __init__(self, assembly: Any, assembly_sha256: str, async_methods: Mapping[int, int]):
        self.assembly = assembly
        self.assembly_sha256 = assembly_sha256
        self.async_methods = dict(async_methods)
        self.decisions: list[dict[str, Any]] = []
        self._decision_ids: set[str] = set()
        self._direct_decisions = 0
        self._helper_decisions = 0
        self._helper_cache: dict[str, dict[str, Any]] = {}
        self._helper_active: set[str] = set()

    def _local_method(self, symbol: str) -> _LocalMethod | None:
        owner, member, _ = invocation_identity(symbol)
        matches = [
            index for index in self.assembly.find_methods(owner, member)
            if self.assembly.method_symbol(index) == _base_symbol(symbol)
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise SourceExtractionError(f"ambiguous local invocation declaration: {symbol}")
        index = matches[0]
        row = self.assembly.md.MethodDef.rows[index - 1]
        flags = row.Flags
        return _LocalMethod(
            index=index, owner=owner, member=member,
            symbol=self.assembly.method_symbol(index),
            special_name=bool(getattr(flags, "mdSpecialName", False)),
            abstract=bool(getattr(flags, "mdAbstract", False)),
        )

    @staticmethod
    def _is_behavior_helper(owner: str, member: str) -> bool:
        return ((owner.startswith(_HELPER_PREFIXES) or (owner, member) in _LOCAL_GAMEPLAY_HELPERS)
                and not member.startswith(("get_", "set_", ".ctor")))

    def _concrete_overrides(self, method: _LocalMethod) -> list[_LocalMethod]:
        result: list[_LocalMethod] = []
        implementers: set[str] = set()
        interface_table = getattr(self.assembly.md, "InterfaceImpl", None)
        if interface_table is not None:
            for row in interface_table.rows:
                try:
                    if self.assembly._type_ref_name(row.Interface.row) == method.owner:
                        implementers.add(self.assembly.type_names[row.Class.row_index])
                except (AttributeError, KeyError, SourceExtractionError):
                    continue
        for candidate_owner in sorted(self.assembly.type_names.values()):
            if (candidate_owner != method.owner
                    and candidate_owner not in implementers
                    and not self.assembly.derives_from(candidate_owner, method.owner)):
                continue
            for index in self.assembly.find_methods(candidate_owner, method.member):
                symbol = self.assembly.method_symbol(index)
                try:
                    _, _, signature = invocation_identity(symbol)
                    _, _, expected = invocation_identity(method.symbol)
                except SourceExtractionError:
                    continue
                row = self.assembly.md.MethodDef.rows[index - 1]
                if signature == expected and not getattr(row.Flags, "mdAbstract", False):
                    result.append(_LocalMethod(index, candidate_owner, method.member, symbol,
                                               bool(getattr(row.Flags, "mdSpecialName", False)), False))
        return result

    def _helper_evidence(self, method: _LocalMethod) -> dict[str, Any]:
        cached = self._helper_cache.get(method.symbol)
        if cached is not None:
            return cached
        if method.symbol in self._helper_active:
            raise SourceExtractionError(f"recursive behavior helper cycle: {method.symbol}")
        self._helper_active.add(method.symbol)
        try:
            implementations = self._concrete_overrides(method) if method.abstract else [method]
            if not implementations:
                raise SourceExtractionError(f"behavior helper has no concrete source implementation: {method.symbol}")
            traversed: list[dict[str, Any]] = []
            effects: list[dict[str, Any]] = []
            nested_sites = 0
            for implementation in implementations:
                body_index = self.async_methods.get(implementation.index, implementation.index)
                record = self.assembly.method_record(body_index, self.assembly_sha256)
                calls = CilDataFlow(record["instructions"]).run()
                nested_sites += len(calls)
                traversed.append({
                    "methodBodySha256": record["methodBodySha256"],
                    "symbolSignature": record["symbolSignature"],
                })
                for nested in calls.values():
                    helper_root = "HELPER." + witness_sha256([record["symbolSignature"]])
                    try:
                        nested_result = self._classify(
                            nested, record, helper_root, record["symbolSignature"],
                            record_decision=False,
                        )
                    except SourceExtractionError as exc:
                        unresolved = stable_unresolved_id(
                            helper_root, record["symbolSignature"], nested, str(exc)
                        )
                        raise SourceExtractionError(f"{unresolved}: {exc}") from exc
                    helper_id = f"{helper_root}/invocation/{nested.index}"
                    self._record_decision(
                        nested_result, nested, helper_id,
                        source_method=record["symbolSignature"], helper=True,
                    )
                    if nested_result["classification"] == "normalizedGameplayOperation":
                        effects.append({
                            "kind": nested_result["normalizedKind"],
                            "sinkSymbolSignature": nested.symbol,
                            "sourceOrder": nested.index,
                            "sourceMethod": record["symbolSignature"],
                        })
                    if (nested_result["classification"] == "traversedGameplayHelper"
                            and nested_result.get("role") == "sourceMethodBody"):
                        child = nested_result["evidence"]
                        effects.extend(child["gameplayEffects"])
                        nested_sites += child["nestedInvocationSites"]
                        traversed.extend(child["traversedMethods"])
            evidence = {
                "gameplayEffects": effects,
                "nestedInvocationSites": nested_sites,
                "traversedMethods": sorted(
                    {witness_sha256(row): row for row in traversed}.values(),
                    key=lambda row: row["symbolSignature"],
                ),
            }
            self._helper_cache[method.symbol] = evidence
            return evidence
        finally:
            self._helper_active.remove(method.symbol)

    @staticmethod
    def _known_command_support(owner: str, member: str) -> bool:
        if owner == "MegaCrit.Sts2.Core.Commands.Builders.AttackCommand":
            return member in _ATTACK_BUILDER_SUPPORT or member == "WithHitCount"
        return (owner, member) in PRESENTATION_COMMANDS

    def _record_decision(self, result: Mapping[str, Any], invocation: Invocation,
                         invocation_id: str, *, source_method: str | None = None,
                         helper: bool) -> None:
        decision = {
            "classification": result["classification"],
            "evidence": result["evidence"],
            "invocationId": invocation_id,
            "sourceOrder": invocation.index,
        }
        if source_method is not None:
            decision["sourceMethod"] = source_method
        if "normalizedKind" in result:
            decision["normalizedKind"] = result["normalizedKind"]
        if "role" in result:
            decision["role"] = result["role"]
        if invocation_id in self._decision_ids:
            previous = next(row for row in self.decisions if row["invocationId"] == invocation_id)
            if previous != decision:
                raise SourceExtractionError(f"invocation decision changed across helper paths: {invocation_id}")
            return
        self._decision_ids.add(invocation_id)
        self.decisions.append(decision)
        if helper:
            self._helper_decisions += 1
        else:
            self._direct_decisions += 1

    def _classify(self, invocation: Invocation, record: Mapping[str, Any], move_id: str,
                  method_symbol: str, *, record_decision: bool) -> dict[str, Any]:
        owner, member, signature = invocation_identity(invocation.symbol)
        identity = {
            "declaringType": owner,
            "member": member,
            "metadataSignature": signature,
            "symbolSignature": invocation.symbol,
        }
        command_kind = GAMEPLAY_COMMANDS.get((owner, member))
        fake_merchant_key_context = (
            owner == "System.String" and member == "Concat" and signature == "00040e0e0e0e0e"
            and method_symbol == "MegaCrit.Sts2.Core.Models.Monsters.FakeMerchantMonster::GetLinesForMove sig:2001151281f50112a4480e"
            and len(invocation.arguments) == 4
            and invocation.arguments[0].kind == "call"
            and invocation.arguments[0].data == "MegaCrit.Sts2.Core.Models.ModelId::get_Entry sig:20000e"
            and len(invocation.arguments[0].operands) == 1
            and invocation.arguments[0].operands[0].kind == "call"
            and invocation.arguments[0].operands[0].data == "MegaCrit.Sts2.Core.Models.AbstractModel::get_Id sig:20001288dc"
            and len(invocation.arguments[0].operands[0].operands) == 1
            and invocation.arguments[0].operands[0].operands[0].kind == "argument"
            and invocation.arguments[0].operands[0].operands[0].data == "0"
            and invocation.arguments[1].kind == "string" and invocation.arguments[1].data == ".moves."
            and invocation.arguments[2].kind == "argument" and invocation.arguments[2].data == "1"
            and invocation.arguments[3].kind == "string" and invocation.arguments[3].data == ".speakLine"
        )
        if fake_merchant_key_context:
            result = {"classification": "provenNonGameplayPlumbing", "role": "dialogueLocalizationKeyConstruction",
                      "evidence": {**identity, "rule": "exactFakeMerchantDialogueLocalizationKeyConcatContext"}}
        elif command_kind is not None:
            result = {"classification": "normalizedGameplayOperation", "normalizedKind": command_kind,
                      "evidence": {**identity, "rule": "exactGameplayCommandDeclaration"}}
        elif owner.startswith(_COMMAND_PREFIX):
            if owner == "MegaCrit.Sts2.Core.Commands.Builders.AttackCommand" and member in _ATTACK_BUILDER_SUPPORT:
                result = {"classification": "traversedGameplayHelper", "role": "attackCommandBuilder",
                          "evidence": {**identity, "rule": "exactAttackBuilderDeclaration"}}
            elif (owner, member) in PRESENTATION_COMMANDS:
                role = "wait" if owner.endswith(".Cmd") else "presentation"
                result = {"classification": "provenNonGameplayPlumbing", "role": role,
                          "evidence": {**identity, "rule": "exactPresentationOrWaitDeclaration"}}
            else:
                raise SourceExtractionError(f"unknown command/effect API: {invocation.symbol}")
        else:
            local = self._local_method(invocation.symbol)
            if local is not None:
                if local.special_name and member.startswith("get_"):
                    result = {"classification": "provenNonGameplayPlumbing", "role": "sourceRead",
                              "evidence": {**identity, "rule": "localSpecialNameGetterDeclaration"}}
                elif (owner, member) == ("MegaCrit.Sts2.Core.Models.AbstractModel", "AssertMutable"):
                    result = {"classification": "provenNonGameplayPlumbing", "role": "mutationGuard",
                              "evidence": {**identity, "rule": "exactModelMutationGuardDeclaration"}}
                elif local.special_name and member.startswith("set_"):
                    if (owner, member) == ("MegaCrit.Sts2.Core.Models.Monsters.LagavulinMatriarch", "set_SleepingVfx"):
                        result = {"classification": "provenNonGameplayPlumbing", "role": "presentationState",
                                  "evidence": {**identity, "rule": "exactPresentationNodeStateDeclaration"}}
                    elif owner.startswith("MegaCrit.Sts2.Core.Models.Monsters."):
                        result = {"classification": "normalizedGameplayOperation", "normalizedKind": "stateWrite",
                                  "evidence": {**identity, "rule": "localMonsterSpecialNameSetterDeclaration"}}
                    elif owner == "MegaCrit.Sts2.Core.Models.PowerModel":
                        result = {"classification": "traversedGameplayHelper", "role": "powerConstruction",
                                  "evidence": {**identity, "rule": "exactPowerConstructionSetterDeclaration"}}
                    elif owner.startswith(("MegaCrit.Sts2.Core.Models.Cards.", "MegaCrit.Sts2.Core.Models.Powers.")):
                        result = {"classification": "normalizedGameplayOperation", "normalizedKind": "stateWrite",
                                  "evidence": {**identity, "rule": "localModelSpecialNameSetterDeclaration"}}
                    elif owner.startswith("MegaCrit.Sts2.Core.Models."):
                        result = {"classification": "traversedGameplayHelper", "role": "modelConstructionOrInternalState",
                                  "evidence": {**identity, "rule": "localModelSpecialNameSetterDeclaration"}}
                    else:
                        result = {"classification": "provenNonGameplayPlumbing", "role": "presentationState",
                                  "evidence": {**identity, "rule": "localNonModelSpecialNameSetterDeclaration"}}
                elif self._is_behavior_helper(owner, member):
                    helper = self._helper_evidence(local)
                    result = {"classification": "traversedGameplayHelper", "role": "sourceMethodBody",
                              "evidence": {**identity, "rule": "exactLocalHelperTraversal", **helper}}
                elif member == ".ctor":
                    result = {"classification": "provenNonGameplayPlumbing", "role": "sourceObjectConstruction",
                              "evidence": {**identity, "rule": "exactLocalConstructorDeclaration"}}
                elif invocation.signature.returns.kind != "void":
                    result = {"classification": "provenNonGameplayPlumbing", "role": "sourceQuery",
                              "evidence": {**identity, "rule": "exactLocalValueReturningDeclaration"}}
                elif owner.startswith(("MegaCrit.Sts2.Core.Nodes.", "MegaCrit.Sts2.Core.Bindings.",
                                       "MegaCrit.Sts2.Core.Helpers.", "MegaCrit.Sts2.Core.Assets.")):
                    result = {"classification": "provenNonGameplayPlumbing", "role": "presentation",
                              "evidence": {**identity, "rule": "localPresentationDeclaration"}}
                else:
                    raise SourceExtractionError(f"unclassified local side-effecting invocation: {invocation.symbol}")
            elif owner.startswith("<TypeSpec:") and member in _TYPESPEC_PLUMBING:
                result = {"classification": "provenNonGameplayPlumbing", "role": "compilerAsyncOrCollection",
                          "evidence": {**identity, "rule": "exactTypeSpecPlumbingMember"}}
            elif member in _SYSTEM_PLUMBING.get(owner, frozenset()):
                result = {"classification": "provenNonGameplayPlumbing", "role": "frameworkCompilerCollectionOrFormula",
                          "evidence": {**identity, "rule": "exactFrameworkPlumbingDeclaration"}}
            elif member in _GODOT_PRESENTATION.get(owner, frozenset()):
                result = {"classification": "provenNonGameplayPlumbing", "role": "presentation",
                          "evidence": {**identity, "rule": "exactGodotPresentationDeclaration"}}
            else:
                raise SourceExtractionError(f"unclassified invocation declaration: {invocation.symbol}")
        if record_decision:
            self._record_decision(
                result, invocation, f"{move_id}/invocation/{invocation.index}",
                helper=False,
            )
        return result

    def classify(self, invocation: Invocation, record: Mapping[str, Any], move_id: str) -> dict[str, Any]:
        try:
            return self._classify(invocation, record, move_id, record["symbolSignature"], record_decision=True)
        except SourceExtractionError as exc:
            unresolved = stable_unresolved_id(move_id, record["symbolSignature"], invocation, str(exc))
            raise SourceExtractionError(f"{unresolved}: {exc}") from exc

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for decision in self.decisions:
            key = decision["classification"]
            counts[key] = counts.get(key, 0) + 1
        direct = [row for row in self.decisions if not row["invocationId"].startswith("HELPER.")]
        helper = [row for row in self.decisions if row["invocationId"].startswith("HELPER.")]
        if (len(direct), len(helper)) != (self._direct_decisions, self._helper_decisions):
            raise SourceExtractionError("invocation direct/helper census accounting mismatch")
        return {
            "classificationCounts": dict(sorted(counts.items())),
            "denominator": len(self.decisions),
            "directDenominator": len(direct),
            "helperDenominator": len(helper),
            "resolved": len(self.decisions),
            "unresolved": 0,
            "vocabularySize": len({row["evidence"]["symbolSignature"] for row in self.decisions}),
            "directVocabularySize": len({row["evidence"]["symbolSignature"] for row in direct}),
        }
