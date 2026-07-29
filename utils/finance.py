"""Automatic interest calculator for loans/EMIs — standard reducing-balance amortization."""
from dateutil.relativedelta import relativedelta


def calculate_emi(principal, annual_rate, tenure_months):
    """Standard EMI formula: E = P * r * (1+r)^n / ((1+r)^n - 1), r = monthly rate."""
    if tenure_months <= 0:
        return 0.0
    if not annual_rate:
        return round(principal / tenure_months, 2)

    r = (annual_rate / 12) / 100
    factor = (1 + r) ** tenure_months
    emi = principal * r * factor / (factor - 1)
    return round(emi, 2)


def build_amortization_schedule(principal, annual_rate, tenure_months, start_date, emi=None):
    """
    Returns a list of dicts, one per installment:
    {installment_no, due_date, amount, principal_component, interest_component}
    Uses reducing-balance interest so the last installment absorbs any rounding drift.
    """
    if emi is None:
        emi = calculate_emi(principal, annual_rate, tenure_months)

    r = (annual_rate / 12) / 100 if annual_rate else 0
    remaining = principal
    schedule = []

    for i in range(1, tenure_months + 1):
        interest_component = round(remaining * r, 2) if r else 0.0
        principal_component = round(emi - interest_component, 2)

        # Final installment: absorb rounding so principal fully reconciles to zero
        if i == tenure_months:
            principal_component = round(remaining, 2)
            this_emi = round(principal_component + interest_component, 2)
        else:
            this_emi = emi

        remaining = round(remaining - principal_component, 2)
        due_date = start_date + relativedelta(months=i)

        schedule.append({
            "installment_no": i,
            "due_date": due_date,
            "amount": this_emi,
            "principal_component": principal_component,
            "interest_component": interest_component,
        })

    return schedule
