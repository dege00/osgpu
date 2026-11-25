from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _miniatura(caminho, lado=520):
    with PILImage.open(caminho) as img:
        img = img.convert("RGB")
        img.thumbnail((lado, lado), PILImage.LANCZOS)
        buf = BytesIO()
        img.save(buf, "JPEG", quality=80, optimize=True)
        buf.seek(0)
        return buf


def _fotos_entrada_pdf(os_, st):
    celulas = []
    for foto in os_.fotos.filter(tipo="entrada").order_by("criado_em"):
        try:
            buf = _miniatura(foto.imagem.path)
        except (ValueError, OSError):
            continue
        partes = [Image(buf, width=38 * mm, height=38 * mm, kind="proportional")]
        if foto.legenda:
            partes += [Spacer(1, 1 * mm), Paragraph(escape(foto.legenda), st["Normal"])]
        celulas.append(partes)
    if not celulas:
        return []
    linhas = []
    for i in range(0, len(celulas), 4):
        linha = celulas[i:i + 4]
        linhas.append(linha + [""] * (4 - len(linha)))
    tabela = Table(linhas, colWidths=[43 * mm] * 4)
    tabela.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 1 * mm),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 1 * mm),
                                ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm)]))
    return [Spacer(1, 4 * mm), Paragraph("<b>Estado do aparelho na entrada</b>", st["Heading3"]),
            Spacer(1, 2 * mm), tabela]


def _checklist_pdf(os_, st):
    els = []
    itens = getattr(os_, "checklist_itens", None) or []
    if isinstance(itens, list):
        linhas = [
            f"{escape(str(item.get('nome', '')))}: {'Sim' if item.get('resposta') == 'sim' else 'Não'}"
            for item in itens if isinstance(item, dict)
        ]
        if linhas:
            els += [Spacer(1, 4 * mm), Paragraph("<b>Checklist de entrada:</b><br/>" + "<br/>".join(linhas), st["Normal"])]
    observacao = getattr(os_, "observacao_entrada", "") or ""
    if observacao:
        texto = escape(observacao).replace("\r\n", "\n").replace("\n", "<br/>")
        els += [Spacer(1, 2 * mm), Paragraph(f"<b>Observações:</b><br/>{texto}", st["Normal"])]
    if os_.checklist:
        texto = escape(os_.checklist).replace("\r\n", "\n").replace("\n", "<br/>")
        els += [Spacer(1, 4 * mm), Paragraph(f"<b>Checklist de entrada:</b><br/>{texto}", st["Normal"])]
    return els


def gerar_pdf_os(os_):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    st = getSampleStyleSheet()
    loja = os_.loja
    els = []
    if loja.logo and loja.logo.name:
        try:
            els.append(Image(loja.logo.path, width=30 * mm, height=18 * mm, kind="proportional"))
        except (ValueError, OSError):
            pass
    els += [Paragraph(f"<b>{escape(loja.nome)}</b>", st["Title"]),
           Paragraph(escape(" • ".join(x for x in [loja.documento, loja.telefone, loja.endereco] if x)), st["Normal"]),
           Spacer(1, 6 * mm)]
    titulo = "ORÇAMENTO" if os_.status == "orcamento" else "ORDEM DE SERVIÇO"
    els.append(Paragraph(f"<b>{titulo} Nº {os_.numero}</b> — {timezone.localtime(os_.criado_em):%d/%m/%Y %H:%M}", st["Heading2"]))
    aparelho = escape(" ".join(x for x in [os_.tipo_aparelho, os_.marca, os_.modelo] if x))
    dados = [["Cliente", escape(os_.cliente.nome), "Telefone", escape(os_.cliente.telefone)],
             ["Aparelho", aparelho, "Situação", os_.get_status_display()],
             ["Defeito", Paragraph(escape(os_.defeito), st["Normal"]), "Nº de série", escape(os_.numero_serie or "—")]]
    if os_.imei:
        dados.append(["IMEI", escape(os_.imei), "", ""])
    t = Table(dados, colWidths=[22 * mm, 66 * mm, 24 * mm, 58 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke), ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    els += [t, Spacer(1, 5 * mm)]
    rows = [["Descrição", "Qtd", "Unit.", "Subtotal"]]
    for i in os_.itens.all():
        rows.append([escape(i.descricao), i.quantidade, brl(i.valor_unitario), brl(i.subtotal)])
    if os_.desconto:
        rows.append(["Desconto", "", "", "- " + brl(os_.desconto)])
    rows.append(["TOTAL", "", "", brl(os_.total)])
    t2 = Table(rows, colWidths=[100 * mm, 15 * mm, 30 * mm, 30 * mm])
    t2.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    els.append(t2)
    els += _checklist_pdf(os_, st)
    els += _fotos_entrada_pdf(os_, st)
    els += [Spacer(1, 4 * mm), Paragraph(f"<b>Garantia:</b> {os_.garantia_dias} dias. {escape(loja.termo_garantia)}", st["Normal"])]
    if os_.assinatura:
        els += [Spacer(1, 6 * mm), Paragraph("Assinatura do cliente:", st["Normal"]),
                Image(os_.assinatura.path, width=60 * mm, height=22 * mm, kind="proportional")]
    doc.build(els)
    return buf.getvalue()
