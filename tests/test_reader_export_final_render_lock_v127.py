from exporters.common import (
    LexiCoreCivilPresentationSanitizer,
    _deduplicate_rendered_action_lines,
    prepare_case_export_for_reader,
    present_line,
)


def test_final_renderer_boundary_cleans_observed_residue_terms():
    raw=(
        'Kunci instrumen, status berlaku, tempus, case keterkaitan. '
        'Applicable law hanya candidate result. Acuan waktu: UNKNOWN_DATE. '
        'actual loss; outstanding principal; intervening acts; impact; '
        'keterkaitan semantik CREDIT, FIDUCIARY, LOSS; '
        'Unsur keterkaitan: existing_4; seluruh gate; level provisional.'
    )
    out=present_line(raw)
    for forbidden in (
        'case keterkaitan','candidate result','UNKNOWN_DATE','actual loss',
        'outstanding principal','intervening acts',' impact','existing_4',
        'seluruh gate','level provisional','CREDIT, FIDUCIARY, LOSS',
    ):
        assert forbidden.lower() not in out.lower()
    assert 'keterkaitan materi perkara' in out.lower()
    assert 'hasil kandidat hukum' in out.lower()
    assert 'belum ditentukan' in out.lower()
    assert 'kerugian nyata' in out.lower()
    assert 'sisa pokok kewajiban' in out.lower()
    assert 'tindakan atau faktor perantara' in out.lower()
    assert 'dampak' in out.lower()


def test_action_node_fingerprint_uses_reader_visible_action_text():
    actions=[
        {'action':'Dapatkan dan uji bukti primer.', 'issue':'Kerugian', 'source':'A'},
        {'action':'  Dapatkan   dan uji bukti primer. ', 'issue':'Kausalitas', 'source':'B'},
    ]
    out=LexiCoreCivilPresentationSanitizer.deduplicate_actions(actions)
    assert len(out)==1
    assert out[0]['issue']=='Kerugian'


def test_final_render_deduplicates_actions_only_inside_same_chain():
    lines=[
        'RANTAI E3 | Status: Ditahan',
        'TINDAKAN: Dapatkan dan uji bukti primer yang sama.',
        'TINDAKAN: Dapatkan   dan uji bukti primer yang sama.',
        'BUKTI: Dapatkan dan uji bukti primer yang sama.',
        'RANTAI E4 | Status: Ditahan',
        'TINDAKAN: Dapatkan dan uji bukti primer yang sama.',
    ]
    out=_deduplicate_rendered_action_lines('Rantai Penalaran Hukum Kanonik', lines)
    assert sum(1 for x in out if x.startswith('TINDAKAN:'))==2
    assert any(x.startswith('BUKTI:') for x in out)


def test_non_chain_sections_are_never_deduplicated_by_final_render_lock():
    lines=['TINDAKAN: sama','TINDAKAN: sama']
    assert _deduplicate_rendered_action_lines('Rencana Tindakan', lines)==lines


def test_prepare_case_export_applies_final_render_lock():
    sections=[('Rantai Penalaran Hukum Kanonik',[
        'RANTAI E3 | Status: HOLD',
        'TINDAKAN: Dapatkan dan uji bukti primer yang secara langsung menjawab gap ini.',
        'TINDAKAN: Dapatkan dan uji bukti primer yang secara langsung menjawab gap ini.',
        'Acuan waktu: UNKNOWN_DATE | case keterkaitan | candidate result',
    ])]
    _, cleaned=prepare_case_export_for_reader([], sections)
    lines=cleaned[0][1]
    assert sum(1 for x in lines if x.startswith('TINDAKAN:'))==1
    joined='\n'.join(lines)
    assert 'UNKNOWN_DATE' not in joined
    assert 'case keterkaitan' not in joined.lower()
    assert 'candidate result' not in joined.lower()
