from services.adversarial_view import build_adversarial_viewpoint_splitter


def _sal(sid, stype, state, speaker, position, stance, target, routes):
    return {
        "statement_id": sid,
        "text_payload": sid,
        "semantic_envelope": {
            "semantic_type": stype,
            "provenance": f"SOURCE | speaker_role={speaker} | position={position} | stance={stance}",
            "domain_posture": f"criminal | adversarial_position={position}",
        },
        "admission_contract": {
            "admissibility_state": state,
            "restricted_routes": list(routes),
            "prohibited_routes": [],
        },
        "downstream_migration": {"primary_target_node": target},
    }


def test_splitter_is_read_only_and_preserves_prosecutor_argument():
    sal = _sal("SAL_JPU", "PARTY_ARGUMENT", "LIMITED", "PROSECUTOR", "PROSECUTION", "ALLEGATION", "Alleged Act", ["Issue", "Alleged Act"])
    result = {
        "source_ledger": [{"statement": "JPU mendalilkan perbuatan terdakwa", "sal_contract": sal}],
        "sal_governed_pools": {"route_token_ledger": {"SAL_JPU": {"allowed_consumers": ["Issue", "Alleged Act"], "prohibited_consumers": []}}},
    }
    before = sal["semantic_envelope"]["semantic_type"]
    vm = build_adversarial_viewpoint_splitter(result)
    assert len(vm["prosecution"]) == 1
    row = vm["prosecution"][0]
    assert row["semantic_type"] == "PARTY_ARGUMENT"
    assert row["trace_label"] == "[Posisi JPU / Belum Terverifikasi]"
    assert sal["semantic_envelope"]["semantic_type"] == before


def test_splitter_preserves_defense_counter_argument():
    sal = _sal("SAL_PH", "COUNTER_ARGUMENT", "LIMITED", "DEFENSE_COUNSEL", "DEFENSE", "REBUTTAL", "Element Test", ["Element Test"])
    result = {
        "source_ledger": [{"statement": "PH membantah kewenangan", "sal_contract": sal}],
        "sal_governed_pools": {"route_token_ledger": {"SAL_PH": {"allowed_consumers": ["Element Test"], "prohibited_consumers": []}}},
    }
    vm = build_adversarial_viewpoint_splitter(result)
    assert len(vm["defense"]) == 1
    assert vm["defense"][0]["trace_label"] == "[Dalil Pembelaan / DEFENSE_COUNSEL]"


def test_splitter_blocks_rows_without_route_token():
    sal = _sal("SAL_RAW", "FACT_ASSERTION", "LIMITED", "UNKNOWN", "NEUTRAL", "UNSPECIFIED", "Document Audit", ["Document Audit"])
    result = {"source_ledger": [{"statement": "raw bypass candidate", "sal_contract": sal}], "sal_governed_pools": {"route_token_ledger": {}}}
    vm = build_adversarial_viewpoint_splitter(result)
    assert vm["prosecution"] == []
    assert vm["defense"] == []
    assert vm["neutral"] == []
    assert vm["blocked_without_route_token"] == 1
    assert vm["status"] == "UNRESOLVED_SOURCE_OWNERSHIP"


def test_neutral_is_not_labeled_objective_fact():
    sal = _sal("SAL_N", "FACT_ASSERTION", "LIMITED", "UNKNOWN", "NEUTRAL", "UNSPECIFIED", "Document Audit", ["Document Audit"])
    result = {
        "source_ledger": [{"statement": "pernyataan netral belum terverifikasi", "sal_contract": sal}],
        "sal_governed_pools": {"route_token_ledger": {"SAL_N": {"allowed_consumers": ["Document Audit"], "prohibited_consumers": []}}},
    }
    vm = build_adversarial_viewpoint_splitter(result)
    assert vm["neutral"][0]["trace_label"] == "[Sumber Netral / Belum Terverifikasi]"
    assert "Objektif" not in vm["neutral"][0]["trace_label"]
