"""Read-only PE/CLI metadata and resolved-CIL access for the pinned assembly.

This module uses dnfile and dncil to parse metadata tables and method bytes. It
never calls Assembly.Load, reflection APIs, game methods, or a CIL runtime.
Bounded semantic evaluators consume its normalized records in sibling modules.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import dnfile
from dncil.cil.body.reader import read_method_body_from_bytes

from .canonical import slugify_ascii_type_name as _slugify_ascii_type_name, witness_sha256
from .errors import SourceExtractionError

_ENCOUNTER_NAMESPACE = "MegaCrit.Sts2.Core.Models.Encounters"
_ENCOUNTER_BASE = "MegaCrit.Sts2.Core.Models.EncounterModel"
_ABSTRACT_MODEL = "MegaCrit.Sts2.Core.Models.AbstractModel"
_EVENT_BASE = f"{_ENCOUNTER_NAMESPACE}.BattlewornDummyEventEncounter"
_DEPRECATED = f"{_ENCOUNTER_NAMESPACE}.DeprecatedEncounter"
_EXPECTED_ABSTRACT = {_EVENT_BASE}
_EXPECTED_DEPRECATED = {_DEPRECATED}
_EXPECTED_COUNTS = {"ordinary": 81, "event": 8, "abstract": 1, "deprecated": 1}
_REQUIRED_CONCRETE_METHODS = {"get_AllPossibleMonsters", "GenerateMonsters"}

# These hashes are version assertions and rule recognizers, not generated IDs.
# methodBodySha256 covers the method header + CIL code bytes from dncil.raw_bytes.
_METHOD_RULES = (
    {
        "owner": "MegaCrit.Sts2.Core.Models.ModelDb",
        "name": "GetCategoryType",
        "metadataSignature": "000112451245",
        "symbolSignature": "System.Type MegaCrit.Sts2.Core.Models.ModelDb::GetCategoryType(System.Type)",
        "methodBodySha256": "7332f8f32f88163ca2b64d749c8f12d9bf56198c6b1e0335850711191a24c25d",
        "cilInstructionsSha256": "fbeb0f51fecc656f7302dac48ae55761a9ecaab33761a720f6ea1eaed7cd2561",
    },
    {
        "owner": "MegaCrit.Sts2.Core.Models.ModelDb",
        "name": "GetCategory",
        "metadataSignature": "00010e1245",
        "symbolSignature": "System.String MegaCrit.Sts2.Core.Models.ModelDb::GetCategory(System.Type)",
        "methodBodySha256": "036cff84f4cc7dacde67cf4554811c9888cc9ceff16ab3f2a759cf6ff7bf3982",
        "cilInstructionsSha256": "6c26ee37003c9a958d93bc76f274273f7aa553e1ea31d600a5a97d19bc8e0f6b",
    },
    {
        "owner": "MegaCrit.Sts2.Core.Models.ModelDb",
        "name": "GetEntry",
        "metadataSignature": "00010e1245",
        "symbolSignature": "System.String MegaCrit.Sts2.Core.Models.ModelDb::GetEntry(System.Type)",
        "methodBodySha256": "9dd81afe5c97577a6cf8c243ff15f4962821423846e813c18a14e79ada5bd044",
        "cilInstructionsSha256": "1829813b6b66ed8e189646c867123990af3ebd33dc8a49a7442dd6eed4f137b3",
    },
    {
        "owner": "MegaCrit.Sts2.Core.Models.ModelId",
        "name": "SlugifyCategory",
        "metadataSignature": "00010e0e",
        "symbolSignature": "System.String MegaCrit.Sts2.Core.Models.ModelId::SlugifyCategory(System.String)",
        "methodBodySha256": "01793ece8c9e885a1a8d61b987a0dd3acb6c55af039894f8befe95fce39d561d",
        "cilInstructionsSha256": "5ba5220f0dc80bd85beda49c7c5baeb4caadd9c7bf46cbd64a05d2c6dd8a1daf",
    },
    {
        "owner": "MegaCrit.Sts2.Core.Helpers.StringHelper",
        "name": "Slugify",
        "metadataSignature": "00010e0e",
        "symbolSignature": "System.String MegaCrit.Sts2.Core.Helpers.StringHelper::Slugify(System.String)",
        "methodBodySha256": "84f528b6ccc8e2850a32c27108d0bbeb64394625a886c8f07539dbc456760514",
        "cilInstructionsSha256": "8acf2667bce35b850c72bbff8715232cc4267c29b22da80b36d161012c49cc29",
    },
)

_MODEL_ID_WITNESS = (
    "categoryType = first base type whose base is AbstractModel; "
    "category = Slugify(categoryType.Name), then remove trailing _MODEL; "
    "entry = Slugify(concreteType.Name); ModelId(category, entry); "
    "Slugify = trim, split ASCII lower-or-digit/upper camel boundaries with _, "
    "uppercase invariant, replace whitespace with _, remove special characters"
)


class AssemblyMetadata:
    def __init__(self, path: Path):
        try:
            self.pe = dnfile.dnPE(str(path))
        except Exception as exc:
            raise SourceExtractionError(f"cannot parse sts2.dll PE/CLI metadata: {exc}") from exc
        if self.pe.net is None or self.pe.net.mdtables is None:
            raise SourceExtractionError("sts2.dll has no readable CLI metadata tables")
        self.md = self.pe.net.mdtables
        required = ("TypeDef", "TypeRef", "NestedClass", "MethodDef")
        missing = [name for name in required if not hasattr(self.md, name)]
        if missing:
            raise SourceExtractionError(
                "sts2.dll is missing required metadata tables: " + ", ".join(missing)
            )

        self._typedef_index = {
            id(row): index for index, row in enumerate(self.md.TypeDef.rows, 1)
        }
        self._nested = {
            row.NestedClass.row_index: row.EnclosingClass.row_index
            for row in self.md.NestedClass.rows
        }
        self.type_names: dict[int, str] = {}

        def type_name(index: int, active: frozenset[int] = frozenset()) -> str:
            if index in self.type_names:
                return self.type_names[index]
            if index in active:
                raise SourceExtractionError("cycle in nested TypeDef metadata")
            row = self.md.TypeDef.rows[index - 1]
            simple = str(row.TypeName)
            namespace = str(row.TypeNamespace)
            if index in self._nested:
                full = type_name(self._nested[index], active | {index}) + "+" + simple
            else:
                full = (namespace + "." if namespace else "") + simple
            self.type_names[index] = full
            return full

        for index in range(1, len(self.md.TypeDef.rows) + 1):
            type_name(index)

        self.method_owner = {
            method.row_index: type_index
            for type_index, type_row in enumerate(self.md.TypeDef.rows, 1)
            for method in type_row.MethodList
        }
        self.field_owner = {
            field.row_index: type_index
            for type_index, type_row in enumerate(self.md.TypeDef.rows, 1)
            for field in type_row.FieldList
        }
        self.base_by_type: dict[str, str] = {}
        for index, row in enumerate(self.md.TypeDef.rows, 1):
            if row.Extends and row.Extends.row:
                self.base_by_type[self.type_names[index]] = self._type_ref_name(
                    row.Extends.row
                )

    def close(self) -> None:
        try:
            self.pe.close()
        except Exception:
            pass

    def _type_ref_name(self, row: Any) -> str:
        class_name = row.__class__.__name__
        if class_name == "TypeDefRow":
            index = self._typedef_index.get(id(row))
            if index is None:
                raise SourceExtractionError("unresolved TypeDef base reference")
            return self.type_names[index]
        if class_name == "TypeRefRow":
            namespace = str(row.TypeNamespace)
            return (namespace + "." if namespace else "") + str(row.TypeName)
        if class_name == "TypeSpecRow":
            # Generic bases elsewhere in the assembly are outside this census.
            # Keep an explicit terminal marker; any encounter chain reaching it
            # fails derives/category resolution rather than being guessed.
            return "<TypeSpec:" + row.Signature.value.hex() + ">"
        raise SourceExtractionError(f"unsupported base type reference {class_name}")

    def derives_from(self, source: str, ancestor: str) -> bool:
        seen: set[str] = set()
        current = source
        while current in self.base_by_type:
            if current in seen:
                raise SourceExtractionError(f"inheritance cycle at {current}")
            seen.add(current)
            current = self.base_by_type[current]
            if current == ancestor:
                return True
        return False

    def category_type(self, source: str) -> str:
        current = source
        seen: set[str] = set()
        while True:
            if current in seen:
                raise SourceExtractionError(f"inheritance cycle while categorizing {source}")
            seen.add(current)
            base = self.base_by_type.get(current)
            if base is None:
                raise SourceExtractionError(f"cannot resolve ModelDb category for {source}")
            if base == _ABSTRACT_MODEL:
                return current
            current = base

    def method_body(self, row_index: int):
        row = self.md.MethodDef.rows[row_index - 1]
        if not row.Rva:
            raise SourceExtractionError(
                f"metadata method 0x{0x06000000 | row_index:08x} has no CIL body"
            )
        try:
            return read_method_body_from_bytes(self.pe.get_data(row.Rva, 1 << 20))
        except Exception as exc:
            raise SourceExtractionError(
                f"cannot parse CIL body 0x{0x06000000 | row_index:08x}: {exc}"
            ) from exc

    def find_methods(self, owner: str, name: str) -> list[int]:
        return [
            index
            for index, row in enumerate(self.md.MethodDef.rows, 1)
            if self.type_names.get(self.method_owner.get(index)) == owner
            and str(row.Name) == name
        ]

    def method_symbol(self, row_index: int) -> str:
        row = self.md.MethodDef.rows[row_index - 1]
        owner = self.type_names.get(self.method_owner.get(row_index), "<global>")
        return f"{owner}::{row.Name} sig:{row.Signature.value.hex()}"

    def field_symbol(self, row_index: int) -> str:
        row = self.md.Field.rows[row_index - 1]
        owner = self.type_names.get(self.field_owner.get(row_index), "<global>")
        return f"{owner}::{row.Name}"

    @staticmethod
    def _coded_type_from_method_spec(blob: bytes) -> tuple[int, int] | None:
        """Decode the first CLASS/VALUETYPE TypeDefOrRef in a MethodSpec blob."""
        try:
            if len(blob) < 4 or blob[0] != 0x0A or blob[1] < 1 or blob[2] not in (0x11, 0x12):
                return None
            pos = 3
            first = blob[pos]
            if first & 0x80 == 0:
                coded = first
            elif first & 0xC0 == 0x80:
                coded = ((first & 0x3F) << 8) | blob[pos + 1]
            else:
                coded = ((first & 0x1F) << 24) | (blob[pos + 1] << 16) | (blob[pos + 2] << 8) | blob[pos + 3]
            return coded & 3, coded >> 2
        except (IndexError, TypeError):
            return None

    def resolve_token(self, token: Any) -> str:
        """Resolve a CIL token to a stable symbol; unknown token tables fail."""
        value = token.value if hasattr(token, "value") else int(token)
        table, index = value >> 24, value & 0xFFFFFF
        if index <= 0:
            raise SourceExtractionError(f"invalid metadata token 0x{value:08x}")
        try:
            if table == 0x70:
                return "string:" + str(self.pe.net.user_strings.get(index))
            if table == 0x02:
                return self.type_names[index]
            if table == 0x01:
                return self._type_ref_name(self.md.TypeRef.rows[index - 1])
            if table == 0x04:
                return self.field_symbol(index)
            if table == 0x06:
                return self.method_symbol(index)
            if table == 0x0A:
                row = self.md.MemberRef.rows[index - 1]
                return f"{self._type_ref_name(row.Class.row)}::{row.Name} sig:{row.Signature.value.hex()}"
            if table == 0x2B:
                row = self.md.MethodSpec.rows[index - 1]
                base = row.Method.row
                if base.__class__.__name__ == "MethodDefRow":
                    base_index = next((i for i, item in enumerate(self.md.MethodDef.rows, 1) if item is base), None)
                    if base_index is None:
                        raise SourceExtractionError("unresolved MethodSpec MethodDef")
                    symbol = self.method_symbol(base_index)
                elif base.__class__.__name__ == "MemberRefRow":
                    member_index = next((i for i, item in enumerate(self.md.MemberRef.rows, 1) if item is base), None)
                    if member_index is None:
                        raise SourceExtractionError("unresolved MethodSpec MemberRef")
                    symbol = self.resolve_token(0x0A000000 | member_index)
                else:
                    raise SourceExtractionError("unsupported MethodSpec target")
                decoded = self._coded_type_from_method_spec(row.Instantiation.value)
                if decoded:
                    tag, rid = decoded
                    if tag == 0:
                        argument = self.type_names[rid]
                    elif tag == 1:
                        argument = self._type_ref_name(self.md.TypeRef.rows[rid - 1])
                    else:
                        raise SourceExtractionError("unsupported MethodSpec generic type reference")
                    return symbol + " generic:" + argument
                return symbol + " methodspec:" + row.Instantiation.value.hex()
            if table == 0x1B:
                return "TypeSpec:" + self.md.TypeSpec.rows[index - 1].Signature.value.hex()
            if table == 0x11:
                return "StandAloneSig:" + self.md.StandAloneSig.rows[index - 1].Signature.value.hex()
        except (IndexError, AttributeError) as exc:
            raise SourceExtractionError(f"cannot resolve metadata token 0x{value:08x}: {exc}") from exc
        raise SourceExtractionError(f"unsupported metadata token table 0x{table:02x}")

    def method_record(self, row_index: int, assembly_sha256: str) -> dict[str, Any]:
        body = self.method_body(row_index)
        row = self.md.MethodDef.rows[row_index - 1]
        instructions: list[dict[str, Any]] = []
        for instruction in body.instructions:
            operand = instruction.operand
            if hasattr(operand, "value"):
                operand = self.resolve_token(operand)
            elif operand is not None and not isinstance(operand, (str, int, float, bytes)):
                operand = str(operand)
            instructions.append({
                "offsetDiagnostic": instruction.offset,
                "opcode": instruction.mnemonic,
                "operand": operand,
            })
        normalized = [
            {"opcode": item["opcode"], "operand": item["operand"]}
            for item in instructions
        ]
        return {
            "assemblySha256": assembly_sha256,
            "cilInstructionsSha256": hashlib.sha256(body.get_instruction_bytes()).hexdigest(),
            "diagnosticMetadataToken": f"0x{0x06000000 | row_index:08x}",
            "instructions": instructions,
            "metadataSignature": row.Signature.value.hex(),
            "methodBodySha256": hashlib.sha256(body.raw_bytes).hexdigest(),
            "normalizedInstructionsSha256": witness_sha256(normalized),
            "symbolSignature": self.method_symbol(row_index),
        }

    def verify_model_id_rules(self, assembly_sha256: str) -> dict[str, Any]:
        methods: list[dict[str, Any]] = []
        for expected in _METHOD_RULES:
            matches: list[int] = []
            for index, row in enumerate(self.md.MethodDef.rows, 1):
                owner = self.type_names.get(self.method_owner.get(index))
                if (
                    owner == expected["owner"]
                    and str(row.Name) == expected["name"]
                    and row.Signature.value.hex() == expected["metadataSignature"]
                ):
                    matches.append(index)
            if len(matches) != 1:
                raise SourceExtractionError(
                    f"unrecognized ModelDb/Slugify rule: {expected['symbolSignature']} "
                    f"matched {len(matches)} methods"
                )
            row_index = matches[0]
            body = self.method_body(row_index)
            body_hash = hashlib.sha256(body.raw_bytes).hexdigest()
            il_hash = hashlib.sha256(body.get_instruction_bytes()).hexdigest()
            if (
                body_hash != expected["methodBodySha256"]
                or il_hash != expected["cilInstructionsSha256"]
            ):
                raise SourceExtractionError(
                    f"unrecognized ModelDb/Slugify CIL for {expected['symbolSignature']}: "
                    f"method body {body_hash}, instructions {il_hash}"
                )
            methods.append(
                {
                    "assemblySha256": assembly_sha256,
                    "cilInstructionsSha256": il_hash,
                    "diagnosticMetadataToken": f"0x{0x06000000 | row_index:08x}",
                    "metadataSignature": expected["metadataSignature"],
                    "methodBodySha256": body_hash,
                    "symbolSignature": expected["symbolSignature"],
                }
            )
        methods.sort(key=lambda item: item["symbolSignature"])
        return {
            "assemblySha256": assembly_sha256,
            "methods": methods,
            "normalizedSemanticWitness": _MODEL_ID_WITNESS,
            "semanticWitnessSha256": witness_sha256(_MODEL_ID_WITNESS),
        }


def _slugify_category(name: str) -> str:
    slug = _slugify_ascii_type_name(name)
    if slug.endswith("_MODEL"):
        slug = slug[: -len("_MODEL")]
    if not slug:
        raise SourceExtractionError(f"SlugifyCategory produced an empty category for {name!r}")
    return slug


def extract_encounter_census(dll_path: Path, assembly_sha256: str, *, assembly: AssemblyMetadata | None = None) -> dict[str, Any]:
    owns_assembly = assembly is None
    if assembly is None:
        assembly = AssemblyMetadata(Path(dll_path))
    try:
        model_id_rule = assembly.verify_model_id_rules(assembly_sha256)
        candidates: list[tuple[int, Any, str, str]] = []
        for index, row in enumerate(assembly.md.TypeDef.rows, 1):
            full_name = assembly.type_names[index]
            namespace = str(row.TypeNamespace)
            # Nested compiler helpers have no TypeNamespace in CLI metadata.
            # They are not model candidates, but a nested EncounterModel would
            # be a new, unresolved census shape and must not be ignored.
            if namespace != _ENCOUNTER_NAMESPACE:
                if (
                    full_name.startswith(_ENCOUNTER_NAMESPACE + ".")
                    and "+" in full_name
                    and assembly.derives_from(full_name, _ENCOUNTER_BASE)
                ):
                    raise SourceExtractionError(
                        f"unexpected nested encounter model: {full_name}"
                    )
                continue
            simple_name = str(row.TypeName)
            if not assembly.derives_from(full_name, _ENCOUNTER_BASE):
                raise SourceExtractionError(
                    f"unexpected non-EncounterModel type in encounter namespace: {full_name}"
                )
            candidates.append((index, row, full_name, simple_name))

        if len(candidates) != sum(_EXPECTED_COUNTS.values()):
            raise SourceExtractionError(
                f"encounter namespace type count drift: got {len(candidates)}, expected 91"
            )

        ordinary: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        abstracts: list[str] = []
        deprecated: list[str] = []
        ids: set[str] = set()

        for index, row, full_name, simple_name in candidates:
            if bool(row.Flags.tdAbstract):
                abstracts.append(full_name)
                continue
            if full_name == _DEPRECATED:
                deprecated.append(full_name)
                continue

            methods = {str(item.row.Name) for item in row.MethodList}
            missing_methods = _REQUIRED_CONCRETE_METHODS - methods
            if missing_methods:
                raise SourceExtractionError(
                    f"unresolved concrete encounter {full_name}: missing "
                    + ", ".join(sorted(missing_methods))
                )

            inherited_event = assembly.derives_from(full_name, _EVENT_BASE)
            named_event = simple_name.endswith("EventEncounter")
            if inherited_event:
                kind = "event"
            elif named_event:
                if assembly.base_by_type.get(full_name) != _ENCOUNTER_BASE:
                    raise SourceExtractionError(
                        f"unrecognized event encounter inheritance: {full_name}"
                    )
                kind = "event"
            else:
                if "Event" in simple_name:
                    raise SourceExtractionError(
                        f"unresolved encounter classification for {full_name}"
                    )
                if assembly.base_by_type.get(full_name) != _ENCOUNTER_BASE:
                    raise SourceExtractionError(
                        f"unrecognized ordinary encounter inheritance: {full_name}"
                    )
                kind = "ordinary"

            category_type = assembly.category_type(full_name)
            category_simple = category_type.rsplit(".", 1)[-1]
            category = _slugify_category(category_simple)
            if category_type != _ENCOUNTER_BASE or category != "ENCOUNTER":
                raise SourceExtractionError(
                    f"unrecognized ModelDb encounter category for {full_name}: "
                    f"{category_type} -> {category}"
                )
            canonical_id = _slugify_ascii_type_name(simple_name)
            if canonical_id in ids:
                raise SourceExtractionError(f"duplicate canonical encounter ID {canonical_id}")
            ids.add(canonical_id)
            record = {
                "assemblyCategory": category,
                "canonicalId": canonical_id,
                "diagnosticMetadataToken": f"0x{0x02000000 | index:08x}",
                "kind": kind,
                "sourceType": full_name,
            }
            (events if kind == "event" else ordinary).append(record)

        if set(abstracts) != _EXPECTED_ABSTRACT:
            raise SourceExtractionError(
                f"abstract encounter type drift: got {sorted(abstracts)!r}, "
                f"expected {sorted(_EXPECTED_ABSTRACT)!r}"
            )
        if set(deprecated) != _EXPECTED_DEPRECATED:
            raise SourceExtractionError(
                f"deprecated encounter type drift: got {sorted(deprecated)!r}, "
                f"expected {sorted(_EXPECTED_DEPRECATED)!r}"
            )

        ordinary.sort(key=lambda item: item["canonicalId"])
        events.sort(key=lambda item: item["canonicalId"])
        actual_counts = {
            "ordinary": len(ordinary),
            "event": len(events),
            "abstract": len(abstracts),
            "deprecated": len(deprecated),
        }
        if actual_counts != _EXPECTED_COUNTS:
            raise SourceExtractionError(
                f"encounter classification count drift: got {actual_counts}, "
                f"expected {_EXPECTED_COUNTS}"
            )
        if "AEONGLASS_BOSS" not in ids:
            raise SourceExtractionError("identity pin failed: AEONGLASS_BOSS is absent")
        if "DOORMAKER_BOSS" in ids:
            raise SourceExtractionError("identity pin failed: DOORMAKER_BOSS is current")

        return {
            "abstractTypes": sorted(abstracts),
            "deprecatedPlaceholderTypes": sorted(deprecated),
            "event": events,
            "modelIdRule": model_id_rule,
            "ordinary": ordinary,
        }
    finally:
        if owns_assembly:
            assembly.close()
