"""Professional DOCX renderer for Case Analysis."""
from io import BytesIO
import re
from docx import Document
from .common import _case_export_sections, _export_scalar

def _docx_set_cell_shading(cell, fill):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr=cell._tc.get_or_add_tcPr(); shd=tcPr.find(qn('w:shd'))
    if shd is None:
        shd=OxmlElement('w:shd'); tcPr.append(shd)
    shd.set(qn('w:fill'), fill)


def _docx_set_cell_margins(cell, top=90, start=100, bottom=90, end=100):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tc=cell._tc; tcPr=tc.get_or_add_tcPr(); tcMar=tcPr.first_child_found_in('w:tcMar')
    if tcMar is None:
        tcMar=OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for m,v in [('top',top),('start',start),('bottom',bottom),('end',end)]:
        node=tcMar.find(qn('w:'+m))
        if node is None:
            node=OxmlElement('w:'+m); tcMar.append(node)
        node.set(qn('w:w'), str(v)); node.set(qn('w:type'),'dxa')


def _docx_add_section_title(doc, number, heading):
    from docx.shared import Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(12); p.paragraph_format.space_after=Pt(5)
    r=p.add_run(f'{number:02d}  {heading.upper()}'); r.bold=True; r.font.name='Aptos Display'; r.font.size=Pt(12); r.font.color.rgb=RGBColor(18,39,63)
    pPr=p._p.get_or_add_pPr(); pbdr=OxmlElement('w:pBdr'); bottom=OxmlElement('w:bottom')
    bottom.set(qn('w:val'),'single'); bottom.set(qn('w:sz'),'8'); bottom.set(qn('w:space'),'4'); bottom.set(qn('w:color'),'D6B253'); pbdr.append(bottom); pPr.append(pbdr)
    return p


def export_case_docx(x):
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    meta,sections=_case_export_sections(x)
    doc=Document(); sec=doc.sections[0]
    sec.top_margin=Inches(.62); sec.bottom_margin=Inches(.62); sec.left_margin=Inches(.68); sec.right_margin=Inches(.68)
    styles=doc.styles
    styles['Normal'].font.name='Aptos'; styles['Normal'].font.size=Pt(10); styles['Normal'].font.color.rgb=RGBColor(31,41,55)
    styles['Normal'].paragraph_format.space_after=Pt(4); styles['Normal'].paragraph_format.line_spacing=1.08

    # Professional brand masthead.
    mast=doc.add_table(rows=1,cols=2); mast.alignment=WD_TABLE_ALIGNMENT.CENTER; mast.autofit=False
    mast.columns[0].width=Inches(.75); mast.columns[1].width=Inches(5.95)
    left,right=mast.rows[0].cells; left.width=Inches(.75); right.width=Inches(5.95)
    _docx_set_cell_shading(left,'D8B65C'); _docx_set_cell_shading(right,'10263D')
    for c in (left,right): c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER; _docx_set_cell_margins(c,120,150,120,150)
    lp=left.paragraphs[0]; lp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    lr=lp.add_run('LC\nELF'); lr.bold=True; lr.font.name='Georgia'; lr.font.size=Pt(13); lr.font.color.rgb=RGBColor(16,38,61)
    rp=right.paragraphs[0]; rp.paragraph_format.space_after=Pt(0)
    rr=rp.add_run('LexiCore'); rr.bold=True; rr.font.name='Georgia'; rr.font.size=Pt(20); rr.font.color.rgb=RGBColor(255,255,255)
    rp.add_run("\nEvidence-to-Action Case Analysis | Initiated by ELF - Erfan's Law Firm").font.color.rgb=RGBColor(223,229,235)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)

    t=doc.add_paragraph(); t.alignment=WD_ALIGN_PARAGRAPH.CENTER; t.paragraph_format.space_after=Pt(2)
    tr=t.add_run(_export_scalar(x.get('title') or 'Case Analysis')); tr.bold=True; tr.font.name='Georgia'; tr.font.size=Pt(17); tr.font.color.rgb=RGBColor(18,39,63)
    s=doc.add_paragraph(); s.alignment=WD_ALIGN_PARAGRAPH.CENTER; s.paragraph_format.space_after=Pt(9)
    sr=s.add_run('WORKING PAPER - PROFESSIONAL VERIFICATION: PENDING'); sr.bold=True; sr.font.size=Pt(8.5); sr.font.color.rgb=RGBColor(151,112,24)

    # Compact metadata table, no heavy grid.
    mt=doc.add_table(rows=0,cols=2); mt.alignment=WD_TABLE_ALIGNMENT.CENTER; mt.autofit=False
    mt.columns[0].width=Inches(1.6); mt.columns[1].width=Inches(5.15)
    for i,(k,v) in enumerate(meta):
        cells=mt.add_row().cells; cells[0].width=Inches(1.6); cells[1].width=Inches(5.15)
        _docx_set_cell_shading(cells[0],'EEF2F6'); _docx_set_cell_shading(cells[1],'FFFFFF')
        for c in cells: _docx_set_cell_margins(c,70,110,70,110)
        p0=cells[0].paragraphs[0]; p0.paragraph_format.space_after=Pt(0); r0=p0.add_run(str(k)); r0.bold=True; r0.font.size=Pt(8.5); r0.font.color.rgb=RGBColor(73,89,105)
        p1=cells[1].paragraphs[0]; p1.paragraph_format.space_after=Pt(0); r1=p1.add_run(_export_scalar(v)); r1.font.size=Pt(9)

    for n,(heading,lines) in enumerate(sections,1):
        _docx_add_section_title(doc,n,heading)
        if heading=='Case Readiness Review':
            vals={}
            disclaimer=None
            for line in lines:
                text=str(line)
                if ':' in text and '%' in text:
                    k,v=text.split(':',1); vals[k.strip()]=v.strip()
                elif text: disclaimer=text
            rt=doc.add_table(rows=1,cols=4); rt.alignment=WD_TABLE_ALIGNMENT.CENTER; rt.autofit=True
            mapping=[('Overall readiness','Overall'),('Evidence Map','Evidence'),('Analisis Hukum','Legal'),('Action Plan','Action')]
            for idx,(key,label) in enumerate(mapping):
                c=rt.rows[0].cells[idx]; _docx_set_cell_shading(c,'F7F9FB' if idx else 'EAF6F0'); _docx_set_cell_margins(c,110,90,110,90)
                p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(1)
                r=p.add_run(vals.get(key,'0%')); r.bold=True; r.font.size=Pt(14); r.font.color.rgb=RGBColor(21,116,82) if idx==0 else RGBColor(18,39,63)
                q=c.add_paragraph(); q.alignment=WD_ALIGN_PARAGRAPH.CENTER; q.paragraph_format.space_after=Pt(0); qr=q.add_run(label); qr.font.size=Pt(7.5); qr.font.color.rgb=RGBColor(91,100,113)
            if disclaimer:
                dp=doc.add_paragraph(); dp.paragraph_format.space_before=Pt(3); dr=dp.add_run(disclaimer); dr.italic=True; dr.font.size=Pt(8); dr.font.color.rgb=RGBColor(100,108,118)
            continue
        # Render content with hierarchy instead of raw paragraph dump.
        for line in lines:
            text=str(line).strip()
            if not text: continue
            if text.endswith(':') and len(text)<80:
                p=doc.add_paragraph(); p.paragraph_format.space_before=Pt(4); p.paragraph_format.space_after=Pt(2)
                r=p.add_run(text[:-1]); r.bold=True; r.font.size=Pt(9.5); r.font.color.rgb=RGBColor(43,58,73)
            elif text.startswith('- '):
                p=doc.add_paragraph(style='List Bullet'); p.paragraph_format.left_indent=Inches(.16); p.paragraph_format.space_after=Pt(2); p.add_run(text[2:])
            elif re.match(r'^\[(P\d|SOURCE|ADMISSION|DENIAL|ALLEGATION)', text, re.I):
                p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(.12); p.paragraph_format.space_after=Pt(3)
                r=p.add_run(text); r.font.size=Pt(9.3)
            else:
                p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(3); p.add_run(text)

    # Footer/header with restrained legal-report identity and page field.
    hp=sec.header.paragraphs[0]; hp.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    hr=hp.add_run("LEXICORE | ELF - ERFAN'S LAW FIRM"); hr.bold=True; hr.font.size=Pt(7.5); hr.font.color.rgb=RGBColor(93,105,118)
    fp=sec.footer.paragraphs[0]; fp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    fr=fp.add_run('Confidential Working Paper | Professional Verification: PENDING | Page '); fr.font.size=Pt(7.5); fr.font.color.rgb=RGBColor(93,105,118)
    fld=OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); fp._p.append(fld)
    doc.core_properties.title='LexiCore Case Analysis - '+str(x.get('title') or 'Case Analysis')
    doc.core_properties.author="ELF - Erfan's Law Firm"
    doc.core_properties.subject='Evidence-to-Action Legal Working Paper'
    bio=BytesIO(); doc.save(bio); bio.seek(0); return bio


