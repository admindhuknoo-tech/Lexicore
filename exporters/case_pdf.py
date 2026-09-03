"""Professional PDF renderer for Case Analysis."""
from io import BytesIO
from .common import _case_export_sections

def export_case_pdf(x):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
        from xml.sax.saxutils import escape as xml_escape
    except ImportError as exc:
        raise RuntimeError('Export PDF membutuhkan reportlab. Jalankan: py -m pip install reportlab') from exc
    meta,sections=_case_export_sections(x); bio=BytesIO()
    navy=colors.HexColor('#10263D'); gold=colors.HexColor('#D8B65C'); ink=colors.HexColor('#1F2937'); muted=colors.HexColor('#66717F'); line=colors.HexColor('#D8DEE6'); soft=colors.HexColor('#F4F7FA'); green=colors.HexColor('#157452')
    doc=SimpleDocTemplate(bio,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=22*mm,bottomMargin=18*mm,title='LexiCore Case Analysis',author="ELF - Erfan's Law Firm")
    ss=getSampleStyleSheet()
    title=ParagraphStyle('LC_Title',parent=ss['Title'],fontName='Helvetica-Bold',fontSize=17,leading=20,alignment=TA_CENTER,textColor=navy,spaceAfter=3)
    subtitle=ParagraphStyle('LC_Sub',parent=ss['Normal'],fontName='Helvetica',fontSize=8.4,leading=11,alignment=TA_CENTER,textColor=muted,spaceAfter=8)
    h1=ParagraphStyle('LC_H1',parent=ss['Heading1'],fontName='Helvetica-Bold',fontSize=10.6,leading=13,textColor=navy,spaceBefore=9,spaceAfter=4)
    body=ParagraphStyle('LC_Body',parent=ss['BodyText'],fontName='Helvetica',fontSize=8.7,leading=12,textColor=ink,spaceAfter=3)
    small=ParagraphStyle('LC_Small',parent=body,fontSize=7.6,leading=10,textColor=muted)
    def clean(v):
        t=str(v).replace('\u2018',"'").replace('\u2019',"'").replace('\u201c','"').replace('\u201d','"').replace('\u2013','-').replace('\u2014','-').replace('\u2022','-')
        return t.encode('latin-1','replace').decode('latin-1')
    def P(text,style=body,bold=False):
        t=xml_escape(clean(text)).replace('\n','<br/>')
        return Paragraph(('<b>'+t+'</b>') if bold else t,style)
    def readiness_table(lines):
        vals={}; disclaimer=''
        for line0 in lines:
            z=str(line0)
            if ':' in z and '%' in z:
                k,v=z.split(':',1); vals[k.strip()]=v.strip()
            elif z: disclaimer=z
        cells=[]
        for key,label in [('Overall readiness','OVERALL'),('Evidence Map','EVIDENCE'),('Analisis Hukum','LEGAL'),('Action Plan','ACTION')]:
            pct=vals.get(key,'0%'); cells.append(Paragraph(f'<font size="13"><b>{xml_escape(clean(pct))}</b></font><br/><font size="7">{xml_escape(clean(label))}</font>', body))
        t=Table([cells],colWidths=[44.25*mm]*4)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),colors.HexColor('#EAF6F0')),('BACKGROUND',(1,0),(-1,0),soft),('TEXTCOLOR',(0,0),(0,0),green),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BOX',(0,0),(-1,-1),.4,line),('INNERGRID',(0,0),(-1,-1),.25,line),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        return [t,Spacer(1,2*mm),P(disclaimer,small)] if disclaimer else [t]
    story=[]
    # Brand masthead as native PDF vectors/text, not an image.
    brand_left=[Paragraph('<b>LC</b>',ParagraphStyle('brand',parent=body,alignment=TA_CENTER,textColor=navy,fontSize=14,leading=15)),Paragraph('ELF',ParagraphStyle('brandSmall',parent=body,alignment=TA_CENTER,textColor=navy,fontSize=6.5,leading=7))]
    brand_right=[Paragraph('<b>LexiCore</b>',ParagraphStyle('brandTitle',parent=body,textColor=colors.white,fontSize=18,leading=20,spaceAfter=1)),Paragraph("Evidence-to-Action Case Analysis | Initiated by ELF - Erfan's Law Firm",ParagraphStyle('brand2',parent=body,textColor=colors.HexColor('#E5EAF0'),fontSize=7.8,leading=9))]
    brand=Table([[brand_left,brand_right]],colWidths=[20*mm,157*mm])
    brand.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),gold),('BACKGROUND',(1,0),(1,0),navy),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story += [brand,Spacer(1,5*mm),Paragraph(xml_escape(clean(x.get('title') or 'Case Analysis')),title),Paragraph('WORKING PAPER | PROFESSIONAL VERIFICATION: PENDING',subtitle)]
    data=[[P(k,small,bold=True),P(v,body)] for k,v in meta]
    mt=Table(data,colWidths=[43*mm,134*mm])
    mt.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),soft),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.35,line),('INNERGRID',(0,0),(-1,-1),.18,line),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story += [mt,Spacer(1,3*mm)]
    for n,(heading,lines) in enumerate(sections,1):
        heading_row=Table([[P(f'{n:02d}',ParagraphStyle('num',parent=body,fontName='Helvetica-Bold',fontSize=8,textColor=navy,alignment=TA_CENTER)),P(heading.upper(),h1)]],colWidths=[11*mm,166*mm])
        heading_row.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),gold),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(1,0),(1,0),1,gold),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        story += [Spacer(1,2*mm),heading_row,Spacer(1,2*mm)]
        if heading=='Case Readiness Review':
            story += readiness_table(lines); continue
        block=[]
        for line0 in lines:
            txt=clean(line0).strip()
            if not txt: continue
            if txt.endswith(':') and len(txt)<80:
                block.append(P(txt[:-1],body,bold=True))
            elif txt.startswith('- '):
                block.append(Paragraph('&bull; '+xml_escape(txt[2:]),body))
            else:
                block.append(P(txt,body))
        # Bug fix (v1.3.3.14): the previous one-liner kept block[:3] together only
        # when a section had 3 lines or fewer; for any longer section (the common
        # case — Ringkasan, Evidence Map, Analisis Hukum, Action Plan, etc. routinely
        # exceed 3 lines) it appended only block[0] and then block[3:], silently
        # dropping block[1] and block[2] from the exported PDF. On a legal working
        # paper that means real evidence/analysis lines vanish without any error.
        # Fix: always keep the first up-to-3 lines together (avoids an orphaned
        # heading at a page break) and always append every remaining line.
        if block:
            story.append(KeepTogether(block[:3]))
            story.extend(block[3:])
    def footer(canvas,docobj):
        canvas.saveState(); w,h=A4
        canvas.setFillColor(navy); canvas.rect(0,h-12*mm,w,12*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold',8); canvas.drawString(16*mm,h-7.6*mm,'LEXICORE')
        canvas.setFont('Helvetica',7); canvas.drawRightString(194*mm,h-7.6*mm,"ELF - Erfan's Law Firm")
        canvas.setStrokeColor(line); canvas.line(16*mm,12*mm,194*mm,12*mm)
        canvas.setFillColor(muted); canvas.setFont('Helvetica',6.8)
        canvas.drawString(16*mm,8*mm,'Confidential Working Paper | Professional Verification: PENDING')
        canvas.drawRightString(194*mm,8*mm,f'Page {docobj.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=footer,onLaterPages=footer); bio.seek(0); return bio


