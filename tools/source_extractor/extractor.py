"""Build the deterministic v0.111.0 normalized source-world artifact."""

from __future__ import annotations

import hashlib
from typing import Any

from . import EXTRACTOR_VERSION, SCHEMA_VERSION
from .canonical import canonical_json_bytes, strict_json_bytes, witness_sha256
from .behavior import attach_event_turn_behavior, extract_behavior
from .ast import validate_operation
from .combat_scaling import extract_combat_scaling
from .encounters import extract_rosters
from .errors import SourceExtractionError
from .event_scripts import extract_event_scripts
from .input_gate import VerifiedInputs
from .localization import require_localized_text
from .identity import extract_observation_identities
from .hp_pipeline import extract_hp_pipeline
from .initial_state import extract_initial_state
from .placement import extract_placement
from .metadata import AssemblyMetadata, extract_encounter_census
from .names import join_monster_names
from .pck import read_selected
from .scaling import extract_hp_multiplayer_scaling
from .states import extract_state_facts
from .world import extract_monster_world

_ENCOUNTER_LOCALIZATION = "localization/eng/encounters.json"
_MONSTER_LOCALIZATION = "localization/eng/monsters.json"
_INTENT_LOCALIZATION = "localization/eng/intents.json"
_POWER_LOCALIZATION = "localization/eng/powers.json"
_CARD_LOCALIZATION = "localization/eng/cards.json"
_ANCIENT_LOCALIZATION = "localization/eng/ancients.json"
_DLL_PATH = "data_sts2_linuxbsd_x86_64/sts2.dll"
_PCK_PATH = "SlayTheSpire2.pck"


def complete(numerator: int, denominator: int) -> dict[str, Any]:
    if numerator != denominator:
        raise SourceExtractionError(f"cannot mark partial coverage complete: {numerator}/{denominator}")
    return {"denominator": denominator, "numerator": numerator, "status": "complete", "unresolved": 0}


def not_extracted() -> dict[str, str]:
    return {"status": "notExtracted"}



def _localization(verified: VerifiedInputs, path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    pck = verified.by_relative_path(_PCK_PATH)
    data, entry, info = read_selected(pck.path, path)
    value = strict_json_bytes(data, f"{_PCK_PATH}:{path}")
    if not isinstance(value, dict):
        raise SourceExtractionError(f"{path}: top level must be an object")
    blob = {
        "entryFlags": entry.flags, "entryMd5": entry.md5,
        "entrySha256": hashlib.sha256(data).hexdigest(),
        "pckDirectoryOffset": info.directory_offset, "pckFileCount": info.file_count,
        "pckFormat": info.format, "pckGodotVersion": list(info.godot_version),
        "pckPath": path, "pckSha256": pck.sha256,
    }
    return value, blob


def _referenced_models(behavior: dict[str, Any], initial_state: dict[str, Any], powers: dict[str, Any], cards: dict[str, Any],
                       power_blob: dict[str, Any], card_blob: dict[str, Any]) -> dict[str, Any]:
    refs = {op.get("model") for move in behavior["registrations"] for op in move["operations"] if op.get("model")}
    power_refs = {x for x in refs if x.startswith("POWER.")}
    power_refs.update(x["canonicalPower"] for x in behavior["scaling"]["power"]["optIns"])
    power_refs.update(x["canonicalPower"] for x in behavior["scaling"]["power"]["overrides"])
    power_refs.update(row["canonicalPower"] for row in initial_state["powerHookClosure"])
    power_refs.update(fact["effect"]["model"] for fact in initial_state["initialStateFacts"]
                      if fact["effect"]["kind"] == "applyPower")
    card_refs = {x for x in refs if x.startswith("CARD.")}
    def rows(items: set[str], localization: dict[str, Any], blob: dict[str, Any]) -> list[dict[str, Any]]:
        output=[]
        for canonical in sorted(items):
            entry=canonical.split(".",1)[1]
            title_key=entry+".title"; smart_key=entry+".smartDescription"
            title=localization.get(title_key)
            if not isinstance(title,str) or not title:
                raise SourceExtractionError(f"missing referenced model localization {title_key}")
            smart=localization.get(smart_key)
            if smart is not None and (not isinstance(smart,str) or not smart):
                raise SourceExtractionError(f"invalid referenced model localization {smart_key}")
            output.append({"canonicalId":canonical,"englishTitle":title,
                "smartDescription":({"classification":"localized","key":smart_key,"template":smart} if smart is not None else {"classification":"missingLocalization","key":smart_key}),
                "provenance":{"blobSha256":blob["entrySha256"],"pckPath":blob["pckPath"],"pckSha256":blob["pckSha256"],
                              "titleKey":title_key,"titleWitnessSha256":witness_sha256([title_key,title])}})
        return output
    return {"cards":rows(card_refs,cards,card_blob),"powers":rows(power_refs,powers,power_blob)}

def _encounter_records(
    verified: VerifiedInputs,
    census: dict[str, Any],
    rosters: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    dll = verified.by_relative_path(_DLL_PATH)
    pck = verified.by_relative_path(_PCK_PATH)
    data, entry, info = read_selected(pck.path, _ENCOUNTER_LOCALIZATION)
    localization = strict_json_bytes(data, f"{_PCK_PATH}:{_ENCOUNTER_LOCALIZATION}")
    if not isinstance(localization, dict):
        raise SourceExtractionError("encounter localization top level must be an object")
    blob_sha256 = hashlib.sha256(data).hexdigest()
    roster_by_id = {
        item["canonicalId"]: item
        for kind in ("ordinary", "event")
        for item in rosters[kind]
    }
    encounters: dict[str, list[dict[str, Any]]] = {"event": [], "ordinary": []}
    for kind in ("ordinary", "event"):
        for source in census[kind]:
            canonical_id = source["canonicalId"]
            key = canonical_id + ".title"
            title = require_localized_text(localization, key)
            identity_witness = {
                "category": source["assemblyCategory"],
                "entry": canonical_id,
                "sourceType": source["sourceType"],
            }
            roster = roster_by_id.pop(canonical_id, None)
            if roster is None:
                raise SourceExtractionError(f"missing roster join for {canonical_id}")
            encounters[kind].append({
                "assemblyCategory": source["assemblyCategory"],
                "canonicalId": canonical_id,
                "initialRoster": roster["initialRoster"],
                "kind": kind,
                "nonRosterInitializationRng": roster["nonRosterInitializationRng"],
                "possibleMonsters": roster["possibleMonsters"],
                "possibleMonstersProvenance": roster["possibleMonstersProvenance"],
                "producedMonsters": roster["producedMonsters"],
                "producedMonstersProvenance": roster["producedMonstersProvenance"],
                "productionPools": roster["productionPools"],
                "provenance": {
                    "identity": {
                        "assemblySha256": dll.sha256,
                        "authority": "rawSource",
                        "diagnosticMetadataToken": source["diagnosticMetadataToken"],
                        "modelIdRule": "modelDb.typeToId.v0.111.0",
                        "semanticWitness": identity_witness,
                        "semanticWitnessSha256": witness_sha256(identity_witness),
                        "sourceType": source["sourceType"],
                    },
                    "title": {
                        "authority": "rawSource",
                        "entryMd5": entry.md5,
                        "entrySha256": blob_sha256,
                        "keyValueWitnessSha256": witness_sha256([key, title]),
                        "localizationKey": key,
                        "pckPath": _ENCOUNTER_LOCALIZATION,
                        "pckSha256": pck.sha256,
                    },
                },
                "rosterMethod": roster["rosterMethod"],
                "sourceType": source["sourceType"],
                "title": title,
            })
    if roster_by_id:
        raise SourceExtractionError(f"orphan roster records: {sorted(roster_by_id)!r}")
    return encounters, {
        "entryFlags": entry.flags,
        "entryMd5": entry.md5,
        "entrySha256": blob_sha256,
        "pckDirectoryOffset": info.directory_offset,
        "pckFileCount": info.file_count,
        "pckFormat": info.format,
        "pckGodotVersion": list(info.godot_version),
        "pckPath": _ENCOUNTER_LOCALIZATION,
        "pckSha256": pck.sha256,
    }


def build_artifact(verified: VerifiedInputs) -> bytes:
    dll = verified.by_relative_path(_DLL_PATH)
    pck = verified.by_relative_path(_PCK_PATH)
    assembly = AssemblyMetadata(dll.path)
    try:
        census = extract_encounter_census(dll.path, dll.sha256, assembly=assembly)
        placement = extract_placement(assembly, dll.sha256, census)
        ancient_l10n, ancient_l10n_blob = _localization(verified, _ANCIENT_LOCALIZATION)
        event_scripts = extract_event_scripts(
            assembly, dll.sha256, placement, ancient_l10n, ancient_l10n_blob
        )
        world = extract_monster_world(dll.path, dll.sha256, assembly=assembly)
        known_models = {"MONSTER." + item["canonicalId"] for item in world["concrete"]}
        rosters = extract_rosters(dll.path, dll.sha256, census, known_models, assembly=assembly)
        name_data = join_monster_names(
            world["concrete"], set(rosters["reachableModels"]), dll.path, dll.sha256,
            pck.path, pck.sha256, assembly=assembly
        )
        state_facts = extract_state_facts(dll.path, dll.sha256, assembly=assembly)
        observation_identities = extract_observation_identities(
            assembly, dll.sha256, world["concrete"], set(rosters["reachableModels"]), state_facts
        )
        hp_scaling = extract_hp_multiplayer_scaling(dll.path, dll.sha256, assembly=assembly)
        hp_pipeline = extract_hp_pipeline(assembly, dll.sha256)
        monster_l10n, monster_l10n_blob = _localization(verified, _MONSTER_LOCALIZATION)
        behavior = extract_behavior(assembly, dll.sha256, pck.sha256, world["concrete"],
                                    rosters["reachableModels"], monster_l10n,
                                    monster_l10n_blob["entrySha256"])
        behavior["scaling"] = extract_combat_scaling(assembly, dll.sha256)
        encounters, encounter_blob = _encounter_records(verified, census, rosters)
        initial_state = extract_initial_state(
            assembly, dll.sha256, world["concrete"], encounters["ordinary"] + encounters["event"],
            reachable_models=set(rosters["reachableModels"]), power_scaling=behavior["scaling"]["power"],
        )
        attach_event_turn_behavior(
            assembly, dll.sha256, behavior, encounters["event"], placement["eventLinkage"],
            initial_state, set(rosters["eventOnlyModels"]), monster_l10n, pck_sha256=pck.sha256,
            localization_blob_sha256=monster_l10n_blob["entrySha256"],
        )
        # Resolve the generic E2c1 scripted boundary only after the independently
        # validated Architect component exists. Lifecycle dependencies stay open.
        scripted_dependencies = [row for row in behavior["eventDependencies"]
                                 if row["kind"] == "scriptedEventSemantics"]
        if len(scripted_dependencies) != 1 or scripted_dependencies[0]["sourceType"] != event_scripts["architect"]["applicability"]["eventSourceType"]:
            raise SourceExtractionError("Architect scripted dependency/component join is ambiguous")
        scripted_dependencies[0]["status"] = "sourceComplete"
        scripted_dependencies[0]["resolvedComponentRef"] = "EVENT_SCRIPT_COMPONENT.THE_ARCHITECT"
        for move in behavior["registrations"]:
            for index, operation in enumerate(move["operations"]):
                validate_operation(operation, path=f"$.behavior.registrations[{move['canonicalId']!r}].operations[{index}]")
        intent_l10n, intent_l10n_blob = _localization(verified, _INTENT_LOCALIZATION)
        power_l10n, power_l10n_blob = _localization(verified, _POWER_LOCALIZATION)
        card_l10n, card_l10n_blob = _localization(verified, _CARD_LOCALIZATION)
        referenced = _referenced_models(behavior, initial_state, power_l10n, card_l10n, power_l10n_blob, card_l10n_blob)
    finally:
        assembly.close()
    reachable = set(rosters["reachableModels"])
    ordinary_reachable = set(rosters["ordinaryReachableModels"])
    event_only = set(rosters["eventOnlyModels"])

    excluded: list[dict[str, str]] = []
    expected_other = world["otherClassifications"]
    for record in world["concrete"]:
        model_ref = "MONSTER." + record["canonicalId"]
        record["provenance"]["identity"]["authority"] = "rawSource"
        if model_ref in ordinary_reachable:
            record["reachability"] = {"classification": "ordinaryReachable"}
        elif model_ref in event_only:
            record["reachability"] = {"classification": "eventOnly"}
        else:
            if record["canonicalId"] == "DEPRECATED_MONSTER":
                classification = "deprecatedPlaceholder"
            else:
                classification = expected_other.get(record["canonicalId"])
            if classification is None:
                raise SourceExtractionError(f"unclassified concrete monster {record['canonicalId']}")
            record["reachability"] = {"classification": classification}
            excluded.append({
                "canonicalId": record["canonicalId"],
                "classification": classification,
                "sourceType": record["sourceType"],
            })
    if len(excluded) != 12:
        raise SourceExtractionError(f"excluded concrete monster count drift: got {len(excluded)}")

    total_encounters = len(encounters["ordinary"]) + len(encounters["event"])

    artifact: dict[str, Any] = {
        "astGrammar": {
            "delegateBindingKinds": ["methodArgument", "null"],
            "expressionKinds": ["actRoomFactor", "arithmetic", "ascensionSelect", "combatQuery", "compare", "conditional", "constant", "convert", "range", "reference", "sourceField", "stateVariable"],
            "intentArgumentKinds": ["booleanConstant", "numericExpression", "sourceDelegate"],
            "graphEdgeKinds": ["conditionalBranch", "followUp", "randomBranch"],
            "graphNodeKinds": ["conditional", "move", "random"],
            "numericTypes": ["decimal", "integer", "integerRange"],
            "arithmeticOperators": ["add", "divide", "multiply", "remainder", "subtract"],
            "operationKinds": ["addGeneratedCard", "addStatusCard", "applyPower", "attack", "attackHitCount", "escape", "gainBlock", "heal", "helperEffect", "kill", "removeCard", "removePower", "stateWrite", "summon", "transition"],
            "rosterKinds": ["filteredChoice", "fixed", "permutation", "repeat", "sequence", "uniformChoice", "weightedChoice"],
            "rules": "docs/source-world-model.md#normalized-ast-grammar",
        },
        "authority": {
            "artifactTier": "rawSource",
            "fallbackPolicy": {
                "allowedFutureKinds": ["community", "empirical"],
                "conflictsMustBeExplicit": True,
                "requiredFutureFields": ["kind", "url", "pageRevisionOrRetrievalDate", "claimedGameVersion", "confidence", "status"],
                "silentMerge": False,
            },
        },
        "coverage": {
            "actCensus": complete(len(placement["acts"]), placement["sourceDenominators"]["acts"]),
            "behaviorGraphApplicability": complete(len(behavior["graphs"]), len(behavior["applicability"])),
            "behaviorOwnerApplicability": complete(len(behavior["applicability"]), len(behavior["graphs"])),
            "encounterPlacement": complete(len(placement["encounters"]), placement["sourceDenominators"]["currentEncounterPlacements"]),
            "eventEncounterLinkage": complete(len(placement["eventLinkage"]), placement["sourceDenominators"]["eventEncounterLinks"]),
            "eventTurnClassifications": complete(behavior["eventTurnSummary"]["classifications"], len(encounters["event"])),
            "eventTurnDependencyClassifications": complete(len(behavior["eventDependencies"]), len(behavior["eventDependencies"])),
            "eventTurnDirectOperations": complete(behavior["eventTurnSummary"]["eventTurnDirectOperations"], behavior["eventTurnSummary"]["eventTurnDirectOperations"]),
            "eventTurnIntentArguments": complete(behavior["eventTurnSummary"]["eventIntentArguments"], behavior["eventTurnSummary"]["eventIntentArguments"]),
            "eventTurnIntentClassification": complete(behavior["eventTurnSummary"]["eventIntentConstructorSites"], behavior["eventTurnSummary"]["eventIntentConstructorSites"]),
            "eventTurnInvocationClassification": complete(behavior["eventTurnInvocationCensus"]["summary"]["resolved"], behavior["eventTurnInvocationCensus"]["summary"]["denominator"]),
            "eventTurnNoOpProofs": complete(behavior["eventTurnSummary"]["noOpProofs"], behavior["eventTurnSummary"]["noOpProofs"]),
            "eventTurnOperations": complete(behavior["eventTurnSummary"]["eventTurnOperationsIncludingNoOpProofs"], behavior["eventTurnSummary"]["eventTurnOperationsIncludingNoOpProofs"]),
            "eventTurnPhysicalOwners": complete(behavior["eventTurnSummary"]["physicalOwners"], behavior["eventTurnSummary"]["physicalOwners"]),
            "eventTurnPhysicalRegistrations": complete(behavior["eventTurnSummary"]["physicalRegistrations"], behavior["eventTurnSummary"]["physicalRegistrations"]),
            "eventTurnPhysicalTitlesEnglish": complete(behavior["eventTurnSummary"]["physicalTitles"], behavior["eventTurnSummary"]["physicalTitles"]),
            "eventTurnReuseInheritanceApplicability": complete(behavior["eventTurnSummary"]["reuseOrInheritanceApplicability"], behavior["eventTurnSummary"]["reuseOrInheritanceApplicability"]),
            "eventScriptOwnerApplicability": complete(event_scripts["sourceDenominators"]["owners"], event_scripts["sourceDenominators"]["owners"]),
            "eventScriptEncounterLinks": complete(event_scripts["sourceDenominators"]["encounterScripts"], event_scripts["sourceDenominators"]["encounterScripts"]),
            "eventScriptOptionDelegates": complete(event_scripts["sourceDenominators"]["options"], event_scripts["sourceDenominators"]["options"]),
            "eventScriptEffectiveMethods": complete(event_scripts["sourceDenominators"]["methods"], event_scripts["sourceDenominators"]["methods"]),
            "eventScriptStateRuntimeContracts": complete(event_scripts["sourceDenominators"]["stateContracts"], event_scripts["sourceDenominators"]["stateContracts"]),
            "eventScriptTransitionArguments": complete(event_scripts["sourceDenominators"]["encounterScripts"], event_scripts["sourceDenominators"]["encounterScripts"]),
            "eventScriptNodes": complete(event_scripts["sourceDenominators"]["nodes"], event_scripts["sourceDenominators"]["nodes"]),
            "eventScriptEdges": complete(event_scripts["sourceDenominators"]["edges"], event_scripts["sourceDenominators"]["edges"]),
            "eventScriptSemanticEffects": complete(event_scripts["sourceDenominators"]["effects"], event_scripts["sourceDenominators"]["effects"]),
            "eventScriptInvocationClassification": complete(event_scripts["invocationCensus"]["summary"]["resolved"], event_scripts["invocationCensus"]["summary"]["denominator"]),
            "eventScriptDependencyRefs": complete(event_scripts["sourceDenominators"]["dependencies"], event_scripts["sourceDenominators"]["dependencies"]),
            "eventScriptDisplayScalingArguments": complete(event_scripts["sourceDenominators"]["displayScalingCalls"], event_scripts["sourceDenominators"]["displayScalingCalls"]),
            "eventScriptOutcomes": complete(event_scripts["sourceDenominators"]["outcomes"], event_scripts["sourceDenominators"]["outcomes"]),
            "eventScriptFrameworkClosure": complete(event_scripts["sourceDenominators"]["frameworkMethods"], event_scripts["sourceDenominators"]["frameworkMethods"]),
            "eventScriptSupportMethodClosure": complete(event_scripts["sourceDenominators"]["supportMethods"], event_scripts["sourceDenominators"]["supportMethods"]),
            "architectOwnerLinkPlacementApplicability": complete(1, 1),
            "architectLocalizationStructuralClosure": complete(event_scripts["architect"]["sourceDenominators"]["localizationKeys"], event_scripts["architect"]["sourceDenominators"]["localizationKeys"]),
            "architectDialogueTemplateCensus": complete(event_scripts["architect"]["sourceDenominators"]["templates"], event_scripts["architect"]["sourceDenominators"]["templates"]),
            "architectDialogueLineCensus": complete(event_scripts["architect"]["sourceDenominators"]["lines"], event_scripts["architect"]["sourceDenominators"]["lines"]),
            "architectOptionDelegateClosure": complete(event_scripts["architect"]["sourceDenominators"]["options"], event_scripts["architect"]["sourceDenominators"]["options"]),
            "architectLineControlNodes": complete(event_scripts["architect"]["sourceDenominators"]["nodes"], event_scripts["architect"]["sourceDenominators"]["nodes"]),
            "architectLineControlEdges": complete(event_scripts["architect"]["sourceDenominators"]["edges"], event_scripts["architect"]["sourceDenominators"]["edges"]),
            "architectVisualOnlyLayoutProof": complete(1, 1),
            "architectStateRuntimeInputContracts": complete(event_scripts["architect"]["sourceDenominators"]["runtimeContracts"], event_scripts["architect"]["sourceDenominators"]["runtimeContracts"]),
            "architectSemanticEffects": complete(event_scripts["architect"]["sourceDenominators"]["semanticEffects"], event_scripts["architect"]["sourceDenominators"]["semanticEffects"]),
            "architectTerminalSinkOrder": complete(1, 1),
            "architectPresentationOnlyClosure": complete(event_scripts["architect"]["sourceDenominators"]["presentationMethods"], event_scripts["architect"]["sourceDenominators"]["presentationMethods"]),
            "architectInvocationClassification": complete(event_scripts["architect"]["sourceDenominators"]["invocations"], event_scripts["architect"]["sourceDenominators"]["invocations"]),
            "architectDependencyRefs": complete(event_scripts["architect"]["sourceDenominators"]["dependencies"], event_scripts["architect"]["sourceDenominators"]["dependencies"]),
            "observableIdentityDomain": complete(len(observation_identities["entries"]), observation_identities["sourceDenominators"]["observableIds"]),
            "observableResourceRepresentations": complete(len(observation_identities["resourceRepresentations"]), observation_identities["sourceDenominators"]["resourceRepresentations"]),
            "observableStateContracts": complete(len(observation_identities["stateObservationContracts"]), observation_identities["sourceDenominators"]["stateObservationContracts"]),
            "poolCensus": complete(len(placement["pools"]), placement["sourceDenominators"]["pools"]),
            "poolMemberships": complete(sum(len(row["canonicalMembers"]) for row in placement["pools"]), placement["sourceDenominators"]["poolRegistryMembers"]),
            "placementMemberships": complete(sum(len(row["memberships"]) for row in placement["encounters"]), placement["sourceDenominators"]["currentEncounterMemberships"]),
            "moveRegistrationApplicability": complete(len(behavior["registrations"]), len(behavior["registrations"])),
            "encounterIdentities": complete(total_encounters, 89),
            "encounterPossibleMembership": complete(total_encounters, 89),
            "encounterProductionMembership": complete(total_encounters, 89),
            "encounterRosters": complete(total_encounters, 89),
            "encounterTitlesEnglish": complete(total_encounters, 89),
            "hpInitialConcreteCensus": complete(len(world["hpGetterCensus"]), 120),
            "hpInitialCurrentReachable": complete(len(reachable), 108),
            "hpMultiplayerScaling": complete(1, 1),
            "hpBaseSelectionUniqueValueChain": complete(hp_pipeline["sourceDenominators"]["baseSelectionChainMethods"], hp_pipeline["sourceDenominators"]["baseSelectionChainMethods"]),
            "hpMultiplayerWrapperHelperCallClosure": complete(hp_pipeline["sourceDenominators"]["multiplayerWrapperHelperCallSites"], hp_pipeline["sourceDenominators"]["multiplayerWrapperHelperCallSites"]),
            "hpAssignmentSetterCensus": complete(hp_pipeline["sourceDenominators"]["setterMethodsAndDirectCallSites"], hp_pipeline["sourceDenominators"]["setterMethodsAndDirectCallSites"]),
            "hpCommandSpecialCallerApplicability": complete(hp_pipeline["sourceDenominators"]["commandAndSpecialCallerApplicability"], hp_pipeline["sourceDenominators"]["commandAndSpecialCallerApplicability"]),
            "hpCapClampPreconditionSemanticFields": complete(hp_pipeline["sourceDenominators"]["capClampPreconditionSemanticFields"], hp_pipeline["sourceDenominators"]["capClampPreconditionSemanticFields"]),
            "hpStorageNetworkSerializationJoins": complete(hp_pipeline["sourceDenominators"]["storageAndNetworkSerializationJoins"], hp_pipeline["sourceDenominators"]["storageAndNetworkSerializationJoins"]),
            "hpCompletePipelineSemanticFields": complete(hp_pipeline["sourceDenominators"]["completePipelineSemanticFields"], hp_pipeline["sourceDenominators"]["completePipelineSemanticFields"]),
            "hpSpecialStateFormulas": complete(4, 4),
            "monsterIdentitiesCurrentReachable": complete(len(reachable), 108),
            "monsterNamesEnglishCurrentReachable": complete(name_data["joinedCount"], 108),
            "monsterNamespaceCensus": complete(121, 121),
            "blockMultiplayerScaling": complete(1, 1),
            "moveActions": complete(behavior["summary"]["asyncActions"] + behavior["summary"]["synchronousNoOpActions"], 315),
            "moveIntentArguments": complete(behavior["summary"]["resolvedIntentArguments"], behavior["summary"]["requiredIntentArguments"]),
            "moveIntentClassification": complete(behavior["summary"]["resolvedIntentConstructorSites"], behavior["summary"]["intentConstructorSites"]),
            "moveOperations": complete(len(behavior["registrations"]), 315),
            "moveRegistrationCensus": complete(len(behavior["registrations"]), 315),
            "moveSelectionGraphs": complete(len(behavior["graphs"]), 105),
            "moveTitleClassification": complete(len(behavior["registrations"]), 315),
            "moveTitlesEnglish": {"denominator": 315, "numerator": behavior["summary"]["localizedTitles"], "status": "classified", "unresolved": 18},
            "invocationClassification": complete(behavior["invocationCensus"]["summary"]["resolved"], behavior["invocationCensus"]["summary"]["denominator"]),
            "operationDirectSinks": complete(behavior["summary"]["directSinkSites"], 497),
            "operationSemanticFields": complete(behavior["summary"]["resolvedSemanticFields"], behavior["summary"]["requiredSemanticFields"]),
            "operationDirectSinksByKind": {
                kind: complete(count, count)
                for kind, count in behavior["summary"]["directSinkCounts"].items()
            },
            "encounterInitializers": complete(len(initial_state["encounterInitializers"]), 89),
            "initialStateOwners": complete(len(initial_state["initialStateOwners"]), 108),
            "initialStateEffectiveHooks": complete(len(initial_state["initialStateOwners"]), 108),
            "initialStateDirectSinkSites": complete(sum(initial_state["sourceDenominators"]["directSinkSitesByKind"].values()), sum(initial_state["sourceDenominators"]["directSinkSitesByKind"].values())),
            "initialStateTransitiveInvocationClassification": complete(len(initial_state["invocationDecisions"]), len(initial_state["invocationDecisions"])),
            "initialStatePowerHookClosure": complete(len(initial_state["powerHookClosure"]), len(initial_state["powerHookClosure"])),
            "initialExternalHookBoundary": complete(sum(len(row["declarations"]) for row in initial_state["externalHookBoundary"]), sum(len(row["declarations"]) for row in initial_state["externalHookBoundary"])),
            "initialStateSemanticFields": complete(len(initial_state["initialStateFacts"]) * 14, len(initial_state["initialStateFacts"]) * 14),
            "powerCardReferencedModels": complete(len(referenced["powers"]) + len(referenced["cards"]), len(referenced["powers"]) + len(referenced["cards"])),
            "powerMultiplayerOptIns": complete(len(behavior["scaling"]["power"]["optIns"]), 12),
            "powerMultiplayerOverrides": complete(len(behavior["scaling"]["power"]["overrides"]), 5),
        },
        "behavior": behavior,
        "cards": referenced["cards"],
        "hpPipeline": hp_pipeline,
        "initialState": initial_state,
        "eventScripts": event_scripts,
        "intentLocalization": {"entries": intent_l10n, "provenance": intent_l10n_blob},
        "powers": referenced["powers"],
        "encounterCensus": {
            "abstractTypes": census["abstractTypes"],
            "counts": {
                "abstract": len(census["abstractTypes"]),
                "currentEvent": len(encounters["event"]),
                "currentOrdinary": len(encounters["ordinary"]),
                "currentTotal": total_encounters,
                "deprecatedPlaceholder": len(census["deprecatedPlaceholderTypes"]),
            },
            "deprecatedPlaceholderTypes": census["deprecatedPlaceholderTypes"],
        },
        "encounters": encounters,
        "extractorVersion": EXTRACTOR_VERSION,
        "game": {
            "branch": verified.release["branch"],
            "commit": verified.release["commit"],
            "mainAssemblyHash": verified.release["main_assembly_hash"],
            "version": verified.release["version"],
        },
        "inputs": [
            {"path": item.relative_path, "sha256": item.sha256, "size": item.size}
            for item in sorted(verified.files, key=lambda value: value.relative_path)
        ],
        "monsterCensus": {
            "abstractTypes": world["abstractTypes"],
            "counts": {
                "abstract": 1,
                "concrete": len(world["concrete"]),
                "eventOnlyReachable": len(event_only),
                "excludedConcrete": len(excluded),
                "namespaceTotal": len(world["concrete"]) + len(world["abstractTypes"]),
                "ordinaryReachable": len(ordinary_reachable),
                "totalReachable": len(reachable),
            },
            "excludedConcrete": sorted(excluded, key=lambda item: item["canonicalId"]),
            "hpGetterCensus": world["hpGetterCensus"],
        },
        "monsters": world["concrete"],
        "observationIdentities": observation_identities,
        "placement": placement,
        "multiplayerScaling": {"block": behavior["scaling"]["block"], "hp": hp_scaling, "power": behavior["scaling"]["power"], "ordinaryMonsterAttack": behavior["scaling"]["ordinaryMonsterAttack"]},
        "provenance": {
            "assemblyRules": {"modelDb.typeToId.v0.111.0": census["modelIdRule"]},
            "localizationBlobs": {
                "encountersEnglish": encounter_blob,
                "monstersEnglish": name_data["localizationBlob"],
                "moveMonstersEnglish": monster_l10n_blob,
                "intentsEnglish": intent_l10n_blob,
                "powersEnglish": power_l10n_blob,
                "cardsEnglish": card_l10n_blob,
                "ancientsEnglishStructural": ancient_l10n_blob,
            },
            "titleRules": name_data["titleRules"],
            "witnessCanonicalization": "SHA-256 of UTF-8 RFC 8259 JSON with object keys sorted, no insignificant whitespace, and non-ASCII preserved",
        },
        "reachability": {
            "eventOnlyModels": rosters["eventOnlyModels"],
            "eventReachableModels": rosters["eventReachableModels"],
            "ordinaryReachableModels": rosters["ordinaryReachableModels"],
            "reachableModels": rosters["reachableModels"],
        },
        "runtimeReady": False,
        "safety": {
            "assemblyExecution": False,
            "cilExecution": False,
            "godotInitialization": False,
            "mode": "metadataAndBoundedCilAnalysis",
            "pckAccess": "readOnlySelective",
            "reflectionLoading": False,
        },
        "schemaVersion": SCHEMA_VERSION,
        "states": {
            **state_facts,
            "hatchlingName": name_data["hatchlingName"],
        },
        "status": "incomplete",
    }
    return canonical_json_bytes(artifact)
