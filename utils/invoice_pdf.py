"""
Invoice PDF generation via reportlab.

Note: PDFs use the base Helvetica font, which does not include the ₹ glyph
(it's outside WinAnsiEncoding) — embedding a Unicode font isn't reliable
across every machine this app might run on, so PDFs use "Rs." instead of "₹".
The web UI still shows ₹ everywhere since browsers handle that fine.
"""
import io
from urllib.parse import quote
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                 Spacer, Image, HRFlowable)
from reportlab.lib.enums import TA_RIGHT, TA_LEFT

LAVENDER = colors.HexColor("#7C5CBF")
LAVENDER_SOFT = colors.HexColor("#F3EEFC")
INK = colors.HexColor("#241B33")
INK_SOFT = colors.HexColor("#5B4D77")


def generate_qr_png_bytes(invoice, upi_id=None, payee_name=None):
    """
    If the issuer has a UPI ID set, this produces a real `upi://pay` deep
    link — any UPI app (GPay, PhonePe, Paytm, etc.) recognizes this format
    and opens a pre-filled payment screen when scanned. Without a UPI ID,
    there's no real destination to pay to, so it falls back to a plain-text
    summary — most camera/QR apps will show that as text you can copy, not
    as a tappable action, since it isn't a recognized URI scheme.
    """
    if upi_id:
        amount = invoice.balance_due()
        note = f"Invoice {invoice.invoice_number}"
        qr_data = (
            f"upi://pay?pa={quote(upi_id)}&pn={quote(payee_name or 'Payment')}"
            f"&am={amount:.2f}&cu=INR&tn={quote(note)}"
        )
    else:
        qr_data = (f"Invoice {invoice.invoice_number}\n"
                    f"Amount Due: Rs. {invoice.balance_due():,.2f}\n"
                    f"Billed to: {invoice.client.name}")

    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#241B33", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _build_qr_image(invoice, upi_id=None, payee_name=None):
    return Image(generate_qr_png_bytes(invoice, upi_id, payee_name), width=26 * mm, height=26 * mm)


def generate_invoice_pdf(invoice, issuer_name, upi_id=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=22 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("InvoiceTitle", parent=styles["Title"], textColor=LAVENDER,
                                  fontSize=26, spaceAfter=0)
    value_style = ParagraphStyle("Value", parent=styles["Normal"], textColor=INK, fontSize=11, leading=15)
    right_value = ParagraphStyle("ValueRight", parent=value_style, alignment=TA_RIGHT)
    section_head = ParagraphStyle("SectionHead", parent=styles["Normal"], textColor=INK_SOFT,
                                   fontSize=9, spaceAfter=4)

    story = []

    # ---- Header: brand + invoice meta ----
    brand = Paragraph("<font color='#7C5CBF'><b>Duo Expense</b></font>", title_style)
    meta_lines = (
        f"Invoice #: <b>{invoice.invoice_number}</b><br/>"
        f"Issue Date: {invoice.issue_date.strftime('%b %d, %Y')}<br/>"
        f"Due Date: {invoice.due_date.strftime('%b %d, %Y') if invoice.due_date else '—'}<br/>"
        f"Status: <b>{invoice.status.upper()}</b>"
    )
    meta = Paragraph(meta_lines, right_value)
    header_table = Table([[brand, meta]], colWidths=[90 * mm, 80 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=LAVENDER, thickness=1.2))
    story.append(Spacer(1, 16))

    # ---- Billed by / Billed to ----
    billed_by = Paragraph(
        f"<font color='#5B4D77' size=9>BILLED BY</font><br/><b>{issuer_name}</b><br/>via Duo Expense",
        value_style
    )
    billed_to = Paragraph(
        f"<font color='#5B4D77' size=9>BILLED TO</font><br/><b>{invoice.client.name}</b><br/>"
        f"{invoice.client.phone or ''}<br/>{invoice.client.email or ''}",
        value_style
    )
    parties_table = Table([[billed_by, billed_to]], colWidths=[85 * mm, 85 * mm])
    parties_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(parties_table)
    story.append(Spacer(1, 22))

    # ---- Line items ----
    rows = [["Description", "Qty", "Unit Price", "Amount"]]
    for item in invoice.items:
        rows.append([
            Paragraph(item.description, value_style),
            str(item.quantity),
            f"Rs. {item.unit_price:,.2f}",
            f"Rs. {item.line_total:,.2f}",
        ])
    items_table = Table(rows, colWidths=[85 * mm, 20 * mm, 32 * mm, 33 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LAVENDER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LAVENDER_SOFT]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#E4D4FF")),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # ---- Totals ----
    totals_rows = [["Subtotal", f"Rs. {invoice.subtotal:,.2f}"]]
    if invoice.discount_percent:
        totals_rows.append([f"Discount ({invoice.discount_percent:.1f}%)", f"- Rs. {invoice.discount_amount:,.2f}"])
    if invoice.gst_percent:
        totals_rows.append([f"GST ({invoice.gst_percent:.1f}%)", f"+ Rs. {invoice.gst_amount:,.2f}"])
    totals_rows.append(["Total", f"Rs. {invoice.total_amount:,.2f}"])
    totals_rows.append(["Amount Paid", f"Rs. {invoice.amount_paid:,.2f}"])
    totals_rows.append(["Balance Due", f"Rs. {invoice.balance_due():,.2f}"])

    totals_table = Table(totals_rows, colWidths=[45 * mm, 40 * mm])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), LAVENDER),
        ("LINEABOVE", (0, -1), (-1, -1), 1, LAVENDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    qr_img = _build_qr_image(invoice, upi_id=upi_id, payee_name=issuer_name)
    qr_caption_text = "Scan to pay via UPI" if upi_id else "Scan for invoice &amp; amount summary"
    qr_caption = Paragraph(f"<font size=7 color='#5B4D77'>{qr_caption_text}</font>", value_style)
    qr_block = Table([[qr_img], [qr_caption]])
    qr_block.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))

    bottom_table = Table([[qr_block, totals_table]], colWidths=[80 * mm, 90 * mm])
    bottom_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(bottom_table)

    if invoice.notes:
        story.append(Spacer(1, 18))
        story.append(Paragraph("NOTES", section_head))
        story.append(Paragraph(invoice.notes, value_style))

    story.append(Spacer(1, 26))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E4D4FF"), thickness=0.8))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<font size=8 color='#5B4D77'>Generated with Duo Expense — thank you for your business.</font>",
        value_style
    ))

    doc.build(story)
    buf.seek(0)
    return buf
