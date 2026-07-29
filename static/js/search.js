let searchDebounceTimer = null;

function escapeHtmlSearch(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderSearchResults(groups, panel) {
  const groupNames = Object.keys(groups);
  if (!groupNames.length) {
    panel.innerHTML = `<div class="notif-empty">No matches yet — try a different term.</div>`;
    return;
  }

  panel.innerHTML = groupNames.map((name) => `
    <div class="search-group">
      <div class="search-group-label">${name}</div>
      ${groups[name].map((item) => `
        <a class="search-result-item" href="${item.url}">
          <span class="sr-label">${escapeHtmlSearch(item.label)}</span>
          <span class="sr-subtitle">${escapeHtmlSearch(item.subtitle)}</span>
        </a>
      `).join("")}
    </div>
  `).join("");
}

async function runSearch(query, panel) {
  if (query.length < 2) {
    panel.classList.remove("open");
    return;
  }
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    renderSearchResults(data, panel);
    panel.classList.add("open");
  } catch (err) {
    panel.innerHTML = `<div class="notif-empty">Search failed — try again.</div>`;
    panel.classList.add("open");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("global-search");
  const panel = document.getElementById("search-results");
  if (!input || !panel) return;

  input.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    const query = input.value.trim();
    if (!query) {
      panel.classList.remove("open");
      return;
    }
    searchDebounceTimer = setTimeout(() => {
      positionFloatingPanel(input, panel, 320);
      runSearch(query, panel);
    }, 250);
  });

  input.addEventListener("focus", () => {
    if (input.value.trim().length >= 2) {
      positionFloatingPanel(input, panel, 320);
      panel.classList.add("open");
    }
  });

  document.addEventListener("click", (e) => {
    if (!panel.contains(e.target) && e.target !== input) {
      panel.classList.remove("open");
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { panel.classList.remove("open"); input.blur(); }
  });
});
