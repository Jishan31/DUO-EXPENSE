function paintGauges() {
  document.querySelectorAll(".gauge-wrap").forEach((wrap) => {
    const pct = Math.min(parseFloat(wrap.dataset.percent) || 0, 100);
    const circle = wrap.querySelector(".gauge-fill");
    if (!circle) return;
    const r = 50;
    const circumference = 2 * Math.PI * r;
    circle.style.strokeDasharray = `${circumference}`;
    circle.style.strokeDashoffset = `${circumference}`; // start empty, then animate in
    requestAnimationFrame(() => {
      setTimeout(() => {
        circle.style.strokeDashoffset = `${circumference - (pct / 100) * circumference}`;
      }, 80);
    });
  });
}

async function saveTotalBudget(e) {
  e.preventDefault();
  const input = document.getElementById("total-budget-input");
  const value = parseFloat(input.value || 0);
  try {
    const res = await fetch("/budgets/update-total", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ monthly_budget_total: value }),
    });
    if (!res.ok) throw new Error("failed");
    location.reload();
  } catch (err) {
    alert("Couldn't save your budget. Please try again.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  paintGauges();
  const form = document.getElementById("total-budget-form");
  if (form) form.addEventListener("submit", saveTotalBudget);
});
