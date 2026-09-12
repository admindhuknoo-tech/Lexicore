from services.element_reasoning import build_element_reasoning
from services.legal_reasoning_chain import build_reasoning_chain
from services.reasoning_contract import validate_reasoning_contract


def _ledger(*statements):
    return [{"source_index":i,"statement":s,"label":"SOURCE FACT","source_classification":"SOURCE_FACT"} for i,s in enumerate(statements)]


def test_pmh_waris_land_does_not_activate_contract_elements():
    domain={"primary_domain":"civil_contract","domain_contract":["civil_contract","civil_procedure","land_property","religious_court"]}
    ledger=_ledger(
        "Gugatan mendalilkan Perbuatan Melawan Hukum terkait waris dan Sertipikat Hak Milik 05392.",
        "Para pihak beragama Islam dan mempersoalkan siapa ahli waris dan pembagian waris.",
        "SKPT Kantor Pertanahan terkait Sertipikat Hak Milik 05392 telah diminta.",
    )
    r=build_element_reasoning(domain_contract=domain,ledger=ledger)
    ids={x["id"] for x in r["element_matrix"]}
    assert "valid_contract" not in ids
    assert "breach" not in ids
    assert "default_notice" not in ids
    assert "pmh_unlawful_act" in ids


def test_element_ownership_is_explicit_and_stable():
    domain={"primary_domain":"land_property","domain_contract":["land_property"]}
    r=build_element_reasoning(domain_contract=domain,ledger=_ledger("SKPT dan Sertipikat Hak Milik 05392 diterbitkan oleh BPN."))
    for row in r["element_matrix"]:
        assert row["owner_domain"] == "land_property"
        assert row["owner_issue_id"] == "land_title_chain"
        assert row["owner_issue"]


def test_legal_argument_is_not_promoted_to_evidence():
    domain={"primary_domain":"civil_procedure","domain_contract":["civil_procedure"]}
    r=build_element_reasoning(domain_contract=domain,ledger=_ledger("Ekseptio Plurium Litis Consortium (Gugatan Kurang Pihak): gugatan kurang pihak."))
    assert all(not x["supporting_evidence"] for x in r["element_matrix"])


def test_land_skpt_not_evidence_for_procedural_consequence():
    domain={"primary_domain":"civil_procedure","domain_contract":["civil_procedure"]}
    r=build_element_reasoning(domain_contract=domain,ledger=_ledger("SKPT Kantor Pertanahan terkait Sertipikat Hak Milik 05392 tidak terdapat blokir."))
    consequence=next(x for x in r["element_matrix"] if x["id"]=="procedural_consequence")
    assert consequence["supporting_evidence"] == []


def test_chain_uses_owned_issue_not_cross_domain_similarity():
    result={
        "legal_issues":["Isu salah yang generik"],
        "element_reasoning":{"elements":[{
            "id":"land_right_identity","element":"Identitas objek tanah dan dasar alas hak","owner_domain":"land_property","owner_issue_id":"land_title_chain","owner_issue":"Bagaimana riwayat alas hak dan status sertipikat?","status":"NOT_ESTABLISHED","supporting_evidence":[]
        }]},
        "applicable_law":[
            {"source":"UU Peradilan Agama","domain":"Peradilan Agama","status":"UNVERIFIED"},
            {"source":"Peraturan Pendaftaran Tanah","domain":"Pertanahan & Properti","status":"UNVERIFIED"},
        ]
    }
    chain=build_reasoning_chain(result)
    row=chain["chains"][0]
    assert row["issue"]["value"] == "Bagaimana riwayat alas hak dan status sertipikat?"
    assert row["applicable_law"]["selected"]["source"] == "Peraturan Pendaftaran Tanah"


def test_validator_exposes_semantic_hold_separately_from_structure():
    result={
        "element_reasoning":{"elements":[{
            "id":"land_right_identity","element":"Identitas objek tanah","owner_domain":"land_property","owner_issue_id":"land_title_chain","owner_issue":"Status sertipikat?","status":"NOT_ESTABLISHED","supporting_evidence":[]
        }]},
        "applicable_law":[{"source":"Peraturan Pendaftaran Tanah","domain":"Pertanahan & Properti","status":"UNVERIFIED"}],
    }
    chain=build_reasoning_chain(result)
    v=validate_reasoning_contract(chain)
    assert v["status"] == "PASS"
    assert v["semantic_status"] == "HOLD"
