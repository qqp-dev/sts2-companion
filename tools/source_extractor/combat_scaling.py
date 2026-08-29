"""Source-derived Block and Power multiplayer scaling facts."""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from .ast import evaluate_expression, validate_expression
from .canonical import slugify_ascii_type_name, witness_sha256
from .errors import SourceExtractionError
from .metadata import AssemblyMetadata


def c(value: int | str, kind: str = "integer") -> dict[str,Any]:
    return {"kind":"constant","value":value,"valueType":kind}

def state(name: str, kind: str, domain: Any) -> dict[str,Any]:
    return {"domain":domain,"kind":"stateVariable","name":name,"valueType":kind}

def arithmetic(op: str, *values: dict[str,Any], kind: str | None = None) -> dict[str,Any]:
    if kind is None: kind="decimal" if any(x["valueType"]=="decimal" for x in values) or op=="divide" else "integer"
    return {"kind":"arithmetic","operands":list(values),"operator":op,"valueType":kind}

def convert(value: dict[str,Any]) -> dict[str,Any]:
    return {"expression":value,"fromType":"integer","kind":"convert","mode":"exact","toType":"decimal","valueType":"decimal"}

def condition(test: dict[str,Any], yes: dict[str,Any], no: dict[str,Any], kind: str="decimal") -> dict[str,Any]:
    return {"condition":test,"kind":"conditional","valueType":kind,"whenFalse":no,"whenTrue":yes}

def compare(op: str,left:dict[str,Any],right:dict[str,Any])->dict[str,Any]:
    return {"kind":"compare","left":left,"operator":op,"right":right,"valueType":"boolean"}

def method(record:dict[str,Any],semantic:Any)->dict[str,Any]:
    normalized=[{"opcode":x["opcode"],"operand":x["operand"]} for x in record["instructions"]]
    return {key:record[key] for key in ("assemblySha256","cilInstructionsSha256","diagnosticMetadataToken","metadataSignature","methodBodySha256","normalizedInstructionsSha256","symbolSignature")} | {"normalizedSliceSha256":witness_sha256(normalized),"semanticWitnessSha256":witness_sha256(semantic)}

def one(assembly:AssemblyMetadata,owner:str,name:str,sha:str)->dict[str,Any]:
    rows=assembly.find_methods(owner,name)
    if len(rows)!=1: raise SourceExtractionError(f"combat scaling method {owner}::{name} matched {len(rows)}")
    return assembly.method_record(rows[0],sha)

def require_calls(record:dict[str,Any], fragments:tuple[str,...])->None:
    calls=[str(x["operand"]) for x in record["instructions"] if x["opcode"] in {"call","callvirt"}]
    for fragment in fragments:
        if not any(fragment in x for x in calls): raise SourceExtractionError(f"scaling call {fragment} absent from {record['symbolSignature']}")

def act_factor()->dict[str,Any]:
    return {"actIndex":state("actIndex","integer",{"maximum":2,"minimum":0}),
            "boss":state("bossRoom","boolean",[False,True]),
            "factors":{"act1":"1.1","act2":"1.2","act3Boss":"1.3","act3NonBoss":"1.2"},
            "kind":"actRoomFactor","valueType":"decimal"}

def extract_block_scaling(assembly:AssemblyMetadata,sha:str)->dict[str,Any]:
    owner="MegaCrit.Sts2.Core.Models.Singleton.MultiplayerScalingModel"
    scale=one(assembly,owner,"ModifyBlockMultiplicative",sha); factor=one(assembly,owner,"GetMultiplayerScaling",sha)
    require_calls(scale,("get_IsPrimaryEnemy","get_IsSecondaryEnemy","IsPoweredCardOrMonsterMoveBlock","get_Players","GetMultiplayerScaling"))
    players=state("playerCount","integer",{"minimum":1}); eligible=state("sourceIsPrimaryOrSecondaryEnemy","boolean",[False,True]); powered=state("isPoweredCardOrMonsterMoveBlock","boolean",[False,True])
    player_factor=condition(compare("lessOrEqual",players,c(2)),convert(players),arithmetic("multiply",convert(players),act_factor()))
    expression=condition(eligible,condition(powered,player_factor,c("1","decimal")),c("1","decimal"))
    validate_expression(expression,expected_type="decimal")
    fixture_inputs=[
      {"actIndex":0,"bossRoom":False,"isPoweredCardOrMonsterMoveBlock":True,"playerCount":1,"sourceIsPrimaryOrSecondaryEnemy":True},
      {"actIndex":0,"bossRoom":False,"isPoweredCardOrMonsterMoveBlock":True,"playerCount":2,"sourceIsPrimaryOrSecondaryEnemy":True},
      {"actIndex":2,"bossRoom":True,"isPoweredCardOrMonsterMoveBlock":True,"playerCount":3,"sourceIsPrimaryOrSecondaryEnemy":True},
      {"actIndex":2,"bossRoom":True,"isPoweredCardOrMonsterMoveBlock":False,"playerCount":3,"sourceIsPrimaryOrSecondaryEnemy":True},
    ]
    fixtures=[{"inputs":x,"multiplier":str(evaluate_expression(expression,x))} for x in fixture_inputs]
    semantic={"expression":expression,"rounding":"none","sourceType":"System.Decimal"}
    return {**semantic,"fixtures":fixtures,"provenance":{"factor":method(factor,act_factor()),"scaling":method(scale,semantic)},"ruleId":"monsterBlockMultiplayerScaling.v0.111.0"}

def _power_formula(name:str,players:dict[str,Any],amount:dict[str,Any])->dict[str,Any]:
    pminus=arithmetic("subtract",players,c(1))
    if name=="ArtifactPower": return arithmetic("subtract",arithmetic("add",amount,convert(players)),c("1","decimal"))
    if name in {"BufferPower","PlatingPower"}: return arithmetic("multiply",amount,convert(arithmetic("add",arithmetic("multiply",pminus,c(2)),c(1))))
    if name=="SkittishPower": return arithmetic("multiply",amount,arithmetic("add",c("1","decimal"),arithmetic("multiply",convert(pminus),c("0.5","decimal"))))
    if name=="SlipperyPower": return arithmetic("multiply",amount,convert(players))
    raise SourceExtractionError(f"unknown Power scaling override {name}")

def extract_power_scaling(assembly:AssemblyMetadata,sha:str)->dict[str,Any]:
    base_owner="MegaCrit.Sts2.Core.Models.PowerModel"
    base_flag=one(assembly,base_owner,"get_ShouldScaleInMultiplayer",sha); base_formula_method=one(assembly,base_owner,"GetScaledAmountForMultiplayer",sha)
    if [(x["opcode"],x["operand"]) for x in base_flag["instructions"]] != [("ldc.i4.0",None),("ret",None)]: raise SourceExtractionError("Power scaling inherited default flag drift")
    require_calls(base_formula_method,("get_Players","GetMultiplayerScaling","Decimal::op_Multiply"))
    optins=[]; overrides=[]
    for ti,row in enumerate(assembly.md.TypeDef.rows,1):
        owner=assembly.type_names[ti]
        prefix="MegaCrit.Sts2.Core.Models.Powers."
        if not owner.startswith(prefix) or "+" in owner or ".Mocks." in owner: continue
        simple=owner[len(prefix):]
        flags=[m.row_index for m in row.MethodList if str(m.row.Name)=="get_ShouldScaleInMultiplayer"]
        formulas=[m.row_index for m in row.MethodList if str(m.row.Name)=="GetScaledAmountForMultiplayer"]
        for mi in flags:
            r=assembly.method_record(mi,sha); normalized=[(x["opcode"],x["operand"]) for x in r["instructions"]]
            if normalized != [("ldc.i4.1",None),("ret",None)]: raise SourceExtractionError(f"unrecognized Power opt-in body {owner}")
            semantic={"canonicalPower":"POWER."+slugify_ascii_type_name(simple),"shouldScale":True}
            optins.append({**semantic,"provenance":method(r,semantic)})
        for mi in formulas:
            r=assembly.method_record(mi,sha)
            players=state("playerCount","integer",{"minimum":1}); amount=state("amount","decimal",{"minimum":"0"}); expression=_power_formula(simple,players,amount);validate_expression(expression,expected_type="decimal")
            power="POWER."+slugify_ascii_type_name(simple); active=bool(flags)
            semantic={"active":active,"canonicalPower":power,"expression":expression,"override":True}
            fixtures=[]
            for pc in (1,2,3):
                inputs={"amount":"2","playerCount":pc};fixtures.append({"inputs":inputs,"result":str(evaluate_expression(expression,inputs))})
            overrides.append({**semantic,"fixtures":fixtures,"provenance":method(r,semantic)})
    optins.sort(key=lambda x:x["canonicalPower"]);overrides.sort(key=lambda x:x["canonicalPower"])
    if (len(optins),len(overrides),sum(x["active"] for x in overrides))!=(12,5,4): raise SourceExtractionError(f"Power scaling census disagreement: {len(optins)}/{len(overrides)}/{sum(x['active'] for x in overrides)}")
    players=state("playerCount","integer",{"minimum":1});amount=state("amount","decimal",{"minimum":"0"})
    default=arithmetic("multiply",amount,convert(players),act_factor())
    validate_expression(default,expected_type="decimal")
    gate=one(assembly,"MegaCrit.Sts2.Core.Commands.PowerCmd+<Apply>d__2","MoveNext",sha)
    require_calls(gate,("get_ShouldScaleInMultiplayer","GetScaledAmountForMultiplayer","get_IsPrimaryEnemy","get_IsSecondaryEnemy"))
    return {"applicationGate":{"conditions":["power.ShouldScaleInMultiplayer","target is primary or secondary enemy","applier is player","player count greater than one"],"provenance":method(gate,{"gate":"role/playerCount/optIn"})},
      "inheritedDefault":{"activeByDefault":False,"expression":default,"provenance":{"formula":method(base_formula_method,default),"optIn":method(base_flag,False)}},
      "optIns":optins,"overrides":overrides,"summary":{"activeOverrides":4,"formulaOverrides":5,"optIns":12}}

def extract_combat_scaling(assembly:AssemblyMetadata,sha:str)->dict[str,Any]:
    return {"block":extract_block_scaling(assembly,sha),"power":extract_power_scaling(assembly,sha),
            "ordinaryMonsterAttack":{"scalesInMultiplayer":False,"basis":"DamageCmd.Attack command amount is not passed through HP, Block, or Power scaling paths"}}
