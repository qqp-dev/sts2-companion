"""Closed E2 lifecycle encounter projection contract and pinned v0.111.0 identities."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 11
GENERATOR_NAME = "sts2-encounter-facts"
GENERATOR_VERSION = "11.1.0"
SOURCE_SCHEMA_VERSION = 14
SOURCE_EXTRACTOR_VERSION = "14.0.0"

SOURCE_ARTIFACT = {
    "id": "INPUT.SOURCE", "path": "data/game-v0.111.0-source.json",
    "sha256": "2991f0391565f384453bdb009050f9cd53a0f4949e86b92adf73e0fe928e559e", "size": 17054697,
}
LEGACY_ARTIFACT = {
    "id": "INPUT.LEGACY", "path": "data/encounters.json",
    "sha256": "91161c59e780329371c930a01d3ae8916becc3c6dfa4574e9692c8a21c398df3", "size": 177972,
}
PROJECTION_INPUTS = [SOURCE_ARTIFACT, LEGACY_ARTIFACT]
GAME = {"branch": "v0.111.0", "commit": "41cef1ea", "mainAssemblyHash": 1579942752, "version": "v0.111.0"}
EMBEDDED_SOURCE_INPUTS = [
    {"path": "SlayTheSpire2.pck", "sha256": "42443027622a6a82de8ab21e81ed5b68e522c0f5647fb6a26a74c4a0970a0d34", "size": 1990363992},
    {"path": "data_sts2_linuxbsd_x86_64/sts2.dll", "sha256": "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f", "size": 9756160},
    {"path": "data_sts2_linuxbsd_x86_64/sts2.xml", "sha256": "a88331870d38cdb84d8fc371ab3d7fb619afa25c8c7249a47aaa77e1c7bf4286", "size": 5650972},
    {"path": "release_info.json", "sha256": "9e5dbce5bcd8ff3b7b432291200220642408e31b8bae7bba14f39aeb6914cd51", "size": 150},
]
SOURCE_AUTHORITY = {
    "artifactTier": "rawSource",
    "fallbackPolicy": {
        "allowedFutureKinds": ["community", "empirical"], "conflictsMustBeExplicit": True,
        "requiredFutureFields": ["kind", "url", "pageRevisionOrRetrievalDate", "claimedGameVersion", "confidence", "status"],
        "silentMerge": False,
    },
}
AUTHORITY = {
    "conflictPolicy": "explicitNoPrecedence", "legacyAnnotations": "legacyCommunityAnnotation",
    "observedRuntimeIdentity": "sourceDerivedAdapterVocabularyNoObservedSamples",
    "projectionPatchPolicy": {"artifactTier": "raw-only", "kind": "none"},
    "silentMerge": False, "sourceFacts": "rawSource",
    "stableLegacyConsumer": "historicalImplementationAuditOnly",
}
# family -> (status, denominator, numerator, unresolved); reviewed constants,
# never values learned from the document being validated.
REQUIRED_COVERAGE: dict[str, tuple[str, int, int, int]] = {
    "architectDependencyRefs": ("complete", 5, 5, 0),
    "architectDialogueLineCensus": ("complete", 39, 39, 0),
    "architectDialogueTemplateCensus": ("complete", 17, 17, 0),
    "architectInvocationClassification": ("complete", 715, 715, 0),
    "architectLineControlEdges": ("complete", 39, 39, 0),
    "architectLineControlNodes": ("complete", 39, 39, 0),
    "architectLocalizationStructuralClosure": ("complete", 64, 64, 0),
    "architectOptionDelegateClosure": ("complete", 2, 2, 0),
    "architectOwnerLinkPlacementApplicability": ("complete", 1, 1, 0),
    "architectPresentationOnlyClosure": ("complete", 13, 13, 0),
    "architectSemanticEffects": ("complete", 6, 6, 0),
    "architectStateRuntimeInputContracts": ("complete", 8, 8, 0),
    "architectTerminalSinkOrder": ("complete", 1, 1, 0),
    "architectVisualOnlyLayoutProof": ("complete", 1, 1, 0),
    "actCensus": ("complete", 4, 4, 0),
    "behaviorGraphApplicability": ("complete", 105, 105, 0),
    "behaviorOwnerApplicability": ("complete", 105, 105, 0),
    "blockMultiplayerScaling": ("complete", 1, 1, 0),
    "coreLifecycleComponent": ("complete", 1, 1, 0),
    "lifecycleCommandDeclarations": ("complete", 4, 4, 0),
    "lifecycleCommandPhysicalBodies": ("complete", 4, 4, 0),
    "lifecycleKillCallSites": ("complete", 21, 21, 0),
    "lifecycleEscapeCallSites": ("complete", 3, 3, 0),
    "lifecycleDispatchMethods": ("complete", 6, 6, 0),
    "lifecycleListenerRegistryMethods": ("complete", 6, 6, 0),
    "lifecycleRemovalMethods": ("complete", 4, 4, 0),
    "lifecycleTerminationMethods": ("complete", 11, 11, 0),
    "lifecycleCentralizedCheckSites": ("complete", 14, 14, 0),
    "lifecycleRuntimeBoundaries": ("complete", 7, 7, 0),
    "lifecycleDependencies": ("complete", 7, 7, 0),
    "lifecycleInvocationClassification": ("complete", 707, 707, 0),
    "lifecycleSemanticNodes": ("complete", 59, 59, 0),
    "lifecycleReachableListenerOwners": ("complete", 108, 108, 0),
    "lifecyclePowerSeedTypes": ("complete", 69, 69, 0),
    "lifecycleFixedPointPowerTypes": ("complete", 71, 71, 0),
    "lifecycleEffectiveListenerApplications": ("complete", 1861, 1861, 0),
    "lifecycleListenerImplementations": ("complete", 80, 80, 0),
    "lifecyclePhaseSystems": ("complete", 6, 6, 0),
    "lifecycleRelationships": ("complete", 6, 6, 0),
    "lifecycleSubscriptions": ("complete", 3, 3, 0),
    "lifecycleBeforeRemovedCleanup": ("complete", 11, 11, 0),
    "lifecycleDeathAddSites": ("complete", 4, 4, 0),
    "lifecycleDeathProductionSystems": ("complete", 3, 3, 0),
    "lifecycleEventCombatRegistrations": ("complete", 7, 7, 0),
    "lifecycleRunTerminationSystems": ("complete", 1, 1, 0),
    "lifecycleCloseoutInvocationClassification": ("complete", 1265, 1265, 0),
    "encounterPlacement": ("complete", 89, 89, 0),
    "eventEncounterLinkage": ("complete", 8, 8, 0),
    "eventTurnClassifications": ("complete", 8, 8, 0),
    "eventTurnDependencyClassifications": ("complete", 4, 4, 0),
    "eventTurnDirectOperations": ("complete", 6, 6, 0),
    "eventTurnIntentArguments": ("complete", 5, 5, 0),
    "eventTurnIntentClassification": ("complete", 6, 6, 0),
    "eventTurnInvocationClassification": ("complete", 103, 103, 0),
    "eventTurnNoOpProofs": ("complete", 4, 4, 0),
    "eventTurnOperations": ("complete", 10, 10, 0),
    "eventTurnPhysicalOwners": ("complete", 5, 5, 0),
    "eventTurnPhysicalRegistrations": ("complete", 8, 8, 0),
    "eventTurnPhysicalTitlesEnglish": ("complete", 8, 8, 0),
    "eventTurnReuseInheritanceApplicability": ("complete", 3, 3, 0),
    "eventScriptDependencyRefs": ("complete", 6, 6, 0),
    "eventScriptDisplayScalingArguments": ("complete", 3, 3, 0),
    "eventScriptEdges": ("complete", 20, 20, 0),
    "eventScriptEffectiveMethods": ("complete", 76, 76, 0),
    "eventScriptEncounterLinks": ("complete", 7, 7, 0),
    "eventScriptFrameworkClosure": ("complete", 53, 53, 0),
    "eventScriptInvocationClassification": ("complete", 1549, 1549, 0),
    "eventScriptNodes": ("complete", 25, 25, 0),
    "eventScriptOptionDelegates": ("complete", 12, 12, 0),
    "eventScriptOutcomes": ("complete", 7, 7, 0),
    "eventScriptOwnerApplicability": ("complete", 5, 5, 0),
    "eventScriptSemanticEffects": ("complete", 10, 10, 0),
    "eventScriptStateRuntimeContracts": ("complete", 10, 10, 0),
    "eventScriptSupportMethodClosure": ("complete", 14, 14, 0),
    "eventScriptTransitionArguments": ("complete", 7, 7, 0),
    "randomBranchOverloadClosure": ("complete", 10, 10, 0),
    "randomBranchRepeatWeightSemantics": ("complete", 61, 61, 0),
    "randomWeightCallbackClosure": ("complete", 8, 8, 0),
    "randomSelectionRuntimeContract": ("complete", 3, 3, 0),
    "productionAddApiCensus": ("complete", 14, 14, 0),
    "productionOstyApiCensus": ("complete", 17, 17, 0),
    "productionOwnerRootDiscovery": ("complete", 7, 7, 0),
    "productionHelperCallClosure": ("complete", 5, 5, 0),
    "productionDirectSiteDiscovery": ("complete", 6, 6, 0),
    "productionOwnerEncounterApplicability": ("complete", 6, 6, 0),
    "productionProducerSemantics": ("complete", 7, 7, 0),
    "productionPoolSemantics": ("complete", 7, 7, 0),
    "productionCandidateEntries": ("complete", 9, 9, 0),
    "productionSlotPolicies": ("complete", 6, 6, 0),
    "productionCandidateRngSelection": ("complete", 1, 1, 0),
    "productionPostAddEffects": ("complete", 4, 4, 0),
    "productionRuntimeStateContracts": ("complete", 12, 12, 0),
    "productionDependencyRefs": ("complete", 4, 4, 0),
    "coreAddOverloadClosure": ("complete", 3, 3, 0),
    "coreAddMethodClosure": ("complete", 6, 6, 0),
    "coreAddSemanticFieldClosure": ("complete", 11, 11, 0),
    "moveRegistrationApplicability": ("complete", 315, 315, 0),
    "observableIdentityDomain": ("complete", 108, 108, 0),
    "observableResourceRepresentations": ("complete", 108, 108, 0),
    "observableStateContracts": ("complete", 8, 8, 0),
    "placementMemberships": ("complete", 90, 90, 0),
    "poolCensus": ("complete", 20, 20, 0),
    "poolMemberships": ("complete", 192, 192, 0),
    "encounterIdentities": ("complete", 89, 89, 0),
    "encounterPossibleMembership": ("complete", 89, 89, 0),
    "encounterProductionMembership": ("complete", 89, 89, 0),
    "encounterRosters": ("complete", 89, 89, 0),
    "encounterTitlesEnglish": ("complete", 89, 89, 0),
    "hpInitialCurrentReachable": ("complete", 108, 108, 0),
    "hpMultiplayerScaling": ("complete", 1, 1, 0),
    "hpAssignmentSetterCensus": ("complete", 11, 11, 0),
    "hpBaseSelectionUniqueValueChain": ("complete", 4, 4, 0),
    "hpCapClampPreconditionSemanticFields": ("complete", 8, 8, 0),
    "hpCommandSpecialCallerApplicability": ("complete", 52, 52, 0),
    "hpCompletePipelineSemanticFields": ("complete", 85, 85, 0),
    "hpMultiplayerWrapperHelperCallClosure": ("complete", 9, 9, 0),
    "hpStorageNetworkSerializationJoins": ("complete", 10, 10, 0),
    "hpSpecialStateFormulas": ("complete", 4, 4, 0),
    "encounterInitializers": ("complete", 89, 89, 0),
    "initialStateOwners": ("complete", 108, 108, 0),
    "initialStateEffectiveHooks": ("complete", 108, 108, 0),
    "initialStateDirectSinkSites": ("complete", 57, 57, 0),
    "initialStateTransitiveInvocationClassification": ("complete", 1092, 1092, 0),
    "initialStatePowerHookClosure": ("complete", 41, 41, 0),
    "initialExternalHookBoundary": ("complete", 29, 29, 0),
    "initialStateSemanticFields": ("complete", 1554, 1554, 0),
    "invocationClassification": ("complete", 6786, 6786, 0),
    "monsterIdentitiesCurrentReachable": ("complete", 108, 108, 0),
    "monsterNamesEnglishCurrentReachable": ("complete", 108, 108, 0),
    "moveActions": ("complete", 315, 315, 0),
    "moveIntentArguments": ("complete", 316, 316, 0),
    "moveIntentClassification": ("complete", 393, 393, 0),
    "moveOperations": ("complete", 315, 315, 0),
    "moveRegistrationCensus": ("complete", 315, 315, 0),
    "moveSelectionGraphs": ("complete", 105, 105, 0),
    "moveTitleClassification": ("complete", 315, 315, 0),
    "moveTitlesEnglish": ("classified", 315, 297, 18),
    "operationDirectSinks": ("complete", 497, 497, 0),
    "operationSemanticFields": ("complete", 1094, 1094, 0),
    "powerCardReferencedModels": ("complete", 78, 78, 0),
    "powerMultiplayerOptIns": ("complete", 12, 12, 0),
    "powerMultiplayerOverrides": ("complete", 5, 5, 0),
}
for _kind, _count in {
    "addGeneratedCard": 6, "addStatusCard": 14, "applyPower": 128, "attack": 207,
    "attackHitCount": 50, "escape": 2, "gainBlock": 23, "heal": 2, "kill": 2,
    "removeCard": 1, "removePower": 6, "stateWrite": 51, "summon": 5,
}.items():
    REQUIRED_COVERAGE[f"operationDirectSinksByKind.{_kind}"] = ("complete", _count, _count, 0)

INTENT_KINDS = {"attack", "block", "buff", "cardDebuff", "deathBlow", "debuff", "escape", "heal", "hidden", "sleep", "status", "stun", "summon"}
ROOT_KEYS = {"authority", "metadata", "payload", "schemaVersion"}
METADATA_KEYS = {
    "embeddedSourceInputManifest", "embeddedSourceInputManifestSha256", "game", "generator",
    "payloadSha256", "projectionInputs", "requiredCoverage", "sourceExtractorVersion", "sourceSchemaVersion",
}
PAYLOAD_KEYS = {"conflicts", "evidence", "factReferences", "knownUnknowns", "laneComparisons", "legacyAnnotations", "readiness", "resolvedAudits", "sourceFacts"}
SOURCE_FACT_KEYS = {"behaviorOwners", "encounters", "graphs", "models", "monsters", "moves", "observationIdentities", "placement", "scaling", "stateRules", "states", "initialState", "hpPipeline", "eventTurnBehavior", "eventScripts", "randomSelection", "production", "lifecycle"}


def coverage_rows() -> list[dict[str, Any]]:
    return [
        {"denominator": d, "family": family, "numerator": n, "status": status, "unresolved": u}
        for family, (status, d, n, u) in sorted(REQUIRED_COVERAGE.items())
    ]
