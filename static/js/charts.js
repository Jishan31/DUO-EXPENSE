const CHART_FONT = "'Inter', sans-serif";
const chartInstances = [];

function currentThemeTextColor() {
  const val = getComputedStyle(document.body).getPropertyValue("--ink-soft").trim();
  return val || "#5B4D77";
}
function currentThemeGridColor() {
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "rgba(181,126,220,0.15)"
    : "rgba(124,92,191,0.08)";
}

function applyChartTheme() {
  const text = currentThemeTextColor();
  const grid = currentThemeGridColor();
  Chart.defaults.color = text;

  chartInstances.forEach((chart) => {
    const legend = chart.options.plugins?.legend;
    if (legend && legend.display !== false) {
      legend.labels = legend.labels || {};
      legend.labels.color = text;
    }

    Object.values(chart.options.scales || {}).forEach((scale) => {
      scale.ticks = scale.ticks || {};
      scale.ticks.color = text;
      if (scale.grid) scale.grid.color = grid;
    });

    chart.update();
  });
}

Chart.defaults.font.family = CHART_FONT;

function emptyState(canvasId, message) {
  const canvas = document.getElementById(canvasId);
  const wrap = canvas.closest(".chart-canvas-wrap");
  wrap.innerHTML = `<div class="chart-empty">${message}</div>`;
}

async function renderCategoryPie() {
  const res = await fetch("/api/charts/category-pie");
  const d = await res.json();
  if (!d.labels.length) return emptyState("chart-category-pie", "No expenses logged this month yet.");

  const chart1 = new Chart(document.getElementById("chart-category-pie"), {
    type: "doughnut",
    data: { labels: d.labels, datasets: [{ data: d.data, backgroundColor: d.colors, borderWidth: 2, borderColor: "#fff" }] },
    options: {
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 14, font: { size: 11.5 } } } },
    },
  });
  chartInstances.push(chart1);
}

async function renderPaymentMode() {
  const res = await fetch("/api/charts/payment-mode");
  const d = await res.json();
  if (!d.labels.length) return emptyState("chart-payment-mode", "No expenses logged this month yet.");

  const chart2 = new Chart(document.getElementById("chart-payment-mode"), {
    type: "doughnut",
    data: { labels: d.labels, datasets: [{ data: d.data, backgroundColor: d.colors, borderWidth: 2, borderColor: "#fff" }] },
    options: {
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 14, font: { size: 11.5 } } } },
    },
  });
  chartInstances.push(chart2);
}

async function renderIncomeExpense() {
  const res = await fetch("/api/charts/income-vs-expense");
  const d = await res.json();
  const chart3 = new Chart(document.getElementById("chart-income-expense"), {
    type: "bar",
    data: {
      labels: d.labels,
      datasets: [
        { label: "Income", data: d.income, backgroundColor: "#2FB77E", borderRadius: 6, maxBarThickness: 28 },
        { label: "Expense", data: d.expense, backgroundColor: "#E9607A", borderRadius: 6, maxBarThickness: 28 },
      ],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { beginAtZero: true, grid: { color: "rgba(124,92,191,0.08)" } },
        x: { grid: { display: false } },
      },
    },
  });
  chartInstances.push(chart3);
}

async function renderMonthlyTrend() {
  const res = await fetch("/api/charts/monthly-trend");
  const d = await res.json();
  const chart4 = new Chart(document.getElementById("chart-monthly-trend"), {
    type: "line",
    data: {
      labels: d.labels,
      datasets: [{
        label: "Expenses", data: d.data, borderColor: "#7C5CBF", backgroundColor: "rgba(181,126,220,0.18)",
        fill: true, tension: 0.4, pointBackgroundColor: "#7C5CBF", pointRadius: 4,
      }],
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, grid: { color: "rgba(124,92,191,0.08)" } }, x: { grid: { display: false } } },
    },
  });
  chartInstances.push(chart4);
}

async function renderWeeklyTrend() {
  const res = await fetch("/api/charts/weekly-trend");
  const d = await res.json();
  const chart5 = new Chart(document.getElementById("chart-weekly-trend"), {
    type: "bar",
    data: { labels: d.labels, datasets: [{ label: "Spend", data: d.data, backgroundColor: "#B57EDC", borderRadius: 8, maxBarThickness: 34 }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, grid: { color: "rgba(124,92,191,0.08)" } }, x: { grid: { display: false } } },
    },
  });
  chartInstances.push(chart5);
}

document.addEventListener("DOMContentLoaded", () => {
  Chart.defaults.color = currentThemeTextColor(); // set AFTER main.js has applied the saved theme

  renderCategoryPie();
  renderPaymentMode();
  renderIncomeExpense();
  renderMonthlyTrend();
  renderWeeklyTrend();

  document.querySelectorAll(".theme-toggle").forEach((btn) => {
    btn.addEventListener("click", () => setTimeout(applyChartTheme, 0));
  });
});
