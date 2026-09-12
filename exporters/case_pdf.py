"""Professional PDF renderer for Case Analysis."""
from io import BytesIO
from identity_profile import get_identity_profile
from .common import (
    _case_export_sections,
    prepare_case_export_for_reader,
    _presentation_source_corpus,
    LexiCoreCivilPresentationSanitizer,
    LexiCoreLowLevelRenderGovernor,
)

F4_MM = (215.0, 330.0)


def _roman(number: int) -> str:
    values = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    n = int(number)
    out = []
    for value, symbol in values:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)


def _legal_chapter_heading(number: int, heading: str) -> str:
    return f"{_roman(number)}. {str(heading or '').strip().rstrip('.').upper()}"


def export_case_pdf(x):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
        from xml.sax.saxutils import escape as xml_escape
    except ImportError as exc:
        raise RuntimeError('Export PDF membutuhkan reportlab. Jalankan: py -m pip install reportlab') from exc

    profile = get_identity_profile()
    meta, sections = _case_export_sections(x)
    meta, sections = prepare_case_export_for_reader(meta, sections)
    posture_label = LexiCoreCivilPresentationSanitizer.resolve_civil_posture_label(
        _presentation_source_corpus(x)
    )
    governor = LexiCoreLowLevelRenderGovernor(is_civil=bool(posture_label))

    bio = BytesIO()
    navy = colors.HexColor('#10263D')
    gold = colors.HexColor('#D8B65C')
    ink = colors.HexColor('#1F2937')
    muted = colors.HexColor('#66717F')
    line = colors.HexColor('#D8DEE6')
    soft = colors.HexColor('#F4F7FA')
    green = colors.HexColor('#157452')

    f4 = (F4_MM[0] * mm, F4_MM[1] * mm)
    doc = SimpleDocTemplate(
        bio,
        pagesize=f4,
        leftMargin=28 * mm,
        rightMargin=22 * mm,
        topMargin=24 * mm,
        bottomMargin=22 * mm,
        title='LexiCore Case Analysis',
        author=profile["signatory_name"],
    )

    ss = getSampleStyleSheet()
    # Times is a built-in ReportLab face; this avoids shipping or depending on
    # external font files while keeping the legal-report body typographically stable.
    title = ParagraphStyle(
        'LC_Title', parent=ss['Title'], fontName='Times-Bold', fontSize=16,
        leading=19, alignment=TA_CENTER, textColor=navy, spaceAfter=5,
    )
    subtitle = ParagraphStyle(
        'LC_Sub', parent=ss['Normal'], fontName='Times-Roman', fontSize=8.5,
        leading=10.5, alignment=TA_CENTER, textColor=muted, spaceAfter=10,
    )
    chapter = ParagraphStyle(
        'LC_Legal_Chapter', parent=ss['Heading1'], fontName='Times-Bold',
        fontSize=12.5, leading=15, alignment=TA_LEFT, textColor=navy,
        firstLineIndent=0, spaceBefore=9, spaceAfter=5, keepWithNext=True,
    )
    body = ParagraphStyle(
        'LC_Legal_Body', parent=ss['BodyText'], fontName='Times-Roman',
        fontSize=10.5, leading=14, alignment=TA_JUSTIFY, textColor=ink,
        firstLineIndent=0, spaceAfter=3,
    )
    body_no_indent = ParagraphStyle(
        'LC_Legal_Body_NoIndent', parent=body, firstLineIndent=0,
    )
    small = ParagraphStyle(
        'LC_Legal_Small', parent=body_no_indent, fontSize=8.5, leading=10.5,
        textColor=muted, spaceAfter=3,
    )
    label_style = ParagraphStyle(
        'LC_Legal_Label', parent=body_no_indent, fontName='Times-Bold',
        fontSize=10.5, leading=13, spaceBefore=3, spaceAfter=2,
    )

    def clean(v):
        t = (str(v)
             .replace('\u2018', "'").replace('\u2019', "'")
             .replace('\u201c', '"').replace('\u201d', '"')
             .replace('\u2013', '-').replace('\u2014', '-')
             .replace('\u2022', '-'))
        return t.encode('latin-1', 'replace').decode('latin-1')

    def P(text, style=body_no_indent, bold=False, intercept=False):
        value = governor.intercept(text) if intercept else governor.sanitize(text)
        if value is None:
            return None
        t = xml_escape(clean(value)).replace('\n', '<br/>')
        return Paragraph(('<b>' + t + '</b>') if bold else t, style)

    def _table_paragraph(value, *, header=False):
        style = ParagraphStyle(
            'LC_Table_Header' if header else 'LC_Table_Cell',
            parent=body_no_indent,
            fontName='Times-Bold' if header else 'Times-Roman',
            fontSize=8.3 if header else 8.1,
            leading=10.0 if header else 9.8,
            alignment=TA_LEFT if header else TA_JUSTIFY,
            textColor=colors.white if header else ink,
            firstLineIndent=0,
            spaceAfter=0,
        )
        return Paragraph(xml_escape(clean(governor.sanitize(str(value or '-')))).replace('\n', '<br/>'), style)

    def _styled_table(rows, widths, headers):
        data = [[_table_paragraph(h, header=True) for h in headers]]
        for row in rows:
            data.append([_table_paragraph(v) for v in row])
        table = Table(data, colWidths=[w * mm for w in widths], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOX', (0, 0), (-1, -1), .45, colors.HexColor('#9AA6B2')),
            ('INNERGRID', (0, 0), (-1, -1), .25, colors.HexColor('#C6CDD5')),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return table

    def _split_pipe(value):
        return [part.strip() for part in str(value or '').split(' | ')]

    def _summary_matrix_projection(lines):
        """Project the executive findings matrix into a reader-facing table.

        This is display-only. It preserves every cell's rendered text and never
        changes the underlying finding/recommendation objects.
        """
        before, rows, after = [], [], []
        in_matrix = False
        for line0 in lines:
            value = governor.intercept(line0)
            if value is None:
                continue
            text = str(value).strip()
            if text.startswith('Matriks temuan utama:'):
                in_matrix = True
                continue
            parts = _split_pipe(text)
            if in_matrix and len(parts) == 4 and not text.startswith('- '):
                rows.append(parts)
                continue
            if in_matrix:
                in_matrix = False
            (after if rows else before).append(text)
        return before, rows, after

    def _evidence_table_projection(lines):
        before, rows, after = [], [], []
        marker_seen = False
        for line0 in lines:
            value = governor.intercept(line0)
            if value is None:
                continue
            text = str(value).strip()
            if text.startswith('TABEL:'):
                marker_seen = True
                continue
            parts = _split_pipe(text)
            if marker_seen and len(parts) == 4 and text.startswith('['):
                rows.append(parts)
                continue
            (after if marker_seen else before).append(text)
        return before, rows, after, marker_seen

    def _action_plan_projection(lines):
        rows, remainder = [], []
        for line0 in lines:
            value = governor.intercept(line0)
            if value is None:
                continue
            text = str(value).strip()
            parts = _split_pipe(text)
            if text.startswith('Langkah ') and len(parts) >= 6:
                step, window, priority, action, objective, condition = parts[:6]
                step = step.split(' ', 1)[1].strip() if step.startswith('Langkah ') else step
                condition = condition.split(':', 1)[1].strip() if condition.startswith('Kondisi:') else condition
                rows.append((step, f'{window}\n{priority}', f'{action}\n{objective}', condition))
            else:
                remainder.append(text)
        return rows, remainder

    def _candidate_law_projection(lines):
        rows, remainder = [], []
        for line0 in lines:
            value = governor.intercept(line0)
            if value is None:
                continue
            text = str(value).strip()
            parts = _split_pipe(text)
            if len(parts) == 3 and parts[0].startswith('Ranah hukum:') and parts[1].startswith('Sumber:'):
                rows.append((
                    parts[0].split(':', 1)[1].strip(),
                    parts[1].split(':', 1)[1].strip(),
                    parts[2].split(':', 1)[1].strip() if ':' in parts[2] else parts[2],
                ))
            else:
                remainder.append(text)
        return rows, remainder

    def readiness_table(lines):
        vals = {}
        disclaimer = ''
        for line0 in lines:
            z = governor.intercept(line0)
            if z is None:
                continue
            z = str(z)
            if ':' in z and '%' in z:
                k, v = z.split(':', 1)
                vals[k.strip()] = v.strip()
            elif z:
                disclaimer = z
        cells = []
        for key, label in (
            ('Kesiapan keseluruhan', 'KESELURUHAN'),
            ('Pemetaan bukti', 'BUKTI'),
            ('Analisis Hukum', 'HUKUM'),
            ('Rencana tindakan', 'TINDAKAN'),
        ):
            pct = vals.get(key, '0%')
            cells.append(Paragraph(
                f'<font size="12"><b>{xml_escape(clean(pct))}</b></font><br/>'
                f'<font size="8">{xml_escape(clean(label))}</font>',
                body_no_indent,
            ))
        # Available text width on F4 with 28/22 mm margins is 165 mm.
        t = Table([cells], colWidths=[41.25 * mm] * 4)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#EAF6F0')),
            ('BACKGROUND', (1, 0), (-1, 0), soft),
            ('TEXTCOLOR', (0, 0), (0, 0), green),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), .4, line),
            ('INNERGRID', (0, 0), (-1, -1), .25, line),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        return [t, Spacer(1, 2 * mm), P(disclaimer, small)] if disclaimer else [t]

    def is_structured_line(text: str) -> bool:
        prefixes = (
            'ISU:', 'FAKTA/DALIL:', 'SUMBER:', 'ATURAN:', 'ANALISIS:', 'STATUS:',
            'HUKUM YANG BERLAKU:', 'UNSUR HUKUM:', 'PERBUATAN YANG DIDALILKAN:',
            'BUKTI:', 'BUKTI/BANTAHAN LAWAN:', 'UJI UNSUR:', 'KAUSALITAS:',
            'RISIKO:', 'KLASIFIKASI PROSEDURAL/POKOK PERKARA:',
            'TINDAKAN YANG DIREKOMENDASIKAN:', 'TINDAKAN:', 'RANTAI ',
            'Langkah ', 'Ranah hukum:',
        )
        return text.startswith(prefixes) or (' | ' in text)

    story = []

    # Preserve LexiCore brand identity, but scale masthead to the legal F4 text area.
    brand_left = [
        Paragraph('<b>LC</b>', ParagraphStyle(
            'brand', parent=body_no_indent, alignment=TA_CENTER,
            textColor=navy, fontName='Times-Bold', fontSize=14, leading=15)),
        Paragraph(xml_escape(clean((profile.get('watermark_text') or profile['display_name'])[:12])), ParagraphStyle(
            'brandSmall', parent=body_no_indent, alignment=TA_CENTER,
            textColor=navy, fontName='Times-Roman', fontSize=6.5, leading=7)),
    ]
    brand_right = [
        Paragraph('<b>LexiCore</b>', ParagraphStyle(
            'brandTitle', parent=body_no_indent, textColor=colors.white,
            fontName='Times-Bold', fontSize=17, leading=19, spaceAfter=1)),
        Paragraph(f"Evidence-to-Action Case Analysis | {profile['display_name']}",
                  ParagraphStyle('brand2', parent=body_no_indent,
                                 textColor=colors.HexColor('#E5EAF0'),
                                 fontName='Times-Roman', fontSize=7.2, leading=8.5)),
    ]
    brand = Table([[brand_left, brand_right]], colWidths=[20 * mm, 145 * mm])
    brand.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), gold),
        ('BACKGROUND', (1, 0), (1, 0), navy),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story += [
        brand,
        Spacer(1, 3 * mm),
        Paragraph(xml_escape(clean(governor.sanitize(x.get('title') or 'Case Analysis'))), title),
        Paragraph('KERTAS KERJA | MENUNGGU VERIFIKASI PROFESIONAL', subtitle),
    ]

    data = [[P(k, small, bold=True), P(v, body_no_indent)] for k, v in meta]
    mt = Table(data, colWidths=[38 * mm, 127 * mm])
    mt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), soft),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), .35, line),
        ('INNERGRID', (0, 0), (-1, -1), .18, line),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story += [mt, Spacer(1, 2.5 * mm)]

    for n, (heading, lines) in enumerate(sections, 1):
        governor.enter_section(heading)
        rendered_heading = governor.sanitize(heading)
        heading_text = _legal_chapter_heading(n, rendered_heading)
        story += [Spacer(1, 1 * mm), Paragraph(xml_escape(clean(heading_text)), chapter)]

        if heading in {'Case Readiness Review', 'Kesiapan Analisis'}:
            story += readiness_table(lines)
            governor.enter_section('')
            continue

        normalized_heading = str(rendered_heading or '').strip().upper()

        # Reference-style matrix projection: the benchmark document uses compact,
        # bordered tables for dense legal review data. These branches only change
        # presentation; source strings and reasoning state remain untouched.
        if normalized_heading == 'RINGKASAN ANALISIS HUKUM':
            before, rows, after = _summary_matrix_projection(lines)
            for text in before:
                if text:
                    story.append(P(text, body_no_indent, intercept=False))
            if rows:
                story.append(Paragraph('Matriks temuan utama', label_style))
                story.append(_styled_table(
                    rows,
                    [32, 34, 49, 50],
                    ['Aspek', 'Posisi/teks dokumen', 'Temuan', 'Rekomendasi'],
                ))
                story.append(Spacer(1, 1.5 * mm))
            lines = after

        elif normalized_heading == 'PEMETAAN BUKTI':
            before, rows, after, marker_seen = _evidence_table_projection(lines)
            for text in before:
                if text:
                    story.append(P(text, body_no_indent, intercept=False))
            if rows:
                story.append(_styled_table(
                    rows,
                    [38, 62, 30, 35],
                    ['Sumber/Bukti Potensial', 'Proposisi Faktual yang Perlu Diuji', 'Status Pembuktian', 'Uji Lanjut'],
                ))
                story.append(Spacer(1, 1.5 * mm))
            elif marker_seen:
                story.append(P('TABEL: [Sumber/Bukti Potensial] | [Proposisi Faktual yang Perlu Diuji] | [Status Pembuktian] | [Uji Lanjut]', small))
            lines = after

        elif normalized_heading == 'RENCANA TINDAKAN':
            rows, remainder = _action_plan_projection(lines)
            if rows:
                story.append(_styled_table(
                    rows,
                    [18, 28, 92, 27],
                    ['Langkah', 'Waktu/Prioritas', 'Tindakan dan Tujuan', 'Kondisi'],
                ))
                story.append(Spacer(1, 1.5 * mm))
            lines = remainder

        elif normalized_heading in {'KANDIDAT DASAR HUKUM YANG PERLU DIVERIFIKASI', 'DASAR HUKUM TERVERIFIKASI'}:
            rows, remainder = _candidate_law_projection(lines)
            if rows:
                story.append(_styled_table(
                    rows,
                    [38, 72, 55],
                    ['Ranah Hukum', 'Instrumen / Sumber', 'Status'],
                ))
                story.append(Spacer(1, 1.5 * mm))
            lines = remainder

        block = []
        for line0 in lines:
            intercepted = governor.intercept(line0)
            if intercepted is None:
                continue
            txt = clean(intercepted).strip()
            if not txt:
                continue
            if txt.endswith(':') and len(txt) < 80:
                block.append(Paragraph(xml_escape(txt[:-1]), label_style))
            elif txt.startswith('- '):
                block.append(Paragraph('&bull; ' + xml_escape(txt[2:]), body_no_indent))
            elif is_structured_line(txt):
                block.append(Paragraph(xml_escape(txt).replace('\n', '<br/>'), body_no_indent))
            else:
                block.append(Paragraph(xml_escape(txt).replace('\n', '<br/>'), body))

        if block:
            story.append(KeepTogether(block[:3]))
            story.extend(block[3:])
        governor.enter_section('')

    def footer(canvas, docobj):
        canvas.saveState()
        w, h = f4
        canvas.setFillColor(navy)
        canvas.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Times-Bold', 8)
        canvas.drawString(28 * mm, h - 7.6 * mm, 'LEXICORE')
        canvas.setFont('Times-Roman', 7)
        canvas.drawRightString(w - 22 * mm, h - 7.6 * mm, clean(profile["display_name"])[:70])
        canvas.setStrokeColor(line)
        canvas.line(28 * mm, 14 * mm, w - 22 * mm, 14 * mm)
        canvas.setFillColor(muted)
        canvas.setFont('Times-Roman', 7)
        canvas.drawString(28 * mm, 9 * mm, 'Kertas Kerja Rahasia | Menunggu Verifikasi Profesional')
        canvas.drawRightString(w - 22 * mm, 9 * mm, f'Halaman {docobj.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    bio.seek(0)
    return bio
