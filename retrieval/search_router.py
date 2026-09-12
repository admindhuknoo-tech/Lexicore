"""Retrieval-only candidate-law relevance router.

This module is deliberately outside SAL and the positive-law verifier.  It may
rank, degrade, or drop discovery hits before they consume candidate-law budget;
it may never mark a rule applicable, valid for the case, or temporally valid.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().with_name("law_weight_config.json")


class LexiCoreLawRetrievalRouter:
    def __init__(self, config_path: str | Path = DEFAULT_CONFIG):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))

    @staticmethod
    def _text(row: dict[str, Any]) -> str:
        # Query text is intentionally excluded: a good query must not launder a
        # bad search result into a materially relevant candidate.
        return " ".join(str(row.get(k) or "") for k in ("title", "description", "snippet", "text_payload")).lower()

    @staticmethod
    def _active_domain_ids(domains: list[dict] | None) -> set[str]:
        return {
            str(d.get("id"))
            for d in (domains or [])
            if isinstance(d, dict) and d.get("id") and d.get("role") != "SUPPORTING_ONLY"
        }

    def _protected_candidate(self, text: str) -> dict[str, Any] | None:
        for item in self.config.get("protected_candidate_laws") or []:
            patterns = [item.get("pattern")] + list(item.get("aliases") or [])
            if any(str(p or "").lower() in text for p in patterns if p):
                return item
        return None

    def evaluate_candidate(self, row: dict[str, Any], domains: list[dict] | None = None) -> dict[str, Any]:
        text = self._text(row)
        active = self._active_domain_ids(domains)
        activation = self.config.get("activation") or {}
        preferred = set(activation.get("prefer_combination") or [])
        target_profile_active = bool(preferred and preferred.issubset(active))
        thresholds = self.config.get("thresholds") or {}
        positive_rules = self.config.get("positive_allow_rules") or {}
        mismatch_rules = self.config.get("institutional_mismatch_rules") or {}

        protected = self._protected_candidate(text)
        positive_hits: list[str] = []
        anchor_groups: set[str] = set()
        score = float(row.get("initial_vector_score") or row.get("relevance_score") or 0.0)
        candidate_role = "SUBSTANTIVE_CANDIDATE"

        for rule_name, rule in positive_rules.items():
            allowed_domains = set(rule.get("domains") or [])
            if allowed_domains and active and not (allowed_domains & active):
                continue
            hits = [kw for kw in (rule.get("keywords") or []) if str(kw).lower() in text]
            if hits:
                anchor_groups.add(rule_name)
                positive_hits.extend(f"{rule_name}:{kw}" for kw in hits)
                # Bounded group-level boost: repeating the same keyword does not
                # repeatedly inflate the score.
                score += float(rule.get("weight") or 0.0)
                if rule.get("candidate_role") == "CONTEXTUAL_LAW":
                    candidate_role = "CONTEXTUAL_LAW"

        # Generic domain profiles provide a second independent positive anchor
        # for canonical/strong statutes without depending on the originating
        # query. This keeps the target profile strict while preserving general
        # LexiCore domains outside corruption-banking cases.
        profiles = self.config.get("generic_domain_profiles") or {}
        for domain_id in active:
            profile = profiles.get(domain_id) or {}
            strong_hits = [kw for kw in (profile.get("strong_positive_terms") or []) if str(kw).lower() in text]
            ordinary_hits = [kw for kw in (profile.get("positive_terms") or []) if str(kw).lower() in text]
            if strong_hits:
                anchor_groups.add(f"generic:{domain_id}:strong")
                positive_hits.extend(f"generic:{domain_id}:strong:{kw}" for kw in strong_hits)
                score += 0.55
            elif ordinary_hits:
                anchor_groups.add(f"generic:{domain_id}")
                positive_hits.extend(f"generic:{domain_id}:{kw}" for kw in ordinary_hits)
                score += 0.20

        hard_drop_reasons: list[str] = []
        degraded_reasons: list[str] = []
        kpk_rule = mismatch_rules.get("kpk_internal_personnel_governance") or {}
        issuer_hit = any(str(kw).lower() in text for kw in (kpk_rule.get("issuer_keywords") or []))
        subject_hit = any(str(kw).lower() in text for kw in (kpk_rule.get("subject_keywords") or []))
        if target_profile_active and issuer_hit and subject_hit and not protected:
            hard_drop_reasons.append(kpk_rule.get("reason") or "INTERNAL_INSTITUTIONAL_GOVERNANCE_NO_CASE_NEXUS")

        cross = mismatch_rules.get("cross_domain_mismatch") or {}
        cross_hits = [kw for kw in (cross.get("keywords") or []) if str(kw).lower() in text]
        if target_profile_active and cross_hits and not protected:
            score *= max(0.0, 1.0 - float(cross.get("penalty") or 0.0))
            degraded_reasons.extend(f"{cross.get('reason') or 'CROSS_DOMAIN_SUBJECT_MATTER_MISMATCH'}:{kw}" for kw in cross_hits)

        max_score = float(thresholds.get("max_final_score") or 1.0)
        score = max(0.0, min(score, max_score))
        min_anchors = int(thresholds.get("minimum_positive_anchors") or 1) if target_profile_active else 1
        threshold = float(thresholds.get("candidate_min_score") or 0.75)

        # Protected means only "do not discard at retrieval". It never means
        # applicable, verified, governing, or tempus-safe. The aggressive score
        # threshold applies only to the targeted corruption+banking profile;
        # other LexiCore domains retain generic positive-nexus admission.
        positive_proof = bool(protected) or len(anchor_groups) >= min_anchors
        rejected = bool(hard_drop_reasons) or (not positive_proof)
        if target_profile_active and not protected and score < threshold:
            rejected = True
        status = "REJECTED_SUBJECT_MATTER_UNPROVEN" if rejected else "POSITIVE_NEXUS_VERIFIED"

        return {
            "status": status,
            "final_retrieval_score": round(score, 4),
            "positive_hits": positive_hits,
            "positive_anchor_groups": sorted(anchor_groups),
            "positive_proof": positive_proof,
            "hard_drop_reasons": hard_drop_reasons,
            "degraded_reasons": degraded_reasons,
            "protected_candidate": bool(protected),
            "protected_candidate_role": (protected or {}).get("role"),
            "protected_effect": (protected or {}).get("effect"),
            "candidate_role": candidate_role,
            "target_profile_active": target_profile_active,
            "policy_version": self.config.get("contract_version") or self.config.get("config_version") or "LAW-RETRIEVAL-WEIGHT-UNKNOWN",
            "may_mark_applicable_law": False,
            "may_override_tempus": False,
        }

    def apply_retrieval_weights(self, raw_search_results: list[dict[str, Any]], domains: list[dict] | None = None) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for law in raw_search_results or []:
            decision = self.evaluate_candidate(law, domains)
            law = dict(law)
            law["law_weight_policy"] = decision
            law["final_retrieval_score"] = decision["final_retrieval_score"]
            law["candidate_role"] = decision["candidate_role"]
            if decision["status"] == "POSITIVE_NEXUS_VERIFIED":
                filtered.append(law)
        return filtered
