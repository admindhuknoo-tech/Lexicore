"""General Case Analysis projection/orchestration guards for LexiCore RC18.

This layer is intentionally domain-agnostic.  It does not decide that a case is
"DKPP", "Tipikor", "waris", etc.  Instead it derives the document's procedural
posture from structural language in the source, exposes material tempus from the
canonical extractor, and prevents a downstream template for one procedural
posture from leaking into another.

It does not replace Regulatory Corpus, positive-law verification, evidence
mapping, or professional review.  Those remain authoritative supporting layers.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, Iterable

from services.material_tempus_extractor import select_material_tempus


def infer_document_posture(text: str) -> Dict[str, Any]:
    """Backward-compatible wrapper around the canonical posture resolver."""
    from services.document_posture_resolver import resolve_document_posture
    return resolve_document_posture({}, {'source_text': text})


_RESPONSE_REPLACEMENTS = (
    (re.compile(r'eksepsi\s*/\s*nota keberatan', re.I), 'jawaban atas pengaduan'),
    (re.compile(r'petitum\s+eksepsi(?:/pembelaan)?', re.I), 'petitum jawaban'),
    (re.compile(r'\bsurat dakwaan\b', re.I), 'pokok aduan'),
    (re.compile(r'\bdakwaan\b', re.I), 'aduan'),
    (re.compile(r'\beksepsi\b', re.I), 'jawaban/keberatan'),
)


def _rewrite_generated(value: Any, replacements) -> Any:
    if isinstance(value, str):
        out = value
        for pattern, repl in replacements:
            out = pattern.sub(repl, out)
        return out
    if isinstance(value, list):
        return [_rewrite_generated(v, replacements) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite_generated(v, replacements) for k, v in value.items()}
    return value


def _collapse_empty_norm_conflicts(value: Any) -> Any:
    """Collapse repeated NONE pseudo-conflicts without suppressing real conflicts."""
    if isinstance(value, list):
        if value and all(
            isinstance(row, dict)
            and str(row.get('status') or row.get('result') or row.get('conflict') or '').upper() in {'NONE', 'NO_CONFLICT', ''}
            for row in value
        ):
            return {'status': 'NO_MATERIAL_NORM_CONFLICT_IDENTIFIED', 'conflicts': [], 'count': 0}
        return value
    if isinstance(value, dict):
        rows = value.get('conflicts') or value.get('items') or value.get('potential_conflicts')
        if isinstance(rows, list) and rows and all(
            isinstance(row, dict)
            and str(row.get('status') or row.get('result') or row.get('conflict') or '').upper() in {'NONE', 'NO_CONFLICT', ''}
            for row in rows
        ):
            out = dict(value)
            for key in ('conflicts', 'items', 'potential_conflicts'):
                if key in out:
                    out[key] = []
            out['status'] = 'NO_MATERIAL_NORM_CONFLICT_IDENTIFIED'
            out['count'] = 0
            return out
    return value


def apply_general_case_orchestration(result: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    """Apply universal case projection just before readiness/working-paper build.

    Source/evidence ledgers are never rewritten.  Only generated presentation and
    recommendation sections are normalized when their terminology contradicts
    the source document posture.
    """
    out = copy.deepcopy(result or {})
    from services.document_posture_resolver import resolve_document_posture
    posture = resolve_document_posture(out.get('domain_classification') or {}, {'source_text': source_text})
    # Presentation/provenance-only adversarial fingerprint. A decisive identity
    # corrects document posture even when OCR loses the physical first-page header.
    from services.contract_enforcer import LexiCoreContractEnforcer
    adv_identity = LexiCoreContractEnforcer.resolve_document_adversarial_identity(source_text)
    if adv_identity.get('speaker_role') != 'UNKNOWN':
        posture = dict(posture)
        posture['document_type'] = adv_identity.get('document_posture')
        posture['adversarial_speaker_role'] = adv_identity.get('speaker_role')
        posture['adversarial_position'] = adv_identity.get('position')
        posture['adversarial_identity_status'] = adv_identity.get('identity_status')
    tempus = out.get('material_tempus') or select_material_tempus(source_text)
    out['general_case_reasoning'] = {
        'document_posture': posture,
        'material_tempus': tempus,
        'architecture': 'GENERAL_FACT_EVIDENCE_POSTURE_ORCHESTRATION',
        'adversarial_document_identity': adv_identity,
    }
    out['material_tempus'] = tempus
    out['document_posture_profile'] = posture
    out['adversarial_document_identity'] = adv_identity

    # Do not modify source_text, source_ledger, evidence ledger, quotations, or
    # official verification records.  Normalize only generated projection areas.
    if posture['posture'] == 'RESPONSE_TO_COMPLAINT':
        generated_keys = (
            'executive_review', 'professional_review', 'document_review',
            'legal_analysis', 'recommendations', 'strategic_recommendations',
            'strategy', 'action_plan', 'case_summary', 'audit_findings',
        )
        for key in generated_keys:
            if key in out:
                out[key] = _rewrite_generated(out[key], _RESPONSE_REPLACEMENTS)
        # Common scalar projections used by exporters/renderers.
        for key in ('document_type', 'document_classification', 'review_document_type'):
            if key in out and isinstance(out[key], str):
                out[key] = posture['document_type']

    out['norm_conflicts'] = _collapse_empty_norm_conflicts(out.get('norm_conflicts'))
    return out
