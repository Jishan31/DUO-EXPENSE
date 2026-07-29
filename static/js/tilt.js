const MAX_TILT_DEG = 7;
let activeTiltCard = null;
let tiltFrameQueued = false;
let lastTiltEvent = null;

function updateTilt() {
  tiltFrameQueued = false;
  if (!activeTiltCard || !lastTiltEvent) return;

  const rect = activeTiltCard.getBoundingClientRect();
  const px = (lastTiltEvent.clientX - rect.left) / rect.width;   // 0..1
  const py = (lastTiltEvent.clientY - rect.top) / rect.height;   // 0..1

  const rotateY = (px - 0.5) * MAX_TILT_DEG * 2;
  const rotateX = (0.5 - py) * MAX_TILT_DEG * 2;

  activeTiltCard.style.transform =
    `perspective(900px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateY(-6px) scale(1.02)`;
  activeTiltCard.style.setProperty("--mx", `${(px * 100).toFixed(1)}%`);
  activeTiltCard.style.setProperty("--my", `${(py * 100).toFixed(1)}%`);
}

function resetTiltCard(card) {
  if (!card) return;
  card.style.transform = "";
  card.style.removeProperty("--mx");
  card.style.removeProperty("--my");
}

function initCardTilt() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (window.matchMedia("(hover: none)").matches) return; // skip on touch devices

  document.addEventListener("pointermove", (e) => {
    const card = e.target.closest(".card");

    if (card !== activeTiltCard) {
      resetTiltCard(activeTiltCard);
      activeTiltCard = card;
    }
    if (!card) return;

    lastTiltEvent = e;
    if (!tiltFrameQueued) {
      tiltFrameQueued = true;
      requestAnimationFrame(updateTilt);
    }
  });

  document.addEventListener("pointerleave", () => {
    resetTiltCard(activeTiltCard);
    activeTiltCard = null;
  }, true);
}

document.addEventListener("DOMContentLoaded", initCardTilt);
