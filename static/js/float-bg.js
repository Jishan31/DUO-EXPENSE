const FLOAT_SYMBOLS = ["₹", "$", "€", "💰", "🪙", "💵", "📈", "📊", "💳", "🏦"];

function rand(min, max) { return Math.random() * (max - min) + min; }

function buildFloatSymbols() {
  const container = document.getElementById("float-symbols");
  if (!container) return [];

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const count = window.innerWidth < 700 ? 8 : 14;
  const nodes = [];

  for (let i = 0; i < count; i++) {
    const el = document.createElement("span");
    el.className = "float-symbol";
    el.textContent = FLOAT_SYMBOLS[i % FLOAT_SYMBOLS.length];
    el.setAttribute("aria-hidden", "true");

    const left = rand(2, 94);
    const top = rand(4, 90);
    const size = rand(20, 42);
    const depth = rand(0.4, 1.0); // how strongly this symbol reacts to the cursor

    el.style.left = `${left}%`;
    el.style.top = `${top}%`;
    el.style.setProperty("--fs-size", `${size}px`);
    el.style.setProperty("--fs-opacity", rand(0.08, 0.2).toFixed(2));
    el.style.setProperty("--fs-drift", `${rand(-34, -14).toFixed(0)}px`);
    el.style.setProperty("--fs-duration", `${rand(10, 22).toFixed(1)}s`);
    el.style.setProperty("--fs-delay", `${rand(-10, 0).toFixed(1)}s`);
    el.style.setProperty("--fs-spin-duration", `${rand(18, 40).toFixed(1)}s`);
    el.style.setProperty("--fs-spin-delay", `${rand(-15, 0).toFixed(1)}s`);
    el.style.setProperty("--fs-rot", `${rand(0, 360).toFixed(0)}deg`);
    el.dataset.depth = depth.toFixed(2);

    if (reduceMotion) {
      el.style.animation = "none";
    }

    container.appendChild(el);
    nodes.push(el);
  }
  return nodes;
}

function initCursorParallax(nodes) {
  if (!nodes.length) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (window.matchMedia("(hover: none)").matches) return; // skip on touch-only devices

  let targetX = 0, targetY = 0;
  let frameQueued = false;

  window.addEventListener("mousemove", (e) => {
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    targetX = (e.clientX - cx) / cx;  // -1 .. 1
    targetY = (e.clientY - cy) / cy;  // -1 .. 1

    if (!frameQueued) {
      frameQueued = true;
      requestAnimationFrame(applyParallax);
    }
  });

  function applyParallax() {
    frameQueued = false;
    nodes.forEach((el) => {
      const depth = parseFloat(el.dataset.depth) || 0.6;
      const px = targetX * 22 * depth;
      const py = targetY * 22 * depth;
      el.style.setProperty("--px", `${px.toFixed(1)}px`);
      el.style.setProperty("--py", `${py.toFixed(1)}px`);
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const nodes = buildFloatSymbols();
  initCursorParallax(nodes);
});
