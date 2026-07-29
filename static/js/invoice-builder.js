function currency(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// Native <select> dropdown popups ignore custom CSS in most browsers (Chrome on
// Windows in particular falls back to plain OS colors, unreadable in dark mode).
// This builds a fully custom-styled dropdown driven by the same hidden <select>,
// so every existing bit of logic that reads select.value / selectedOptions still
// works completely unchanged — only what's visually shown to the user is custom.
function buildCustomSelect(row) {
  const select = row.querySelector(".item-product-select");
  const wrap = row.querySelector(".custom-select-wrap");
  const btn = wrap.querySelector(".custom-select-btn");
  const list = wrap.querySelector(".custom-select-list");

  // Move the popup out of the scrollable table wrapper entirely — nested
  // inside .line-items-scroll (overflow-x: auto), an absolutely-positioned
  // dropdown gets silently clipped by the container's overflow, even though
  // it's technically "open". Reparenting to <body> with position:fixed and
  // positioning via the same helper the search/notification panels use
  // sidesteps that completely.
  document.body.appendChild(list);
  wrap._customList = list; // keep a reference since it's no longer a DOM child of wrap

  Array.from(select.options).forEach((opt, i) => {
    const item = document.createElement("div");
    item.className = "custom-select-option" + (i === select.selectedIndex ? " selected" : "");
    item.textContent = opt.textContent;
    item.dataset.index = i;
    item.addEventListener("click", () => {
      select.selectedIndex = i;
      select.dispatchEvent(new Event("change"));
      btn.textContent = opt.textContent;
      list.querySelectorAll(".custom-select-option").forEach((el) => el.classList.remove("selected"));
      item.classList.add("selected");
      list.classList.remove("open");
    });
    list.appendChild(item);
  });

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    document.querySelectorAll(".custom-select-list.open").forEach((l) => { if (l !== list) l.classList.remove("open"); });
    if (typeof positionFloatingPanel === "function") positionFloatingPanel(btn, list, 240);
    list.classList.toggle("open");
  });
}

document.addEventListener("click", () => {
  document.querySelectorAll(".custom-select-list.open").forEach((l) => l.classList.remove("open"));
});
document.addEventListener("scroll", () => {
  document.querySelectorAll(".custom-select-list.open").forEach((l) => l.classList.remove("open"));
}, true);

function addLineItem() {
  const template = document.getElementById("line-item-template");
  const body = document.getElementById("line-items-body");
  const clone = template.content.cloneNode(true);
  const row = clone.querySelector(".line-item-row");

  buildCustomSelect(row);

  row.querySelector(".item-product-select").addEventListener("change", function () {
    const opt = this.selectedOptions[0];
    const descField = row.querySelector(".item-description");
    const priceField = row.querySelector(".item-price");
    if (opt && opt.value) {
      descField.value = opt.dataset.name || "";
      priceField.value = opt.dataset.price || 0;
    }
    recalculate();
  });

  row.querySelectorAll(".item-qty, .item-price").forEach((el) => {
    el.addEventListener("input", recalculate);
  });

  row.querySelector(".remove-line-btn").addEventListener("click", () => {
    const wrap = row.querySelector(".custom-select-wrap");
    if (wrap && wrap._customList) wrap._customList.remove();
    row.remove();
    recalculate();
  });

  body.appendChild(clone);
}

function getLineItems() {
  const rows = document.querySelectorAll(".line-item-row");
  return Array.from(rows).map((row) => {
    const select = row.querySelector(".item-product-select");
    const opt = select.selectedOptions[0];
    const productId = select.value ? parseInt(select.value) : null;
    const quantity = parseInt(row.querySelector(".item-qty").value) || 1;
    const unitPrice = parseFloat(row.querySelector(".item-price").value) || 0;
    let description = row.querySelector(".item-description").value.trim();
    if (!description && opt && opt.dataset.name) description = opt.dataset.name;

    return {
      product_id: productId,
      description: description || "Item",
      quantity,
      unit_price: unitPrice,
      line_total: Math.round(quantity * unitPrice * 100) / 100,
      max_stock: opt ? parseInt(opt.dataset.stock || "0") : null,
    };
  });
}

function recalculate() {
  const items = getLineItems();

  document.querySelectorAll(".line-item-row").forEach((row, i) => {
    const totalCell = row.querySelector(".item-line-total");
    if (items[i]) totalCell.textContent = currency(items[i].line_total);
  });

  const subtotal = items.reduce((sum, i) => sum + i.line_total, 0);
  const discountPct = parseFloat(document.getElementById("discount_percent").value) || 0;
  const gstPct = parseFloat(document.getElementById("gst_percent").value) || 0;

  const discountAmount = subtotal * discountPct / 100;
  const taxable = subtotal - discountAmount;
  const gstAmount = taxable * gstPct / 100;
  const total = taxable + gstAmount;

  document.getElementById("preview-subtotal").textContent = currency(subtotal);
  document.getElementById("preview-discount").textContent = "-" + currency(discountAmount);
  document.getElementById("preview-gst").textContent = "+" + currency(gstAmount);
  document.getElementById("preview-total").textContent = currency(total);
}

function initInvoiceForm() {
  const form = document.getElementById("invoice-form");
  if (!form) return;

  document.getElementById("add-line-btn").addEventListener("click", addLineItem);
  document.getElementById("discount_percent").addEventListener("input", recalculate);
  document.getElementById("gst_percent").addEventListener("input", recalculate);

  addLineItem(); // start with one row so the form isn't empty

  form.addEventListener("submit", (e) => {
    const items = getLineItems().filter((i) => i.quantity > 0);

    if (!items.length) {
      e.preventDefault();
      alert("Add at least one line item before creating the invoice.");
      return;
    }

    for (const item of items) {
      if (item.max_stock !== null && item.quantity > item.max_stock) {
        e.preventDefault();
        alert(`Only ${item.max_stock} units of "${item.description}" are in stock.`);
        return;
      }
    }

    document.getElementById("items_json").value = JSON.stringify(items);
  });
}

document.addEventListener("DOMContentLoaded", initInvoiceForm);
