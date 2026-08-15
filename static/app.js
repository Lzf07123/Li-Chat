"use strict";

const state = { me: null, ws: null };

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

async function loadMe() {
  let response;
  try {
    response = await fetch("/api/me", { credentials: "same-origin" });
  } catch {
    renderLoggedOut();
    return;
  }
  if (!response.ok) {
    renderLoggedOut();
    return;
  }
  state.me = await response.json();
  renderLoggedIn();
  connectWebSocket();
}

function renderLoggedOut() {
  document.getElementById("app").innerHTML = `
    <h1>Li&Chat</h1>
    <p class="subtitle">统一使用 Li&Pass 账号登录</p>
    <a class="btn" href="/oidc/login">使用 Li&Pass 登录</a>`;
}

function renderLoggedIn() {
  const me = state.me;
  const avatar = me.picture
    ? `<img class="avatar" src="${escapeHtml(me.picture)}" alt="头像" />`
    : `<div class="avatar placeholder">${escapeHtml(
        (me.nickname || me.sub).slice(0, 1).toUpperCase()
      )}</div>`;
  document.getElementById("app").innerHTML = `
    <h1>Li&Chat</h1>
    <div class="me">
      ${avatar}
      <span class="nickname">${escapeHtml(me.nickname || me.name || me.sub)}</span>
    </div>
    <div id="ws-status" class="status">连接中…</div>
    <button id="logout" class="btn secondary">退出登录</button>`;
  document.getElementById("logout").addEventListener("click", logout);
}

function logout() {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/oidc/logout";
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = "csrf_token";
  input.value = state.me.csrf_token;
  form.appendChild(input);
  document.body.appendChild(form);
  form.submit();
}

function connectWebSocket() {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
  state.ws = socket;
  const status = () => document.getElementById("ws-status");

  socket.addEventListener("open", () => {
    if (status()) status().textContent = "已连接";
  });
  socket.addEventListener("close", (event) => {
    if (status()) {
      status().textContent = event.code === 4401 ? "登录已失效" : "连接已断开";
    }
    if (event.code === 4401) {
      window.location.href = "/oidc/login";
    }
  });

  window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

loadMe();
