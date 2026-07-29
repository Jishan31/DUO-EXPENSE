function escapeHtmlChat(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function appendBubble(container, role, text) {
  const empty = container.querySelector(".chat-empty");
  if (empty) empty.remove();

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function showTyping(container) {
  const typing = document.createElement("div");
  typing.className = "chat-typing";
  typing.id = "chat-typing-indicator";
  typing.innerHTML = "<span></span><span></span><span></span>";
  container.appendChild(typing);
  container.scrollTop = container.scrollHeight;
}

function hideTyping() {
  document.getElementById("chat-typing-indicator")?.remove();
}

async function loadChatHistory() {
  const container = document.getElementById("chat-messages");
  if (!container) return;
  try {
    const res = await fetch("/assistant/history");
    const messages = await res.json();
    if (messages.length) {
      container.querySelector(".chat-empty")?.remove();
      messages.forEach((m) => appendBubble(container, m.role, m.content));
    }
  } catch (err) {
    // history is a nice-to-have; a failed load just leaves the empty state
  }
}

async function sendChatMessage() {
  const input = document.getElementById("chat-input");
  const container = document.getElementById("chat-messages");
  const message = input.value.trim();
  if (!message) return;

  appendBubble(container, "user", message);
  input.value = "";
  input.disabled = true;
  showTyping(container);

  try {
    const res = await fetch("/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    hideTyping();

    if (data.error) {
      appendBubble(container, "error", data.error);
    } else {
      appendBubble(container, "assistant", data.reply);
    }
  } catch (err) {
    hideTyping();
    appendBubble(container, "error", "Couldn't reach the assistant — check your connection and try again.");
  } finally {
    input.disabled = false;
    input.focus();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const fab = document.getElementById("chat-fab");
  const panel = document.getElementById("chat-panel");
  const closeBtn = document.getElementById("chat-close-btn");
  const clearBtn = document.getElementById("chat-clear-btn");
  const sendBtn = document.getElementById("chat-send-btn");
  const input = document.getElementById("chat-input");
  if (!fab || !panel) return;

  let historyLoaded = false;

  fab.addEventListener("click", () => {
    panel.classList.add("open");
    fab.style.display = "none";
    if (!historyLoaded) { loadChatHistory(); historyLoaded = true; }
    input.focus();
  });

  closeBtn.addEventListener("click", () => {
    panel.classList.remove("open");
    fab.style.display = "flex";
  });

  clearBtn.addEventListener("click", async () => {
    if (!confirm("Clear this conversation?")) return;
    await fetch("/assistant/clear", { method: "POST" });
    const container = document.getElementById("chat-messages");
    container.innerHTML = `<div class="chat-empty">Ask me about your spending, budgets, loans, or how to use any feature.</div>`;
  });

  sendBtn.addEventListener("click", sendChatMessage);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });
});
