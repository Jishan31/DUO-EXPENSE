async function loadNotifications() {
  const list = document.getElementById("notif-list");
  const badge = document.getElementById("notif-badge");
  if (!list) return;

  try {
    const [budgetRes, loanRes, businessRes] = await Promise.all([
      fetch("/budgets/api"),
      fetch("/loans/api/alerts"),
      fetch("/business/api/alerts"),
    ]);
    const budgetData = await budgetRes.json();
    const loanData = await loanRes.json();
    const businessData = await businessRes.json();
    const alerts = [...(loanData.alerts || []), ...(businessData.alerts || []), ...(budgetData.alerts || [])];

    if (!alerts.length) {
      list.innerHTML = `<div class="notif-empty">You're all caught up — no alerts right now.</div>`;
      if (badge) badge.style.display = "none";
      return;
    }

    if (badge) badge.style.display = "block";
    list.innerHTML = alerts.map((a) => `
      <div class="notif-item">
        <span style="color:${a.color === '#E9607A' ? 'var(--danger)' : 'var(--warning)'}">⚠️</span>
        <span>${a.message}</span>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = `<div class="notif-empty">Couldn't load notifications.</div>`;
  }
}

function positionFloatingPanel(anchorEl, panelEl, panelWidth) {
  panelWidth = Math.min(panelWidth, window.innerWidth - 20); // never wider than the viewport, with a small margin
  panelEl.style.width = `${panelWidth}px`;

  const rect = anchorEl.getBoundingClientRect();
  const margin = 12;
  const spaceRight = window.innerWidth - rect.right;

  let left, top;
  if (spaceRight >= panelWidth + margin) {
    left = rect.right + margin;
    top = rect.top;
  } else {
    left = Math.max(10, Math.min(rect.left, window.innerWidth - panelWidth - 10));
    top = rect.bottom + 8;
  }

  const maxTop = window.innerHeight - 60;
  panelEl.style.left = `${left}px`;
  panelEl.style.top = `${Math.min(top, maxTop)}px`;
}

document.addEventListener("DOMContentLoaded", () => {
  loadNotifications();

  const bell = document.getElementById("notif-bell");
  const dropdown = document.getElementById("notif-dropdown");
  if (!bell || !dropdown) return;

  bell.addEventListener("click", (e) => {
    e.stopPropagation();
    positionFloatingPanel(bell, dropdown, 300);
    dropdown.classList.toggle("open");
  });
  window.addEventListener("resize", () => {
    if (dropdown.classList.contains("open")) positionFloatingPanel(bell, dropdown, 300);
  });
  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target) && e.target !== bell) {
      dropdown.classList.remove("open");
    }
  });
});
