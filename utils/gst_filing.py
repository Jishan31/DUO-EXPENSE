"""
GST filing summary — pulls together output GST (collected on sales, from
Invoice records) and input GST (paid on purchases, from Expense records)
for a chosen period, computes net payable/refundable, and can render the
whole thing as a reference PDF.

This produces a summary an accountant or the business owner can use as a
starting point for actual GST return filing (GSTR-1/GSTR-3B) — it is NOT
an official government form and doesn't submit anything anywhere.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER

from models import Invoice, Expense

LAVENDER = colors.HexColor("#7C5CBF")
LAVENDER_SOFT = colors.HexColor("#F3EEFC")
INK = colors.HexColor("#241B33")
INK_SOFT = colors.HexColor("#5B4D77")


def compute_gst_summary(user, start_date, end_date):
    invoices = (Invoice.query.filter(
        Invoice.user_id == user.id, Invoice.issue_date >= start_date,
        Invoice.issue_date <= end_date, Invoice.status != "draft",
        Invoice.status != "cancelled", Invoice.gst_amount > 0,
    ).order_by(Invoice.issue_date).all())

    expenses = (Expense.query.filter(
        Expense.user_id == user.id, Expense.date >= start_date,
        Expense.date <= end_date, Expense.gst_amount > 0,
    ).order_by(Expense.date).all())

    output_gst = round(sum(i.gst_amount for i in invoices), 2)
    input_gst = round(sum(e.gst_amount for e in expenses), 2)
    taxable_sales = round(sum(i.subtotal - i.discount_amount for i in invoices), 2)
    taxable_purchases = round(sum(e.amount - e.gst_amount for e in expenses), 2)

    return {
        "invoices": invoices, "expenses": expenses,
        "output_gst": output_gst, "input_gst": input_gst,
        "net_payable": round(output_gst - input_gst, 2),
        "taxable_sales": taxable_sales, "taxable_purchases": taxable_purchases,
    }


def generate_gst_pdf(user, start_date, end_date, summary):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm,
                             leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=LAVENDER, fontSize=20, spaceAfter=2)
    meta = ParagraphStyle("meta", parent=styles["Normal"], textColor=INK_SOFT, fontSize=10)
    section = ParagraphStyle("section", parent=styles["Heading2"], textColor=INK, fontSize=13, spaceBefore=14, spaceAfter=6)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, textColor=INK_SOFT)
    disclaimer = ParagraphStyle("disclaimer", parent=styles["Normal"], fontSize=8.5, textColor=INK_SOFT, spaceBefore=14)

    story = []
    business = user.business_name or user.username
    story.append(Paragraph("GST Filing Summary", h1))
    story.append(Paragraph(f"{business}" + (f" &nbsp;\u00b7&nbsp; GSTIN: {user.business_gstin}" if user.business_gstin else ""), meta))
    story.append(Paragraph(f"Period: {start_date.strftime('%d %b %Y')} \u2013 {end_date.strftime('%d %b %Y')}", meta))
    story.append(HRFlowable(width="100%", thickness=1, color=LAVENDER_SOFT, spaceBefore=8, spaceAfter=4))

    story.append(Paragraph("Summary", section))
    rows = [
        ["", "Amount (Rs.)"],
        ["Taxable sales (outward supplies)", f"{summary['taxable_sales']:,.2f}"],
        ["Output GST collected", f"{summary['output_gst']:,.2f}"],
        ["Taxable purchases (inward supplies)", f"{summary['taxable_purchases']:,.2f}"],
        ["Input GST paid", f"{summary['input_gst']:,.2f}"],
        ["Net GST Payable" if summary["net_payable"] >= 0 else "Net GST Refundable / Carried Forward",
         f"{abs(summary['net_payable']):,.2f}"],
    ]
    t = Table(rows, colWidths=[110 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LAVENDER),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, LAVENDER),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LAVENDER_SOFT]),
    ]))
    story.append(t)

    story.append(Paragraph(f"Output GST \u2014 Sales ({len(summary['invoices'])} invoice(s))", section))
    if summary["invoices"]:
        inv_rows = [["Date", "Invoice #", "Taxable Value", "GST", "Total"]]
        for i in summary["invoices"]:
            inv_rows.append([
                i.issue_date.strftime("%d %b %Y"), i.invoice_number,
                f"{i.subtotal - i.discount_amount:,.2f}", f"{i.gst_amount:,.2f}", f"{i.total_amount:,.2f}",
            ])
        it = Table(inv_rows, colWidths=[25 * mm, 35 * mm, 35 * mm, 30 * mm, 35 * mm])
        it.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LAVENDER_SOFT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LAVENDER_SOFT),
        ]))
        story.append(it)
    else:
        story.append(Paragraph("No GST-bearing invoices in this period.", small))

    story.append(Paragraph(f"Input GST \u2014 Purchases ({len(summary['expenses'])} expense(s))", section))
    if summary["expenses"]:
        exp_rows = [["Date", "Expense", "Merchant", "Taxable Value", "GST"]]
        for e in summary["expenses"]:
            exp_rows.append([
                e.date.strftime("%d %b %Y"), e.name[:28], (e.merchant or "\u2014")[:20],
                f"{e.amount - e.gst_amount:,.2f}", f"{e.gst_amount:,.2f}",
            ])
        et = Table(exp_rows, colWidths=[22 * mm, 45 * mm, 33 * mm, 30 * mm, 30 * mm])
        et.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LAVENDER_SOFT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LAVENDER_SOFT),
        ]))
        story.append(et)
    else:
        story.append(Paragraph("No GST-bearing expenses in this period.", small))

    story.append(Paragraph(
        "This is a reference summary generated from data recorded in Duo Expense, not an official "
        "government filing form. Verify all figures \u2014 especially GST rate splits (CGST/SGST/IGST) and "
        "any reverse-charge or exempt items \u2014 before filing GSTR-1/GSTR-3B, ideally with a tax professional.",
        disclaimer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf
