function getTransitionTarget() {
  return document.querySelector(".app-shell") || document.querySelector(".auth-shell") || document.body;
}

// ---------- Entrance ----------
document.addEventListener("DOMContentLoaded", () => {
  const target = getTransitionTarget();
  target.classList.add("page-enter-3d");
});

// A page restored from the browser's back/forward cache can still be
// showing the mid-animation "exit" state from when the user left it —
// always clear that on show so the page never appears stuck/invisible.
window.addEventListener("pageshow", () => {
  const target = getTransitionTarget();
  target.classList.remove("page-exit-3d");
});

// ---------- Exit (on internal link navigation) ----------
document.addEventListener("click", (e) => {
  try {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const link = e.target.closest("a[href]");
    if (!link) return;
    if (link.target === "_blank" || link.hasAttribute("download")) return;
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;

    const href = link.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:") || href.startsWith("javascript:")) return;

    let url;
    try { url = new URL(href, window.location.href); } catch (err) { return; }
    if (url.origin !== window.location.origin) return; // let external links navigate normally

    e.preventDefault();
    // Navigation is scheduled FIRST and unconditionally — if anything below
    // (the animation) fails, the page still navigates on time.
    setTimeout(() => { window.location.href = url.href; }, 220);

    try {
      getTransitionTarget().classList.add("page-exit-3d");
    } catch (animErr) {
      // cosmetic only — navigation above is already guaranteed
    }
  } catch (err) {
    // never let this handler block a click from working normally
  }
});
