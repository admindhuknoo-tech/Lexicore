from services.legal_element_engine import build_element_reasoning

def test_element_reasoning_fails_closed_without_verified_norm():
    r=build_element_reasoning({
      "element_matrix":[{"element":"Mens rea / tujuan menguntungkan","status":"SUPPORTED","prosecution_support":"x","defense_focus":"y"}],
      "source_ledger":[{"statement":"Terdapat rekening dan aliran dana kepada pihak terkait.","label":"DOCUMENT","segment":1}],
      "case_regulatory_snapshot":{"official_results":[]},
    })
    assert r["overall_status"] == "PROVISIONAL_LEGAL_ANALYSIS"
    assert r["elements"][0]["legal_gate"] == "NOT_VERIFIED"
    assert "norma positif" in r["legal_conclusion"]

def test_element_reasoning_does_not_promote_without_evidence():
    r=build_element_reasoning({
      "element_matrix":[{"element":"Kausalitas","status":"SUPPORTED"}],
      "source_ledger":[],
      "case_regulatory_snapshot":{"official_results":[{"positive_law_verification":{
        "final_status":"VERIFIED_APPLICABLE","identity_confirmed":True,"case_nexus_status":"CASE_NEXUS_VERIFIED",
        "tempus_status":"TEMPUS_VERIFIED","tempus_applicable":True,
        "provision_verification":{"status":"PROVISION_VERIFIED","verified_count":1}}}]},
    })
    assert r["elements"][0]["status"] == "NOT_ESTABLISHED"
    assert r["overall_status"] == "INSUFFICIENT_RECORD"
