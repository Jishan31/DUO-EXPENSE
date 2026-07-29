function calcEmi(principal, annualRate, months) {
  if (!months || months <= 0) return 0;
  if (!annualRate) return principal / months;
  const r = (annualRate / 12) / 100;
  const factor = Math.pow(1 + r, months);
  return (principal * r * factor) / (factor - 1);
}

function currency(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function updateEmiPreview() {
  const principal = parseFloat(document.getElementById("principal_amount").value) || 0;
  const rate = parseFloat(document.getElementById("interest_rate").value) || 0;
  const months = parseInt(document.getElementById("tenure_months").value) || 0;
  const startVal = document.getElementById("start_date").value;

  const emi = calcEmi(principal, rate, months);
  const totalPayment = emi * months;
  const totalInterest = Math.max(totalPayment - principal, 0);

  document.getElementById("emi-preview-value").textContent = Math.round(emi).toLocaleString("en-IN");
  document.getElementById("emi-total-interest").textContent = currency(totalInterest);
  document.getElementById("emi-total-payment").textContent = currency(totalPayment);

  if (startVal && months) {
    const start = new Date(startVal);
    const end = new Date(start);
    end.setMonth(end.getMonth() + months);
    document.getElementById("emi-end-date").textContent = end.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
  } else {
    document.getElementById("emi-end-date").textContent = "—";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const startField = document.getElementById("start_date");
  if (startField && !startField.value) startField.value = new Date().toISOString().slice(0, 10);

  ["principal_amount", "interest_rate", "tenure_months", "start_date"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", updateEmiPreview);
  });
  updateEmiPreview();
});
