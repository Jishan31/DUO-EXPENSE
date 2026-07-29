const ICON_OPTIONS = ["utensils", "plane", "bag", "film", "fuel", "book", "cross", "receipt", "calendar", "dots", "home", "tech", "tag"];
const ICON_GLYPH = { utensils:"🍽️", plane:"✈️", bag:"🛍️", film:"🎬", fuel:"⛽", book:"📚", cross:"➕", receipt:"🧾", calendar:"📅", dots:"⋯", home:"🏠", tech:"💻", tag:"🏷️" };
const COLOR_OPTIONS = ["#B57EDC", "#8E6FCE", "#A783E1", "#C79BEF", "#9A7FE0", "#7C5CBF", "#B08DE8", "#976FDB", "#856AC9", "#D0B6F5", "#E9607A", "#2FB77E"];

function currency(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function animateValue(el, to) {
  const from = 0;
  const duration = 700;
  const start = performance.now();
  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = currency(from + (to - from) * eased);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

async function loadSummary() {
  try {
    const res = await fetch("/api/summary");
    const data = await res.json();
    document.querySelectorAll("[data-field]").forEach((el) => {
      const field = el.dataset.field;
      if (field in data) animateValue(el, data[field]);
    });
  } catch (err) {
    console.error("Summary load failed", err);
  }
}

async function loadTransactions() {
  const body = document.getElementById("tx-body");
  if (!body) return;
  try {
    const res = await fetch("/api/recent-transactions");
    const rows = await res.json();
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="4" class="tx-empty">No expenses yet — add your first one from the wheel above.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((r) => `
      <tr>
        <td>${escapeHtml(r.name)}</td>
        <td><span class="tx-cat-dot" style="background:${r.color}"></span>${escapeHtml(r.category)}</td>
        <td>${r.date}</td>
        <td class="tabular">₹${Number(r.amount).toLocaleString("en-IN")}</td>
      </tr>
    `).join("");
  } catch (err) {
    body.innerHTML = `<tr><td colspan="4" class="tx-empty">Couldn't load transactions.</td></tr>`;
  }
}

async function loadBreakdown() {
  const list = document.getElementById("breakdown-list");
  if (!list) return;
  try {
    const res = await fetch("/api/wheel-data");
    const cats = await res.json();
    const total = cats.reduce((sum, c) => sum + c.spent, 0) || 1;
    const top = [...cats].sort((a, b) => b.spent - a.spent).slice(0, 6);

    if (!top.some((c) => c.spent > 0)) {
      list.innerHTML = `<p class="tx-empty">Nothing spent yet this month.</p>`;
      return;
    }

    list.innerHTML = top.map((c) => `
      <div class="breakdown-item">
        <span class="dot" style="background:${c.color}"></span>
        <span class="name">${escapeHtml(c.name)}</span>
        <span class="amt tabular">${currency(c.spent)}</span>
      </div>
      <div class="breakdown-bar-track">
        <div style="width:${Math.min((c.spent / total) * 100, 100)}%; height:100%; background:${c.color};"></div>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = `<p class="tx-empty">Couldn't load category breakdown.</p>`;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- Category modal ----------
let editingCategoryId = null;

function buildSwatches() {
  const iconWrap = document.getElementById("icon-swatches");
  const colorWrap = document.getElementById("color-swatches");
  if (iconWrap && !iconWrap.dataset.built) {
    iconWrap.innerHTML = ICON_OPTIONS.map((icon) =>
      `<div class="icon-swatch" data-icon="${icon}" onclick="selectIcon('${icon}')">${ICON_GLYPH[icon]}</div>`
    ).join("");
    iconWrap.dataset.built = "1";
  }
  if (colorWrap && !colorWrap.dataset.built) {
    colorWrap.innerHTML = COLOR_OPTIONS.map((c) =>
      `<div class="color-swatch" style="background:${c}" data-color="${c}" onclick="selectColor('${c}')"></div>`
    ).join("");
    colorWrap.dataset.built = "1";
  }
}

function selectIcon(icon) {
  document.querySelectorAll(".icon-swatch").forEach((el) => el.classList.toggle("selected", el.dataset.icon === icon));
  document.getElementById("category-modal-overlay").dataset.icon = icon;
}
function selectColor(color) {
  document.querySelectorAll(".color-swatch").forEach((el) => el.classList.toggle("selected", el.dataset.color === color));
  document.getElementById("category-modal-overlay").dataset.color = color;
}

function openCategoryModal(id, name, icon, color, budget) {
  buildSwatches();
  editingCategoryId = id || null;
  document.getElementById("category-modal-title").textContent = id ? "Edit Category" : "Add Category";
  document.getElementById("category-name").value = name || "";
  document.getElementById("category-budget").value = budget || "";
  selectIcon(icon || "tag");
  selectColor(color || COLOR_OPTIONS[0]);
  document.getElementById("category-modal-overlay").classList.add("open");
}
function closeCategoryModal() {
  document.getElementById("category-modal-overlay").classList.remove("open");
}

async function saveCategory(e) {
  e.preventDefault();
  const overlay = document.getElementById("category-modal-overlay");
  const payload = {
    name: document.getElementById("category-name").value.trim(),
    monthly_budget: document.getElementById("category-budget").value || 0,
    icon: overlay.dataset.icon || "tag",
    color: overlay.dataset.color || COLOR_OPTIONS[0],
  };
  if (!payload.name) return;

  const url = editingCategoryId ? `/categories/${editingCategoryId}/edit` : "/categories/add";
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("Save failed");
    closeCategoryModal();
    location.reload();
  } catch (err) {
    alert("Couldn't save the category. Please try again.");
  }
}

async function deleteCategory(id) {
  if (!confirm("Delete this category? Expenses inside it must be moved first.")) return;
  try {
    const res = await fetch(`/categories/${id}/delete`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Couldn't delete this category."); return; }
    location.reload();
  } catch (err) {
    alert("Couldn't delete this category.");
  }
}

async function loadDashboardAlerts() {
  const wrap = document.getElementById("dashboard-alerts");
  if (!wrap) return;
  try {
    const res = await fetch("/budgets/api");
    const data = await res.json();
    const alerts = (data.alerts || []).slice(0, 3);
    wrap.innerHTML = alerts.map((a) => `
      <div class="alert-banner ${a.type === 'category_warning' ? 'warning' : ''} reveal is-visible">⚠️ ${escapeHtml(a.message)}</div>
    `).join("");
  } catch (err) {
    // Fail silently — alerts are a bonus, not core functionality
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadSummary();
  loadTransactions();
  loadBreakdown();
  loadDashboardAlerts();

  const form = document.getElementById("category-form");
  if (form) form.addEventListener("submit", saveCategory);
});
