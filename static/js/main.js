// ---------- Theme (dark / light) ----------
// NOTE: the actual data-theme attribute is set synchronously in an inline
// <script> in base.html's <head>, before first paint, to avoid a flash of
// the wrong theme. This just wires up the toggle button to match and react.
const THEME_CYCLE = ["light", "dark", "ocean", "sunset"];
const THEME_ICONS = { light: "☀️", dark: "🌙", ocean: "🌊", sunset: "🌅" };
const THEME_LABELS = { light: "Light", dark: "Dark", ocean: "Ocean", sunset: "Sunset" };

function setToggleIcon(btn, theme) {
  btn.textContent = THEME_ICONS[theme] || THEME_ICONS.light;
  btn.title = `Theme: ${THEME_LABELS[theme] || "Light"} (click to change)`;
}

function initTheme() {
  const theme = document.documentElement.getAttribute("data-theme") || "light";
  document.querySelectorAll(".theme-toggle").forEach((btn) => {
    setToggleIcon(btn, theme);
    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const idx = THEME_CYCLE.indexOf(current);
      const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("duo-theme", next);
      setToggleIcon(btn, next);
    });
  });
}

// ---------- Button ripple ----------
function initRipples() {
  document.querySelectorAll(".btn").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      const rect = this.getBoundingClientRect();
      const ripple = document.createElement("span");
      const size = Math.max(rect.width, rect.height);
      ripple.className = "ripple";
      ripple.style.width = ripple.style.height = `${size}px`;
      ripple.style.left = `${e.clientX - rect.left - size / 2}px`;
      ripple.style.top = `${e.clientY - rect.top - size / 2}px`;
      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 650);
    });
  });
}

// ---------- Flash messages auto-dismiss ----------
function initFlashes() {
  document.querySelectorAll(".flash").forEach((flash, i) => {
    setTimeout(() => {
      flash.style.opacity = "0";
      flash.style.transform = "translateX(30px)";
      setTimeout(() => flash.remove(), 400);
    }, 4200 + i * 300);
  });
}

// ---------- Scroll reveal ----------
function initReveal() {
  const items = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || !items.length) {
    items.forEach((i) => i.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );
  items.forEach((i) => observer.observe(i));
}

// ---------- Time-of-day greeting (dashboard) ----------
function initTimeGreeting() {
  const el = document.getElementById("time-greeting");
  if (!el) return;
  const hour = new Date().getHours();
  let word = "evening";
  if (hour >= 5 && hour < 12) word = "morning";
  else if (hour >= 12 && hour < 17) word = "afternoon";
  else if (hour >= 17 && hour < 21) word = "evening";
  else word = "night";
  el.textContent = word;
}

// ---------- Password strength (register/account pages) ----------
// Mirrors utils/validators.py::password_strength() exactly — client and
// server must never disagree about what counts as weak/moderate/strong.
function scorePassword(val) {
  if (!val) return { level: "weak", score: 0 };
  let score = 0;
  if (val.length >= 8) score++;
  if (val.length >= 12) score++;
  if (/[a-z]/.test(val) && /[A-Z]/.test(val)) score++;
  if (/[0-9]/.test(val)) score++;
  if (/[^A-Za-z0-9]/.test(val)) score++;
  const level = score <= 2 ? "weak" : score <= 3 ? "moderate" : "strong";
  return { level, score };
}

function initPasswordStrength() {
  document.querySelectorAll("[data-password-strength]").forEach((input) => {
    const wrap = input.closest(".field");
    const meter = wrap ? wrap.querySelector(".strength-meter") : null;
    const label = wrap ? wrap.querySelector(".strength-label") : null;
    if (!meter) return;

    input.addEventListener("input", () => {
      const val = input.value;
      const { level } = scorePassword(val);
      const styles = {
        weak: { width: "30%", color: "#E9607A", text: "Weak — add more variety or length" },
        moderate: { width: "65%", color: "#E0A64A", text: "Moderate — good enough, could be stronger" },
        strong: { width: "100%", color: "#2FB77E", text: "Strong" },
      };
      const s = styles[level];
      meter.style.width = val.length ? s.width : "0%";
      meter.style.background = s.color;
      if (label) label.textContent = val.length ? s.text : "";
    });
  });
}

// ---------- Phone OTP flow (register page) ----------
function initOtpFlow() {
  const phoneToggle = document.getElementById("use-phone-toggle");
  const otpSection = document.getElementById("otp-section");
  const sendOtpBtn = document.getElementById("send-otp-btn");
  const otpStatus = document.getElementById("otp-status");
  const otpInput = document.getElementById("otp");
  if (!phoneToggle) return;

  phoneToggle.addEventListener("change", () => {
    otpSection.style.display = phoneToggle.checked ? "block" : "none";
  });

  if (sendOtpBtn) {
    sendOtpBtn.addEventListener("click", () => {
      const phone = document.getElementById("phone").value.trim();
      const region = document.getElementById("region").value;
      if (!phone) {
        otpStatus.textContent = "Enter a phone number first.";
        otpStatus.style.color = "var(--danger)";
        return;
      }
      sendOtpBtn.disabled = true;
      sendOtpBtn.textContent = "Sending…";
      fetch("/send-otp", { method: "POST", body: new URLSearchParams({ phone, region }) })
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
          if (!ok) {
            otpStatus.textContent = data.error || "Couldn't send the code.";
            otpStatus.style.color = "var(--danger)";
            sendOtpBtn.disabled = false;
            sendOtpBtn.textContent = "Send OTP";
            return;
          }
          sendOtpBtn.textContent = "Code sent ✓";
          otpStatus.textContent = data.message;
          otpStatus.style.color = "var(--success)";
          if (otpInput) otpInput.focus();
        })
        .catch(() => {
          otpStatus.textContent = "Network error — try again.";
          otpStatus.style.color = "var(--danger)";
          sendOtpBtn.disabled = false;
          sendOtpBtn.textContent = "Send OTP";
        });
    });
  }

  if (otpInput) {
    otpInput.addEventListener("input", () => {
      if (otpInput.value.length !== 6) return;
      fetch("/verify-otp", { method: "POST", body: new URLSearchParams({ otp: otpInput.value }) })
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
          if (ok && data.verified) {
            otpStatus.textContent = "✓ Phone verified";
            otpStatus.style.color = "var(--success)";
            otpInput.disabled = true;
            document.getElementById("phone").disabled = true;
          } else {
            otpStatus.textContent = data.error || "Incorrect code.";
            otpStatus.style.color = "var(--danger)";
          }
        });
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initRipples();
  initFlashes();
  initReveal();
  initPasswordStrength();
  initOtpFlow();
  initTimeGreeting();
});
