"""LexiCore SAL v1.0 cross-layer contract enforcer.

This module is deliberately small and deterministic.  SAL remains the semantic
producer; this enforcer makes the producer's restricted-routing contract binding
on every downstream consumer and blocks subject-matter-mismatched law results
before they can become Candidate Law.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Tuple

PROOF_NODES = {"Evidence Map", "Case Readiness"}
ALLEGED_ACT_NODE = "Alleged Act"
LEGAL_CONSTRUCTION_NODE = "Legal Construction"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


class LexiCoreContractEnforcer:
    """Binding enforcement for SAL routing and law subject-matter admission."""

    @staticmethod
    def enforce_routing(sal_payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(sal_payload or {})
        adm = dict(payload.get("admission_contract") or {})
        migration = dict(payload.get("downstream_migration") or {})
        state = str(adm.get("admissibility_state") or "REJECTED").upper()
        allowed = list(dict.fromkeys(adm.get("restricted_routes") or []))
        prohibited = list(dict.fromkeys(adm.get("prohibited_routes") or []))
        target = migration.get("primary_target_node") or "NONE"
        directive = migration.get("next_execution_directive") or "STOP"

        def forbid(*nodes: str) -> None:
            nonlocal prohibited
            for node in nodes:
                if node not in prohibited:
                    prohibited.append(node)
            allowed[:] = [node for node in allowed if node not in nodes]

        if state == "LEAD_ONLY":
            forbid("Evidence Map", "Case Readiness", "Alleged Act", "Legal Elements", "Causation")
            if target in prohibited or target == "NONE":
                target = "Document Audit"
                directive = "FORCE_ROUTE_TO_AUDIT_AS_LEAD_ONLY_DO_NOT_CONVERT_TO_PROOF"
                if target not in allowed:
                    allowed.append(target)

        elif state == "LIMITED":
            # LIMITED may legitimately route to Alleged Act for PARTY_ARGUMENT,
            # but never to proof pools. Preserve the producer's narrower route set.
            forbid("Evidence Map", "Case Readiness")
            if target in prohibited:
                target = allowed[0] if allowed else "Document Audit"
                directive = "ENFORCE_LIMITED_ROUTE_NO_PROOF_UPGRADE"

        elif state == "REJECTED":
            forbid("Evidence Map", "Case Readiness", "Alleged Act", "Legal Construction", "Legal Elements", "Causation", "Risk")
            # A rejected source may still carry a producer-authorized Action Plan
            # route (e.g. FUTURE_ACTION). Otherwise isolate it in Document Audit.
            if target not in allowed:
                if "Action Plan" in allowed:
                    target = "Action Plan"
                    directive = "ROUTE_REJECTED_SOURCE_AS_PROSPECTIVE_ACTION_ONLY"
                else:
                    target = "Document Audit"
                    directive = "HARD_ISOLATION_REJECTED_BY_UPSTREAM_SAL"
                    if target not in allowed:
                        allowed.append(target)

        payload["admission_contract"] = {
            **adm,
            "restricted_routes": allowed,
            "prohibited_routes": prohibited,
        }
        payload["downstream_migration"] = {
            **migration,
            "primary_target_node": target,
            "next_execution_directive": directive,
        }
        return payload

    @staticmethod
    def route_allowed(sal_payload: Dict[str, Any], route: str) -> bool:
        payload = LexiCoreContractEnforcer.enforce_routing(sal_payload)
        adm = payload.get("admission_contract") or {}
        allowed = set(adm.get("restricted_routes") or [])
        prohibited = set(adm.get("prohibited_routes") or [])
        return route in allowed and route not in prohibited


    @staticmethod
    def resolve_document_adversarial_identity(raw_extracted_text: str) -> Dict[str, str]:
        """Resolve document identity from the whole available corpus.

        Presentation/provenance only.  Positive weighted fingerprints are used
        for three explicit document families: prosecution response, defense
        pleading, and BAP/interrogation record.  Ties or weak signals stay
        unresolved; there is no default-to-defense fallback.
        """
        text_lower = _clean(raw_extracted_text).lower()

        prosecution_markers = (
            ("tanggapan penuntut umum", 10),
            ("nota perlawanan terdakwa", 5),
            ("penuntut umum memohon", 5),
            ("menolak seluruh dalil", 5),
            ("kami penuntut umum", 4),
            ("surat dakwaan nomor", 3),
            ("agenda pembuktian", 3),
            ("melanjutkan pemeriksaan perkara", 2),
        )
        defense_markers = (
            ("eksepsi", 10),
            ("nota pembelaan", 10),
            ("nota keberatan", 8),
            ("penasehat hukum terdakwa", 5),
            ("penasihat hukum terdakwa", 5),
            ("mohon dapat diputuskan dengan seadil-adilnya", 4),
            ("dakwaan batal demi hukum", 3),
            ("dikeluarkan dari rumah tahanan", 3),
            ("error in persona", 2),
        )
        bap_markers = (
            ("berita acara pemeriksaan tersangka", 14),
            ("berita acara pemeriksaan", 12),
            ("jaksa penyidik", 6),
            ("pertanyaan penyidik", 6),
            ("telah memeriksa seorang yang dihadapan saya mengaku", 5),
            ("apakah sekarang tersangka", 3),
            ("diperlihatkan kepada saudara", 3),
            ("surat perintah penyidikan", 2),
        )

        def score(markers):
            # Count occurrences so a corpus-wide fingerprint survives partial OCR
            # and does not depend on a single header token.
            return sum(text_lower.count(marker) * weight for marker, weight in markers)

        prosecution_score = score(prosecution_markers)
        defense_score = score(defense_markers)
        bap_score = score(bap_markers)

        # Context anchors prevent generic litigation language such as "menolak
        # seluruh dalil" in ethics/civil responses from being mistaken for a
        # prosecutor document.  The weighted score still decides within an
        # anchored document family.
        prosecution_anchor = any(m in text_lower for m in ("penuntut umum", "jaksa penuntut umum", "kejaksaan negeri"))
        defense_anchor = any(m in text_lower for m in ("terdakwa", "penasehat hukum terdakwa", "penasihat hukum terdakwa"))
        bap_anchor = any(m in text_lower for m in ("berita acara pemeriksaan", "jaksa penyidik", "surat perintah penyidikan"))
        if not prosecution_anchor:
            prosecution_score = 0
        if not defense_anchor:
            defense_score = 0
        if not bap_anchor:
            bap_score = 0
        scores = {
            "PROSECUTOR": prosecution_score,
            "DEFENSE_COUNSEL": defense_score,
            "INTERROGATOR_AND_SUSPECT": bap_score,
        }
        winner = max(scores, key=scores.get) if scores else "UNKNOWN"
        winning_score = scores.get(winner, 0)
        ordered = sorted(scores.values(), reverse=True)
        runner_up = ordered[1] if len(ordered) > 1 else 0

        # Positive-allow identity: require a meaningful and strictly dominant
        # fingerprint.  Weak/tied evidence remains unresolved.
        if winning_score < 4 or winning_score == runner_up:
            winner = "UNKNOWN"

        common = {
            "identity_status": "RESOLVED_BY_SEMANTIC_FINGERPRINT" if winner != "UNKNOWN" else "UNRESOLVED_SOURCE_OWNERSHIP",
            "prosecution_score": str(prosecution_score),
            "defense_score": str(defense_score),
            "bap_score": str(bap_score),
        }
        if winner == "INTERROGATOR_AND_SUSPECT":
            return {
                **common,
                "document_posture": "Berita Acara Pemeriksaan (BAP) / Interogasi Prosedural",
                "speaker_role": "INTERROGATOR_AND_SUSPECT",
                "position": "NEUTRAL_RECORD",
                "default_stance": "EXAMINATION_RECORD",
            }
        if winner == "PROSECUTOR":
            return {
                **common,
                "document_posture": "Tanggapan Penuntut Umum terhadap Nota Perlawanan",
                "speaker_role": "PROSECUTOR",
                "position": "PROSECUTION",
                "default_stance": "ALLEGATION",
            }
        if winner == "DEFENSE_COUNSEL":
            return {
                **common,
                "document_posture": "Nota Pembelaan / Eksepsi Terdakwa",
                "speaker_role": "DEFENSE_COUNSEL",
                "position": "DEFENSE",
                "default_stance": "REBUTTAL",
            }
        return {
            **common,
            "document_posture": "Dokumen Hukum / Kepemilikan Suara Belum Terverifikasi",
            "speaker_role": "UNKNOWN",
            "position": "NEUTRAL",
            "default_stance": "UNSPECIFIED",
        }

    @staticmethod
    def infer_adversarial_context(raw_document_text: str) -> Dict[str, str]:
        """Backward-compatible adversarial context wrapper."""
        identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(raw_document_text)
        return {
            "speaker_role": identity["speaker_role"],
            "position": identity["position"],
            "stance": identity["default_stance"],
        }

    @staticmethod
    def adversarial_context_from_payload(sal_payload: Dict[str, Any]) -> Dict[str, str]:
        """Read frozen-schema adversarial and epistemic context from provenance."""
        env = (sal_payload or {}).get("semantic_envelope") or {}
        blob = f"{env.get('provenance','')} {env.get('domain_posture','')}"
        values = {}
        for key in ("speaker_role", "position", "stance", "epistemic_status"):
            m = re.search(rf"(?:^|\|\s*){key}=([A-Z_]+)", blob, re.I)
            if m:
                values[key] = m.group(1).upper()
        return {
            "speaker_role": values.get("speaker_role", "UNKNOWN"),
            "position": values.get("position", "NEUTRAL"),
            "stance": values.get("stance", "UNSPECIFIED"),
            "epistemic_status": values.get("epistemic_status", "UNSPECIFIED"),
        }

    @staticmethod
    def enforce_adversarial_context(sal_payload: Dict[str, Any], raw_document_text: str) -> Dict[str, Any]:
        """Bind speaker ownership without changing the frozen semantic type schema.

        FACT_ASSERTION remains a statement type.  Its epistemic ownership is
        separately bound in provenance, so a chronological assertion may survive
        while a unilateral merits accusation cannot masquerade as an objective fact
        in governed summaries or trace projections.
        """
        payload = dict(sal_payload or {})
        env = dict(payload.get("semantic_envelope") or {})
        text = _clean(payload.get("text_payload"))
        identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(raw_document_text)
        context = {
            "speaker_role": identity["speaker_role"],
            "position": identity["position"],
            "stance": identity["default_stance"],
        }

        provenance = _clean(env.get("provenance")) or "SOURCE_PROVENANCE_UNKNOWN"
        domain_posture = _clean(env.get("domain_posture")) or "UNKNOWN / UNKNOWN"
        provenance = re.sub(r"\s*\|\s*speaker_role=[A-Z_]+\s*\|\s*position=[A-Z_]+\s*\|\s*stance=[A-Z_]+(?:\s*\|\s*epistemic_status=[A-Z_]+)?", "", provenance, flags=re.I)
        domain_posture = re.sub(r"\s*\|\s*adversarial_position=[A-Z_]+", "", domain_posture, flags=re.I)

        epistemic = "UNSPECIFIED"
        if str(env.get("semantic_type") or "") == "FACT_ASSERTION":
            low = text.lower()
            merits_markers = (
                "melakukan perbuatan melawan hukum",
                "menyalahgunakan kewenangan",
                "merugikan keuangan",
                "mengakibatkan kerugian",
                "telah merugikan",
                "secara melawan hukum",
            )
            defense_rebuttal_markers = (
                "bukan kewenangan",
                "tidak berwenang mengadili",
                "error in persona",
                "batal demi hukum",
                "tidak berdasar",
                "tidak beralasan",
            )
            if context["speaker_role"] == "PROSECUTOR":
                epistemic = "UNVERIFIED_PROSECUTION_ALLEGATION" if any(m in low for m in merits_markers) else "CHRONOLOGICAL_FACT_REPORTED_BY_PROSECUTION"
            elif context["speaker_role"] == "DEFENSE_COUNSEL":
                epistemic = "UNVERIFIED_DEFENSE_REBUTTAL" if any(m in low for m in defense_rebuttal_markers) else "CHRONOLOGICAL_FACT_REPORTED_BY_DEFENSE"
            else:
                epistemic = "UNVERIFIED_NEUTRAL_ASSERTION"
        elif str(env.get("semantic_type") or "") == "PARTY_ARGUMENT":
            epistemic = "UNVERIFIED_PROSECUTION_ALLEGATION" if context["speaker_role"] == "PROSECUTOR" else ("UNVERIFIED_DEFENSE_POSITION" if context["speaker_role"] == "DEFENSE_COUNSEL" else "UNVERIFIED_PARTY_ARGUMENT")
        elif str(env.get("semantic_type") or "") == "COUNTER_ARGUMENT":
            epistemic = "UNVERIFIED_DEFENSE_REBUTTAL" if context["speaker_role"] == "DEFENSE_COUNSEL" else "UNVERIFIED_COUNTER_ARGUMENT"

        env["provenance"] = (
            f"{provenance} | speaker_role={context['speaker_role']} | position={context['position']} "
            f"| stance={context['stance']} | epistemic_status={epistemic}"
        )
        env["domain_posture"] = f"{domain_posture} | adversarial_position={context['position']}"
        payload["semantic_envelope"] = env
        return LexiCoreContractEnforcer.enforce_routing(payload)

    @staticmethod
    def enforce_law_admission(
        law_payload: Dict[str, Any],
        *,
        case_domains: Iterable[str] = (),
        issue_text: str = "",
        case_text: str = "",
    ) -> Tuple[Dict[str, Any], bool, str]:
        """Reject clearly specialized cross-domain norms before Candidate Law.

        This is not substantive-law validation.  It only asks whether the source
        belongs to a subject-matter family that is absent from the active case/issue.
        General procedural/civil instruments are intentionally left for the normal
        law/tempus/status gates downstream.
        """
        payload = dict(law_payload or {})
        source = _clean(payload.get("text_payload") or payload.get("source") or payload.get("title") or payload.get("citation"))
        domain_hint = _clean((payload.get("semantic_envelope") or {}).get("domain_posture") or payload.get("domain"))
        blob = f"{source} {domain_hint}".lower()
        context = f"{issue_text} {case_text} {' '.join(str(x) for x in case_domains or [])}".lower()

        families = {
            "HKI": (
                ("hak cipta", "merek", "paten", "kekayaan intelektual", "lisensi teknologi", "perjanjian lisensi"),
                ("hki", "intellectual_property", "copyright", "trademark", "patent", "lisensi", "merek", "hak cipta"),
            ),
            "PERTAMBANGAN": (
                ("pertambangan", "izin usaha pertambangan", " iup", "mining", "minerba"),
                ("pertambangan", "mining", "minerba", "energi", "iup"),
            ),
            "PERTANAHAN": (
                ("pendaftaran tanah", "agraria", "hak atas tanah", "kantor pertanahan", "bpn", "sertipikat tanah"),
                ("land", "land_property", "pertanahan", "agraria", "tanah", "bpn"),
            ),
            "KETENAGAKERJAAN": (
                ("ketenagakerjaan", "hubungan industrial", "pemutusan hubungan kerja", " phk", "upah pekerja"),
                ("employment", "ketenagakerjaan", "industrial_relations", "buruh", "pekerja", "phk"),
            ),
            "KEPAILITAN": (
                ("kepailitan", "penundaan kewajiban pembayaran utang", " pkpu", "pailit"),
                ("bankruptcy", "kepailitan", "pkpu", "pailit"),
            ),
            "PIDANA": (
                ("tindak pidana", "kuhp", "tipikor", "pemberantasan tindak pidana korupsi", "pidana korupsi"),
                ("criminal", "corruption", "pidana", "tipikor", "korupsi", "tersangka", "terdakwa"),
            ),
        }

        for family, (source_markers, context_markers) in families.items():
            if any(marker in blob for marker in source_markers) and not any(marker in context for marker in context_markers):
                reason = f"SUBJECT_MATTER_MISMATCH_{family}"
                if "admission_contract" in payload:
                    adm = dict(payload.get("admission_contract") or {})
                    adm["admissibility_state"] = "REJECTED"
                    adm["prohibited_routes"] = list(dict.fromkeys((adm.get("prohibited_routes") or []) + ["Candidate Law", "Regulation/Tempus", "Norm Conflict"]))
                    adm["restricted_routes"] = [r for r in (adm.get("restricted_routes") or []) if r not in {"Candidate Law", "Regulation/Tempus", "Norm Conflict"}]
                    adm["rationale"] = reason
                    payload["admission_contract"] = adm
                    payload["downstream_migration"] = {
                        **(payload.get("downstream_migration") or {}),
                        "primary_target_node": "NONE",
                        "next_execution_directive": "DROP_CANDIDATE_SUBJECT_MATTER_MISMATCH",
                    }
                return payload, False, reason
        return payload, True, "SUBJECT_MATTER_ALIGNED_OR_GENERAL"
