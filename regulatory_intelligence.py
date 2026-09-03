"""LexiCore Regulatory Intelligence Foundation.

This module ports the *data-model and graph concepts* observed in LEGAL.zip
into the existing Python/Flask LexiCore stack without introducing Node,
PostgreSQL, Neo4j, RabbitMQ, Redis, or Elasticsearch.

Design constraints:
- Existing local corpus remains a working retrieval aid, never final authority.
- No demo/seed legal propositions from LEGAL.zip are imported as verified law.
- Every article is qualified by its parent regulation.
- Relationships are explicit and typed; inferred relationships are labelled.
- Conflict resolution is issue-spotting, not a final legal determination.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import date
import re

from regulatory_db import get_all_regulations, search_regulations, corpus_stats

HIERARCHY = {
    'UUD': 1,
    'TAP_MPR': 2,
    'UU': 3,
    'PERPPU': 3,
    'PP': 4,
    'PERPRES': 5,
    # Ministerial / agency regulations are recognized instruments whose
    # validity depends on delegation/authority; kept below Perpres here only
    # for conflict-screening, not as a final legal-validity determination.
    'PER_MENTERI': 6,
    'PER_LEMBAGA': 6,
    'POJK': 6,
    'PERDA_PROV': 7,
    'PERDA_KAB': 8,
    # Judicial instruments are not forced into the statutory hierarchy.
    'PERMA': 90,
    'SEMA': 91,
}

RELATION_TYPES = {
    'MENGUBAH', 'DICABUT_OLEH', 'DIJELASKAN_OLEH', 'DILAKSANAKAN_OLEH',
    'DIUJI_OLEH', 'BERTENTANGAN_DENGAN', 'DIGUNAKAN_DALAM',
    'LEX_SPECIALIS_DARI', 'MERATIFIKASI', 'MERUJUK', 'TERKAIT_DENGAN'
}


def _norm_type(reg: Dict[str, Any]) -> str:
    t = (reg.get('jenis') or '').upper().strip()
    if t in HIERARCHY:
        return t
    n = (reg.get('nomor') or '').upper()
    if 'POJK' in n or 'OTORITAS JASA KEUANGAN' in (reg.get('tentang') or '').upper():
        return 'POJK'
    return t or 'UNKNOWN'


def _rank(reg: Dict[str, Any]) -> int:
    explicit = reg.get('hierarchy_rank')
    try:
        if explicit is not None:
            return int(explicit)
    except Exception:
        pass
    return HIERARCHY.get(_norm_type(reg), 99)


def qualified_article_id(reg: Dict[str, Any], art: Dict[str, Any]) -> str:
    rid = str(reg.get('id') or 'unknown-regulation')
    aid = str(art.get('id') or re.sub(r'[^a-z0-9]+', '-', (art.get('pasal') or 'article').lower()).strip('-'))
    return f'{rid}::{aid}'


def qualified_citation(reg: Dict[str, Any], art: Dict[str, Any]) -> str:
    return f"{reg.get('nomor') or reg.get('tentang') or 'Peraturan tidak teridentifikasi'} — {art.get('pasal') or 'Pasal tidak teridentifikasi'}"


def _build_relationships(regulations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build only relationships supported by corpus metadata.

    Cross references and court-decision references are not upgraded into a
    substantive legal conclusion. They are labelled MERUJUK / DIUJI_OLEH and
    remain verification-pending.
    """
    out: List[Dict[str, Any]] = []
    by_id = {r.get('id'): r for r in regulations}
    seen = set()
    for reg in regulations:
        for art in reg.get('articles', []):
            source = qualified_article_id(reg, art)
            for target_reg_id in art.get('cross_references', []) or []:
                target_reg = by_id.get(target_reg_id)
                if not target_reg:
                    continue
                key = (source, target_reg_id, 'MERUJUK')
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    'source_id': source,
                    'source_citation': qualified_citation(reg, art),
                    'target_id': target_reg_id,
                    'target_citation': target_reg.get('nomor') or target_reg.get('tentang'),
                    'relation_type': 'MERUJUK',
                    'basis': 'Explicit cross_references metadata in local corpus',
                    'verification_status': 'LOCAL_METADATA — OFFICIAL SOURCE VERIFICATION REQUIRED',
                })
            for decision in art.get('related_court_decisions', []) or []:
                key = (source, decision, 'DIUJI_OLEH')
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    'source_id': source,
                    'source_citation': qualified_citation(reg, art),
                    'target_id': decision,
                    'target_citation': decision,
                    'relation_type': 'DIUJI_OLEH',
                    'basis': 'Explicit related_court_decisions metadata in local corpus',
                    'verification_status': 'LOCAL_METADATA — OFFICIAL COURT SOURCE VERIFICATION REQUIRED',
                })
    return out


def normalized_catalog() -> Dict[str, Any]:
    regulations = get_all_regulations()
    nodes_reg = []
    nodes_art = []
    for reg in regulations:
        reg_node = {
            'id': reg.get('id'),
            'kind': 'REGULATION',
            'type': _norm_type(reg),
            'number': reg.get('nomor'),
            'year': reg.get('tahun'),
            'title': reg.get('tentang'),
            'status': reg.get('status'),
            'hierarchy_rank': _rank(reg),
            'promulgation_date': reg.get('promulgation_date'),
            'effective_date': reg.get('effective_date'),
            'official_url': reg.get('official_url'),
            'authority_source': reg.get('jdih_source'),
            'verification_status': 'LOCAL CORPUS RECORD — OFFICIAL SOURCE VERIFICATION REQUIRED',
        }
        nodes_reg.append(reg_node)
        for art in reg.get('articles', []):
            nodes_art.append({
                'id': qualified_article_id(reg, art),
                'kind': 'ARTICLE',
                'regulation_id': reg.get('id'),
                'regulation': reg.get('nomor') or reg.get('tentang'),
                'article': art.get('pasal'),
                'qualified_citation': qualified_citation(reg, art),
                'topic': art.get('topic'),
                'text': art.get('content'),
                'keywords': art.get('keywords') or [],
                'status': art.get('status') or reg.get('status'),
                'verification_status': 'LOCAL CORPUS ARTICLE — OFFICIAL SOURCE VERIFICATION REQUIRED',
            })
    relationships = _build_relationships(regulations)
    return {
        'regulations': nodes_reg,
        'articles': nodes_art,
        'relationships': relationships,
        'counts': {
            'regulations': len(nodes_reg),
            'articles': len(nodes_art),
            'relationships': len(relationships),
        },
        'model': 'REGULATION_ARTICLE_RELATIONSHIP_V1_3_5',
        'corpus_stats': corpus_stats(),
        'professional_verification': 'PENDING',
    }


def graph_for_query(query: str = '', limit: int = 10) -> Dict[str, Any]:
    catalog = normalized_catalog()
    if not query.strip():
        regs = catalog['regulations'][:limit]
    else:
        hits = search_regulations(query, limit=limit)
        ids = {h.get('regulation', {}).get('id') for h in hits}
        regs = [r for r in catalog['regulations'] if r.get('id') in ids]
    reg_ids = {r['id'] for r in regs}
    arts = [a for a in catalog['articles'] if a.get('regulation_id') in reg_ids]
    node_ids = {a['id'] for a in arts} | reg_ids
    rels = [r for r in catalog['relationships'] if r.get('source_id') in node_ids or r.get('target_id') in node_ids]
    return {
        'query': query,
        'regulations': regs,
        'articles': arts,
        'relationships': rels,
        'coverage_note': 'Graph is generated from the local curated corpus. A relationship is not final legal authority until verified against official sources.',
        'professional_verification': 'PENDING',
    }


def timeline_for_regulation(regulation_id: Optional[str] = None, query: str = '') -> Dict[str, Any]:
    regulations = get_all_regulations()
    selected = []
    if regulation_id:
        selected = [r for r in regulations if r.get('id') == regulation_id]
    elif query.strip():
        selected = [h['regulation'] for h in search_regulations(query, limit=8)]
    else:
        selected = regulations

    events = []
    for reg in selected:
        base = {'regulation_id': reg.get('id'), 'citation': reg.get('nomor') or reg.get('tentang'), 'status': reg.get('status')}
        if reg.get('promulgation_date'):
            events.append({**base, 'date': reg.get('promulgation_date'), 'event': 'PROMULGATED'})
        if reg.get('effective_date'):
            events.append({**base, 'date': reg.get('effective_date'), 'event': 'EFFECTIVE'})
    events.sort(key=lambda x: str(x.get('date') or ''))
    return {
        'events': events,
        'coverage_note': 'Timeline reflects dates recorded in the local corpus only. Amendment, repeal, transition, and court-review effects must be verified against official sources.',
        'professional_verification': 'PENDING',
    }


def _extract_year(reg: Dict[str, Any]) -> Optional[int]:
    try:
        return int(reg.get('tahun'))
    except Exception:
        return None


def compare_regulations(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic hierarchy/temporal comparison without pretending to decide lex specialis."""
    ar, br = _rank(a), _rank(b)
    ay, by = _extract_year(a), _extract_year(b)
    hierarchy = {
        'a_rank': ar, 'b_rank': br,
        'a_type': _norm_type(a), 'b_type': _norm_type(b),
        'result': 'SAME_OR_UNRESOLVED_LEVEL'
    }
    if ar < br:
        hierarchy['result'] = 'A_HIGHER'
    elif br < ar:
        hierarchy['result'] = 'B_HIGHER'

    temporal = {'result': 'UNRESOLVED', 'a_year': ay, 'b_year': by}
    if ay and by and ay != by:
        temporal['result'] = 'A_NEWER' if ay > by else 'B_NEWER'
    elif ay and by:
        temporal['result'] = 'SAME_YEAR'

    return {
        'norm_a': {'id': a.get('id'), 'citation': a.get('nomor') or a.get('tentang'), 'type': _norm_type(a), 'year': ay, 'rank': ar},
        'norm_b': {'id': b.get('id'), 'citation': b.get('nomor') or b.get('tentang'), 'type': _norm_type(b), 'year': by, 'rank': br},
        'lex_superior_screen': hierarchy,
        'lex_posterior_screen': temporal,
        'lex_specialis_screen': {
            'result': 'REQUIRES_SUBJECT_MATTER_AND_SCOPE_ANALYSIS',
            'reason': 'Specificity cannot be safely inferred from hierarchy or year alone.'
        },
        'final_applicable_norm': 'NOT_DETERMINED',
        'verification_status': 'PROFESSIONAL VERIFICATION: PENDING',
    }


def resolve_conflict_from_query(query_a: str, query_b: str, context: str = '') -> Dict[str, Any]:
    ha = search_regulations(query_a, limit=1)
    hb = search_regulations(query_b, limit=1)
    if not ha or not hb:
        return {
            'success': False,
            'error': 'Satu atau kedua norma tidak dapat diidentifikasi pada corpus lokal. Gunakan identitas peraturan yang lebih lengkap (jenis/nomor/tahun/pasal).',
            'query_a': query_a, 'query_b': query_b,
            'professional_verification': 'PENDING',
        }
    result = compare_regulations(ha[0]['regulation'], hb[0]['regulation'])
    result['context'] = context
    result['success'] = True
    result['coverage_note'] = 'Lex superior and temporal screens are deterministic. Lex specialis and final applicability remain legal-analysis questions requiring exact text, delegation, transition rules, and official-source verification.'
    return result


def intelligence_for_case(regulatory_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    ids = []
    for hit in regulatory_matches or []:
        rid = (hit.get('regulation') or {}).get('id')
        if rid and rid not in ids:
            ids.append(rid)
    catalog = normalized_catalog()
    regs = [r for r in catalog['regulations'] if r['id'] in ids]
    arts = [a for a in catalog['articles'] if a.get('regulation_id') in ids]
    node_ids = set(ids) | {a['id'] for a in arts}
    rels = [r for r in catalog['relationships'] if r.get('source_id') in node_ids or r.get('target_id') in node_ids]
    timeline = []
    for rid in ids:
        timeline.extend(timeline_for_regulation(regulation_id=rid)['events'])
    timeline.sort(key=lambda x: str(x.get('date') or ''))
    return {
        'regulations': regs,
        'articles': arts,
        'relationships': rels,
        'timeline': timeline,
        'model': 'REGULATORY_INTELLIGENCE_V1_3_5',
        'professional_verification': 'PENDING',
    }
