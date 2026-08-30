"""Closed C0 encounter projection contract and pinned v0.111.0 identities."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
GENERATOR_NAME = "sts2-encounter-facts"
GENERATOR_VERSION = "1.0.0"
SOURCE_SCHEMA_VERSION = 4
SOURCE_EXTRACTOR_VERSION = "4.0.0"

SOURCE_ARTIFACT = {
    "id": "INPUT.SOURCE", "path": "data/game-v0.111.0-source.json",
    "sha256": "a03e4213a7aa173f7379656e78ee3f45a9cb42b7cd73ff0287be3bb064811131", "size": 8721864,
}
LEGACY_ARTIFACT = {
    "id": "INPUT.LEGACY", "path": "data/encounters.json",
    "sha256": "0c01dd0b851c501acea59fb41b10a828030ad2c3e63f9fc624f98b6e403e0103", "size": 170154,
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
    "observedRuntimeIdentity": "contractOnlyNotPopulated",
    "projectionPatchPolicy": {"artifactTier": "raw-only", "kind": "none"},
    "silentMerge": False, "sourceFacts": "rawSource",
}
# family -> (status, denominator, numerator, unresolved); reviewed constants,
# never values learned from the document being validated.
REQUIRED_COVERAGE: dict[str, tuple[str, int, int, int]] = {
    "blockMultiplayerScaling": ("complete", 1, 1, 0),
    "encounterIdentities": ("complete", 89, 89, 0),
    "encounterPossibleMembership": ("complete", 89, 89, 0),
    "encounterProductionMembership": ("complete", 89, 89, 0),
    "encounterRosters": ("complete", 89, 89, 0),
    "encounterTitlesEnglish": ("complete", 89, 89, 0),
    "hpInitialCurrentReachable": ("complete", 108, 108, 0),
    "hpMultiplayerScaling": ("complete", 1, 1, 0),
    "hpSpecialStateFormulas": ("complete", 4, 4, 0),
    "invocationClassification": ("complete", 6683, 6683, 0),
    "monsterIdentitiesCurrentReachable": ("complete", 108, 108, 0),
    "monsterNamesEnglishCurrentReachable": ("complete", 108, 108, 0),
    "moveActions": ("complete", 307, 307, 0),
    "moveIntentArguments": ("complete", 311, 311, 0),
    "moveIntentClassification": ("complete", 387, 387, 0),
    "moveOperations": ("complete", 307, 307, 0),
    "moveRegistrationCensus": ("complete", 307, 307, 0),
    "moveSelectionGraphs": ("complete", 100, 100, 0),
    "moveTitleClassification": ("complete", 307, 307, 0),
    "moveTitlesEnglish": ("classified", 307, 289, 18),
    "operationDirectSinks": ("complete", 491, 491, 0),
    "operationSemanticFields": ("complete", 1081, 1081, 0),
    "powerCardReferencedModels": ("complete", 52, 52, 0),
    "powerMultiplayerOptIns": ("complete", 12, 12, 0),
    "powerMultiplayerOverrides": ("complete", 5, 5, 0),
}
for _kind, _count in {
    "addGeneratedCard": 6, "addStatusCard": 14, "applyPower": 126, "attack": 204,
    "attackHitCount": 49, "escape": 2, "gainBlock": 23, "heal": 2, "kill": 2,
    "removeCard": 1, "removePower": 6, "stateWrite": 51, "summon": 5,
}.items():
    REQUIRED_COVERAGE[f"operationDirectSinksByKind.{_kind}"] = ("complete", _count, _count, 0)

INTENT_KINDS = {"attack", "block", "buff", "cardDebuff", "deathBlow", "debuff", "escape", "heal", "sleep", "status", "stun", "summon"}
ROOT_KEYS = {"authority", "metadata", "payload", "schemaVersion"}
METADATA_KEYS = {
    "embeddedSourceInputManifest", "embeddedSourceInputManifestSha256", "game", "generator",
    "payloadSha256", "projectionInputs", "requiredCoverage", "sourceExtractorVersion", "sourceSchemaVersion",
}
PAYLOAD_KEYS = {"conflicts", "evidence", "factReferences", "knownUnknowns", "laneComparisons", "legacyAnnotations", "readiness", "sourceFacts"}
SOURCE_FACT_KEYS = {"behaviorOwners", "encounters", "graphs", "models", "monsters", "moves", "scaling", "stateRules", "states"}


def coverage_rows() -> list[dict[str, Any]]:
    return [
        {"denominator": d, "family": family, "numerator": n, "status": status, "unresolved": u}
        for family, (status, d, n, u) in sorted(REQUIRED_COVERAGE.items())
    ]
