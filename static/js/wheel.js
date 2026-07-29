/**
 * Expense Wheel — renders category spend as annular sectors around a
 * central "liquid glass" orb. Data-driven so Add/Edit/Delete Category
 * instantly reshapes the wheel.
 */

const ICONS = {
  utensils: "🍽️", plane: "✈️", bag: "🛍️", film: "🎬", fuel: "⛽",
  book: "📚", cross: "➕", receipt: "🧾", calendar: "📅", dots: "⋯",
  tag: "🏷️", salary: "💼", investment: "📈", business: "🏢",
  loan: "🏦", home: "🏠", tech: "💻",
};

const SVG_NS = "http://www.w3.org/2000/svg";
const CENTER = 250;
const R_OUTER = 226;
const R_INNER = 148;
const GAP_DEG = 4;

function polar(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function sectorPath(startAngle, endAngle) {
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  const o1 = polar(CENTER, CENTER, R_OUTER, startAngle);
  const o2 = polar(CENTER, CENTER, R_OUTER, endAngle);
  const i1 = polar(CENTER, CENTER, R_INNER, endAngle);
  const i2 = polar(CENTER, CENTER, R_INNER, startAngle);
  return [
    `M ${o1.x} ${o1.y}`,
    `A ${R_OUTER} ${R_OUTER} 0 ${largeArc} 1 ${o2.x} ${o2.y}`,
    `L ${i1.x} ${i1.y}`,
    `A ${R_INNER} ${R_INNER} 0 ${largeArc} 0 ${i2.x} ${i2.y}`,
    "Z",
  ].join(" ");
}

function shadeColor(hex, percent) {
  const num = parseInt(hex.replace("#", ""), 16);
  let r = (num >> 16) + percent, g = ((num >> 8) & 0x00ff) + percent, b = (num & 0x0000ff) + percent;
  r = Math.min(255, Math.max(0, r)); g = Math.min(255, Math.max(0, g)); b = Math.min(255, Math.max(0, b));
  return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}

let wheelData = [];

async function loadWheel() {
  const svg = document.getElementById("wheel-svg");
  const tooltip = document.getElementById("wheel-tooltip");
  if (!svg) return;

  try {
    const res = await fetch("/api/wheel-data");
    wheelData = await res.json();
  } catch (err) {
    console.error("Could not load wheel data", err);
    return;
  }

  renderWheel(svg, tooltip, wheelData);
}

function renderWheel(svg, tooltip, categories) {
  svg.innerHTML = "";
  if (!categories.length) return;

  const defs = document.createElementNS(SVG_NS, "defs");
  svg.appendChild(defs);

  // Everything that should orbit lives inside this one rotating group.
  const rotator = document.createElementNS(SVG_NS, "g");
  rotator.setAttribute("class", "wheel-rotator");
  svg.appendChild(rotator);

  const n = categories.length;
  const sweep = 360 / n;

  categories.forEach((cat, i) => {
    const startAngle = i * sweep + GAP_DEG / 2;
    const endAngle = (i + 1) * sweep - GAP_DEG / 2;
    const midAngle = (startAngle + endAngle) / 2;
    const mid = polar(CENTER, CENTER, (R_OUTER + R_INNER) / 2, midAngle);

    // Glassy gradient per sector
    const gradId = `grad-${cat.id}`;
    const grad = document.createElementNS(SVG_NS, "linearGradient");
    grad.setAttribute("id", gradId);
    grad.setAttribute("x1", "0%"); grad.setAttribute("y1", "0%");
    grad.setAttribute("x2", "100%"); grad.setAttribute("y2", "100%");
    grad.innerHTML = `
      <stop offset="0%" stop-color="${shadeColor(cat.color, 35)}" />
      <stop offset="100%" stop-color="${cat.color}" />
    `;
    defs.appendChild(grad);

    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", sectorPath(startAngle, endAngle));
    path.setAttribute("fill", `url(#${gradId})`);
    path.setAttribute("stroke", "rgba(255,255,255,0.55)");
    path.setAttribute("stroke-width", "1.5");
    path.setAttribute("class", "wheel-sector");
    path.dataset.categoryId = cat.id;

    path.addEventListener("mouseenter", () => showTooltip(tooltip, cat, path, svg));
    path.addEventListener("mousemove", () => showTooltip(tooltip, cat, path, svg));
    path.addEventListener("mouseleave", () => tooltip.classList.remove("visible"));
    path.addEventListener("click", () => {
      window.location.href = `/expenses/add?category_id=${cat.id}`;
    });

    rotator.appendChild(path);

    // Icon + label sit in their own group that counter-rotates around this
    // same midpoint, so as the wheel orbits, the text always stays upright.
    const labelGroup = document.createElementNS(SVG_NS, "g");
    labelGroup.setAttribute("class", "wheel-label-counter");
    labelGroup.style.transformOrigin = `${mid.x}px ${mid.y}px`;

    const iconText = document.createElementNS(SVG_NS, "text");
    iconText.setAttribute("x", mid.x);
    iconText.setAttribute("y", mid.y - 10);
    iconText.setAttribute("text-anchor", "middle");
    iconText.setAttribute("class", "wheel-icon-badge");
    iconText.setAttribute("font-size", "20");
    iconText.textContent = ICONS[cat.icon] || "🏷️";
    labelGroup.appendChild(iconText);

    const nameText = document.createElementNS(SVG_NS, "text");
    nameText.setAttribute("x", mid.x);
    nameText.setAttribute("y", mid.y + 14);
    nameText.setAttribute("text-anchor", "middle");
    nameText.setAttribute("class", "wheel-label-name");
    nameText.textContent = cat.name.length > 10 ? cat.name.slice(0, 9) + "…" : cat.name;
    labelGroup.appendChild(nameText);

    const amountText = document.createElementNS(SVG_NS, "text");
    amountText.setAttribute("x", mid.x);
    amountText.setAttribute("y", mid.y + 29);
    amountText.setAttribute("text-anchor", "middle");
    amountText.setAttribute("class", "wheel-label-amount");
    amountText.textContent = cat.spent > 0 ? `₹${formatCompact(cat.spent)}` : "—";
    labelGroup.appendChild(amountText);

    rotator.appendChild(labelGroup);
  });
}

function formatCompact(n) {
  if (n >= 100000) return (n / 100000).toFixed(1) + "L";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n.toFixed(0);
}

function showTooltip(tooltip, cat, pathEl, svg) {
  const pathRect = pathEl.getBoundingClientRect();
  const wrapRect = svg.closest(".wheel-wrap").getBoundingClientRect();
  const left = pathRect.left + pathRect.width / 2 - wrapRect.left;
  const top = pathRect.top + pathRect.height / 2 - wrapRect.top;

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
  tooltip.innerHTML = `<strong>${cat.name}</strong><br>₹${cat.spent.toLocaleString("en-IN")} this month`;
  tooltip.classList.add("visible");
}

function initWheelCenter() {
  const center = document.getElementById("wheel-center");
  if (!center) return;
  center.addEventListener("click", () => {
    const target = document.getElementById("overview-panel");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      target.classList.add("pulse-highlight");
      setTimeout(() => target.classList.remove("pulse-highlight"), 1200);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadWheel();
  initWheelCenter();
});

// Expose so category add/edit/delete modals can trigger a re-render
window.refreshWheel = loadWheel;
