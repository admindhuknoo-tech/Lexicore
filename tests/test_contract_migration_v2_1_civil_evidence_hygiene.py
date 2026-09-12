from services.element_reasoning import build_element_reasoning
from services.legal_reasoning_chain import build_reasoning_chain


def _domain():
    return {"primary_domain":"civil_procedure","domain_contract":["civil_procedure","land_property","religious_court","civil_contract"]}


def test_pmh_waris_land_does_not_inject_wanprestasi_template_without_contract_case():
    ledger=[
        {"label":"ALLEGATION","statement":"Gugatan mendalilkan Perbuatan Melawan Hukum mengenai Sertipikat Hak Milik dan pembagian waris."},
        {"label":"ALLEGATION","statement":"Para pihak adalah ahli waris dan objek sengketa adalah tanah SHM 05392."},
    ]
    out=build_element_reasoning(domain_contract=_domain(), ledger=ledger, existing_matrix=[])
    ids={x["id"] for x in out["element_matrix"]}
    assert "valid_contract" not in ids
    assert "breach" not in ids
    assert "pmh_unlawful_act" in ids
    assert "procedural_standing" in ids
    assert "land_right_identity" in ids
    assert "inheritance_character" in ids


def test_pleading_and_denial_are_not_promoted_to_evidence_or_counter_evidence():
    ledger=[
        {"label":"ALLEGATION","statement":"Penggugat mendalilkan Perbuatan Melawan Hukum atas Sertipikat Hak Milik 05392."},
        {"label":"DENIAL / LIMITATION","statement":"Para Tergugat menolak dengan tegas dalil Penggugat mengenai Sertipikat Hak Milik 05392."},
        {"label":"LEGAL REFERENCE","statement":"Pasal 49 Undang-Undang Peradilan Agama."},
    ]
    out=build_element_reasoning(domain_contract=_domain(), ledger=ledger, existing_matrix=[])
    land=next(x for x in out["element_matrix"] if x["id"]=="land_right_identity")
    assert land["supporting_evidence"] == []
    assert land["counter_evidence"] == []
    assert land["alleged_act"]
    assert land["counter_arguments"]


def test_procedural_chain_marks_causation_not_applicable_and_does_not_borrow_unrelated_law():
    result={
        "legal_issues":["Apakah gugatan memenuhi syarat formil dan kompetensi absolut?"],
        "element_matrix":[{
            "id":"absolute_competence","element":"Kompetensi absolut forum berdasarkan subjek dan objek", "status":"NOT_ESTABLISHED",
            "alleged_act":"Penggugat memilih Pengadilan Negeri untuk sengketa waris.",
            "supporting_evidence":[],"counter_evidence":[],
        }],
        "applicable_law":[{"source":"UU Perbankan", "status":"CANDIDATE", "domain":"Perbankan"}],
        "causation_analysis":{"status":"PARTIAL_NEXUS_IDENTIFIED","reason":"global merits nexus"},
    }
    chain=build_reasoning_chain(result)["chains"][0]
    assert chain["procedural_merits_classification"]["value"] == "PROCEDURAL"
    assert chain["causation"]["status"] == "GAP"
    assert chain["applicable_law"]["selected"] is None
