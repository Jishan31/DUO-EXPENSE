function toggleUploadState(loading) {
  document.getElementById("upload-drop-idle").style.display = loading ? "none" : "block";
  document.getElementById("upload-drop-loading").style.display = loading ? "block" : "none";
}

function findCategoryIdByName(name) {
  if (!name || !window.CATEGORY_MAP) return null;
  const entry = Object.entries(window.CATEGORY_MAP).find(([id, n]) => n.toLowerCase() === name.toLowerCase());
  return entry ? entry[0] : null;
}

function selectCategoryInPicker(categoryId) {
  const radio = document.querySelector(`.category-pick-item input[value="${categoryId}"]`);
  if (!radio) return;
  document.querySelectorAll(".category-pick-item").forEach((el) => el.classList.remove("selected"));
  radio.checked = true;
  radio.closest(".category-pick-item").classList.add("selected");
}

function renderDetectedItems(products) {
  const wrap = document.getElementById("ocr-items-wrap");
  const list = document.getElementById("ocr-items-list");
  if (!products || !products.length) {
    wrap.style.display = "none";
    return;
  }
  list.innerHTML = products.map((p) =>
    `<div class="flex-between" style="padding:4px 0;"><span>${escapeHtmlLocal(p.name)}</span><span class="tabular">₹${p.price}</span></div>`
  ).join("");
  wrap.style.display = "block";
}

function escapeHtmlLocal(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function handleReceiptFile(file) {
  if (!file) return;

  // Instant local preview
  const previewWrap = document.getElementById("receipt-preview-wrap");
  const previewImg = document.getElementById("receipt-preview-img");
  previewImg.src = URL.createObjectURL(file);
  previewWrap.style.display = "block";

  toggleUploadState(true);
  document.getElementById("ocr-warning").style.display = "none";

  const formData = new FormData();
  formData.append("receipt", file);

  try {
    const res = await fetch("/scanner/scan", { method: "POST", body: formData });
    const data = await res.json();
    toggleUploadState(false);

    if (data.error) {
      document.getElementById("ocr-warning").textContent = data.error;
      document.getElementById("ocr-warning").style.display = "block";
      return;
    }

    if (data.receipt_url) document.getElementById("receipt_path").value = data.receipt_url;

    if (data.merchant) {
      const merchantField = document.getElementById("merchant");
      if (merchantField) merchantField.value = data.merchant;
      const nameField = document.getElementById("name");
      if (nameField && !nameField.value) nameField.value = data.merchant;
    }
    if (data.amount) document.getElementById("amount").value = data.amount;
    if (data.gst_amount) document.getElementById("gst_amount").value = data.gst_amount;
    if (data.date) document.getElementById("date").value = data.date;

    const catId = findCategoryIdByName(data.suggested_category);
    if (catId) selectCategoryInPicker(catId);

    renderDetectedItems(data.products);

    if (data.warning) {
      document.getElementById("ocr-warning").textContent = data.warning;
      document.getElementById("ocr-warning").style.display = "block";
    } else {
      document.getElementById("upload-drop-idle").innerHTML =
        `✅ <strong>Receipt scanned</strong> — review the details below before saving<div class="field-hint">Tap here to scan a different receipt</div>`;
    }
  } catch (err) {
    toggleUploadState(false);
    document.getElementById("ocr-warning").textContent = "Something went wrong reading this receipt — please enter the details manually.";
    document.getElementById("ocr-warning").style.display = "block";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("receipt-input");
  if (input) input.addEventListener("change", (e) => handleReceiptFile(e.target.files[0]));

  const form = document.getElementById("expense-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      const hasCategory = document.querySelector('.category-pick-item input[type="radio"]:checked');
      const hint = document.getElementById("category-required-hint");
      if (!hasCategory) {
        e.preventDefault();
        if (hint) hint.style.display = "block";
        document.querySelector(".category-picker").scrollIntoView({ behavior: "smooth", block: "center" });
      } else if (hint) {
        hint.style.display = "none";
      }
    });
  }
});
