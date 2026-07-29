async function renderInventoryChart() {
  const canvas = document.getElementById("chart-inventory-pie");
  if (!canvas) return;

  try {
    const res = await fetch("/business/api/products");
    const products = await res.json();

    // Need purchase price too, which the lightweight products API omits —
    // pull it from the product cards already rendered server-side instead.
    const cards = document.querySelectorAll(".product-card");
    const labels = [];
    const data = [];
    const palette = ["#B57EDC", "#8E6FCE", "#A783E1", "#C79BEF", "#9A7FE0", "#7C5CBF", "#B08DE8", "#976FDB"];

    cards.forEach((card, i) => {
      const name = card.querySelector("h3")?.textContent?.trim();
      const figs = card.querySelectorAll(".fig-value");
      const stock = parseInt(figs[0]?.textContent) || 0;
      if (name && stock > 0) {
        labels.push(name);
        data.push(stock);
      }
    });

    if (!labels.length) {
      canvas.closest(".chart-canvas-wrap").innerHTML = `<div class="chart-empty">Add stock to a product to see this chart.</div>`;
      return;
    }

    new Chart(canvas, {
      type: "doughnut",
      data: { labels, datasets: [{ data, backgroundColor: palette, borderWidth: 2, borderColor: "#fff" }] },
      options: {
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 12, font: { size: 11 } } } },
      },
    });
  } catch (err) {
    console.error("Inventory chart failed to load", err);
  }
}

document.addEventListener("DOMContentLoaded", renderInventoryChart);
