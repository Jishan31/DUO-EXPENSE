"""
Full expense & income report for a given period — the comprehensive document
a user hands to an auditor for a filing project, as opposed to the live,
period-scoped table view the auditor also gets automatic read access to.
Covers every expense and income record, grouped by category, with totals.
"""
import io
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, PageBreak

from models import Expense, Income

LAVENDER = colors.HexColor("#7C5CBF")
LAVENDER_SOFT = colors.HexColor("#F3EEFC")
INK = colors.HexColor("#241B33")
INK_SOFT = colors.HexColor("#5B4D77")
SUCCESS = colors.HexColor("#2FB77E")


def compute_expense_report(user, start_date, end_date):
    expenses = (Expense.query.filter(Expense.user_id == user.id, Expense.date >= start_date,
                                      Expense.date <= end_date).order_by(Expense.date).all())
    incomes = (Income.query.filter(Income.user_id == user.id, Income.date >= start_date,
                                    Income.date <= end_date).order_by(Income.date).all())

    by_category = defaultdict(lambda: {"total": 0.0, "count": 0})
    for e in expenses:
        name = e.category.name if e.category else "Uncategorized"
        by_category[name]["total"] += e.amount
        by_category[name]["count"] += 1
    category_breakdown = sorted(by_category.items(), key=lambda x: x[1]["total"], reverse=True)

    total_expense = round(sum(e.amount for e in expenses), 2)
    total_income = round(sum(i.amount for i in incomes), 2)

    return {
        "expenses": expenses, "incomes": incomes, "category_breakdown": category_breakdown,
        "total_expense": total_expense, "total_income": total_income,
        "net": round(total_income - total_expense, 2),
    }


def generate_expense_report_pdf(user, start_date, end_date, report):
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
    story.append(Paragraph("Expense &amp; Income Report", h1))
    story.append(Paragraph(business, meta))
    story.append(Paragraph(f"Period: {start_date.strftime('%d %b %Y')} \u2013 {end_date.strftime('%d %b %Y')}", meta))
    story.append(HRFlowable(width="100%", thickness=1, color=LAVENDER_SOFT, spaceBefore=8, spaceAfter=4))

    story.append(Paragraph("Summary", section))
    rows = [
        ["", "Amount (Rs.)"],
        ["Total Income", f"{report['total_income']:,.2f}"],
        ["Total Expenses", f"{report['total_expense']:,.2f}"],
        ["Net" if report["net"] >= 0 else "Net (Deficit)", f"{abs(report['net']):,.2f}"],
    ]
    t = Table(rows, colWidths=[110 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LAVENDER), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, LAVENDER), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LAVENDER_SOFT]),
    ]))
    story.append(t)

    story.append(Paragraph("Expenses by Category", section))
    if report["category_breakdown"]:
        cat_rows = [["Category", "Count", "Total"]]
        for name, d in report["category_breakdown"]:
            cat_rows.append([name, str(d["count"]), f"{d['total']:,.2f}"])
        ct = Table(cat_rows, colWidths=[90 * mm, 30 * mm, 40 * mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LAVENDER_SOFT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LAVENDER_SOFT),
        ]))
        story.append(ct)
    else:
        story.append(Paragraph("No expenses in this period.", small))

    story.append(Paragraph(f"All Expenses ({len(report['expenses'])})", section))
    if report["expenses"]:
        exp_rows = [["Date", "Name", "Category", "Merchant", "Payment", "Amount"]]
        for e in report["expenses"]:
            exp_rows.append([
                e.date.strftime("%d %b %Y"), e.name[:26], (e.category.name if e.category else "\u2014")[:16],
                (e.merchant or "\u2014")[:16], e.payment_mode, f"{e.amount:,.2f}",
            ])
        et = Table(exp_rows, colWidths=[20 * mm, 38 * mm, 26 * mm, 30 * mm, 22 * mm, 24 * mm], repeatRows=1)
        et.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LAVENDER_SOFT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.8), ("ALIGN", (5, 0), (5, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LAVENDER_SOFT),
        ]))
        story.append(et)
    else:
        story.append(Paragraph("No expenses in this period.", small))

    story.append(PageBreak())
    story.append(Paragraph(f"All Income ({len(report['incomes'])})", section))
    if report["incomes"]:
        inc_rows = [["Date", "Source", "Name", "Amount"]]
        for i in report["incomes"]:
            inc_rows.append([i.date.strftime("%d %b %Y"), i.source, i.name[:30], f"{i.amount:,.2f}"])
        it = Table(inc_rows, colWidths=[25 * mm, 35 * mm, 60 * mm, 30 * mm])
        it.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LAVENDER_SOFT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LAVENDER_SOFT),
        ]))
        story.append(it)
    else:
        story.append(Paragraph("No income in this period.", small))

    story.append(Paragraph(
        "This report is generated from data recorded in Duo Expense by the account holder. It has not been "
        "independently verified and should be reviewed against source documents (receipts, bank statements) "
        "before being used for tax filing.", disclaimer,
    ))

    doc.build(story)
    buf.seek(0)
    return buf
