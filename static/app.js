"use strict";

const state = {
  me: null,
  ws: null,
  pingTimer: null,
  loggingOut: false,
  friends: [],
  requests: { incoming: [], outgoing: [] },
  recommendations: [],
  searchResults: [],
  conversations: [],
  readUpTo: {},
  activeSub: null,
  activePeer: null,
  messages: [],
  nextBefore: null,
  loadingHistory: false,
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function footerHtml() {
  return `<footer class="site-footer">${escapeHtml(BRAND.footer())}</footer>`;
}

function themeToggleHtml() {
  return `
    <button id="theme-toggle" class="icon-btn theme-toggle" type="button" aria-label="切换主题">
      <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" aria-hidden="true">
        <circle cx="12" cy="12" r="4"/>
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
      </svg>
      <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    </button>`;
}

function mount(className, inner) {
  const app = document.getElementById("app");
  app.className = className;
  app.innerHTML = inner;
  LiChatTheme.initTheme();
}

function displayName(user) {
  return user.nickname || user.name || user.sub;
}

function avatarHtml(user) {
  const initial = escapeHtml(displayName(user).slice(0, 1).toUpperCase());
  return user.picture
    ? `<img class="avatar" src="${escapeHtml(user.picture)}" alt="头像" />`
    : `<div class="avatar avatar-placeholder" aria-hidden="true">${initial}</div>`;
}

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers);
  if (typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }
  if (state.me) headers["X-CSRF-Token"] = state.me.csrf_token;
  let response;
  try {
    response = await fetch(path, Object.assign({}, options, {
      credentials: "same-origin",
      headers,
    }));
  } catch {
    throw new Error("网络错误，请稍后重试");
  }
  if (response.status === 401) {
    window.location.href = "/";
    throw new Error("登录已失效");
  }
  return response;
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
  window.LiChatAmbient && window.LiChatAmbient.setDensity(10);
  mount(
    "auth-shell",
    `${themeToggleHtml()}
    <div class="auth-brand">${BRAND.logo}<span class="brand-name">${escapeHtml(BRAND.name)}</span></div>
    <p class="slogan">${escapeHtml(BRAND.slogan)}</p>
    <section class="card card-interactive auth-card page-enter">
      <h1>欢迎回来</h1>
      <p class="muted">统一使用 Li&Pass 账号登录，本地不保存密码。</p>
      <a class="btn btn-primary" href="/oidc/login">使用 Li&Pass 登录</a>
    </section>
    ${footerHtml()}`
  );
}

function headerHtml() {
  return `<header class="app-header">
    <div class="app-brand">${BRAND.logo}<span>${escapeHtml(BRAND.name)}</span></div>
    <div class="app-actions">
      <div class="app-profile">
        <button id="profile-toggle" class="profile-toggle" type="button"
          aria-haspopup="menu" aria-expanded="false" aria-label="个人菜单">
          <div class="ws-status header-status">
            <span id="ws-dot" class="status-dot status-connecting" aria-hidden="true"></span>
            <span id="ws-text" role="status">连接中…</span>
          </div>
          ${avatarHtml(state.me)}
          <span class="profile-name">${escapeHtml(displayName(state.me))}</span>
          <svg class="profile-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M6 9l6 6 6-6"/>
          </svg>
        </button>
        <div id="profile-dropdown" class="profile-dropdown" role="menu" aria-label="个人菜单" hidden>
          <div class="profile-dropdown-header">
            ${avatarHtml(state.me)}
            <span class="profile-name">${escapeHtml(displayName(state.me))}</span>
          </div>
          <button id="logout" class="profile-menu-item" role="menuitem" type="button">
            退出登录
          </button>
        </div>
      </div>
      ${themeToggleHtml()}
    </div>
  </header>`;
}

function mainHtml() {
  return `<main class="app-main app-main-chat">
    <aside class="chat-sidebar" aria-label="好友与申请">
      <form id="search-form" class="search-box">
        <label class="sr-only" for="search-input">搜索用户</label>
        <input id="search-input" class="input" type="search" maxlength="64"
          placeholder="按昵称或邮箱搜索" autocomplete="off" />
        <button class="btn btn-primary btn-sm" type="submit">搜索</button>
      </form>
      <ul id="search-results" class="contact-list search-results" hidden></ul>
      <section class="sidebar-section">
        <h2 class="sidebar-title">好友申请
          <span id="requests-badge" class="badge badge-primary" hidden>0</span>
        </h2>
        <p id="requests-empty" class="sidebar-empty">暂无申请</p>
        <ul id="requests-list" class="contact-list"></ul>
      </section>
      <section class="sidebar-section">
        <h2 class="sidebar-title">好友推荐
          <button id="recommend-refresh" class="icon-btn refresh-btn" type="button"
            aria-label="刷新推荐">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-2.64-6.36"/>
              <path d="M21 3v6h-6"/>
            </svg>
          </button>
        </h2>
        <p id="recommend-empty" class="sidebar-empty">暂时没有可推荐的人</p>
        <ul id="recommend-list" class="contact-list"></ul>
      </section>
      <section class="sidebar-section">
        <h2 class="sidebar-title">好友</h2>
        <p id="friends-empty" class="sidebar-empty">还没有好友，先搜索添加</p>
        <ul id="friends-list" class="contact-list"></ul>
      </section>
    </aside>
    <section id="chat-panel" class="chat-panel" aria-label="聊天">
      <div id="chat-empty" class="chat-empty">
        <p>选择一个好友开始聊天</p>
        <p class="muted">对话只在你们之间流动</p>
      </div>
      <div id="chat-active" class="chat-active" hidden>
        <header class="chat-header">
          <button id="chat-back" class="icon-btn chat-back" type="button" aria-label="返回好友列表">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
          </button>
          <div class="chat-peer" id="chat-peer"></div>
        </header>
        <div class="messages-wrap">
          <button id="load-older" class="btn btn-ghost btn-sm load-older" type="button" hidden>
            加载更早消息
          </button>
          <div id="messages" class="messages" role="log" aria-live="polite" aria-label="聊天记录"></div>
        </div>
        <form id="composer" class="composer">
          <label class="sr-only" for="message-input">消息内容</label>
          <textarea id="message-input" class="input" rows="1" maxlength="2000"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"></textarea>
          <button class="btn btn-primary" type="submit">发送</button>
        </form>
      </div>
    </section>
  </main>
  ${footerHtml()}`;
}

function renderLoggedIn() {
  window.LiChatAmbient && window.LiChatAmbient.setDensity(8);
  mount("app-shell", `${headerHtml()} ${mainHtml()}`);
  document.getElementById("profile-toggle").addEventListener("click", onProfileToggle);
  document.addEventListener("click", onProfileClickOutside);
  document.addEventListener("keydown", onProfileKeydown);
  document.getElementById("logout").addEventListener("click", logout);
  document.getElementById("search-form").addEventListener("submit", onSearch);
  document.getElementById("search-results").addEventListener("click", onSearchResultClick);
  document.getElementById("requests-list").addEventListener("click", onRequestListClick);
  document.getElementById("recommend-list").addEventListener("click", onRecommendListClick);
  document.getElementById("recommend-refresh").addEventListener("click", loadRecommendations);
  document.getElementById("friends-list").addEventListener("click", onFriendListClick);
  document.getElementById("composer").addEventListener("submit", onComposerSubmit);
  document.getElementById("message-input").addEventListener("keydown", onComposerKeydown);
  document.getElementById("load-older").addEventListener("click", loadOlder);
  document.getElementById("chat-back").addEventListener("click", closeChat);
  refreshSidebar();
}

function setProfileMenu(open) {
  const dropdown = document.getElementById("profile-dropdown");
  const toggle = document.getElementById("profile-toggle");
  dropdown.hidden = !open;
  toggle.setAttribute("aria-expanded", String(open));
}

function onProfileToggle(event) {
  event.stopPropagation();
  setProfileMenu(document.getElementById("profile-dropdown").hidden);
}

function onProfileClickOutside(event) {
  const dropdown = document.getElementById("profile-dropdown");
  if (!dropdown.hidden && !event.target.closest(".app-profile")) {
    setProfileMenu(false);
  }
}

function onProfileKeydown(event) {
  const dropdown = document.getElementById("profile-dropdown");
  if (event.key === "Escape" && !dropdown.hidden) {
    setProfileMenu(false);
    document.getElementById("profile-toggle").focus();
  }
}

async function refreshSidebar() {
  try {
    const [friendsRes, requestsRes, recommendRes, conversationsRes] = await Promise.all([
      api("/api/friends"),
      api("/api/friends/requests"),
      api("/api/friends/recommendations"),
      api("/api/conversations"),
    ]);
    if (friendsRes.ok) state.friends = (await friendsRes.json()).friends;
    if (requestsRes.ok) state.requests = await requestsRes.json();
    if (recommendRes.ok) {
      state.recommendations = (await recommendRes.json()).friends;
    }
    if (conversationsRes.ok) {
      state.conversations = (await conversationsRes.json()).conversations;
    }
    renderSidebar();
  } catch {
    /* 登录失效已由 api() 统一跳转 */
  }
}

function renderSidebar() {
  const badge = document.getElementById("requests-badge");
  badge.hidden = state.requests.incoming.length === 0;
  badge.textContent = String(state.requests.incoming.length);
  document.getElementById("requests-empty").hidden =
    state.requests.incoming.length + state.requests.outgoing.length > 0;
  document.getElementById("requests-list").innerHTML = [
    ...state.requests.incoming.map(requestIncomingHtml),
    ...state.requests.outgoing.map(requestOutgoingHtml),
  ].join("");
  document.getElementById("recommend-empty").hidden = state.recommendations.length > 0;
  document.getElementById("recommend-list").innerHTML = state.recommendations
    .map(recommendHtml)
    .join("");
  const summaries = new Map(
    state.conversations.map((item) => [item.peer.sub, item])
  );
  const friends = state.conversations.map((item) => item.peer);
  for (const friend of state.friends) {
    if (!friends.some((item) => item.sub === friend.sub)) friends.push(friend);
  }
  document.getElementById("friends-empty").hidden = friends.length > 0;
  document.getElementById("friends-list").innerHTML = friends
    .map((friend) => friendHtml(friend, summaries.get(friend.sub)))
    .join("");
}

function requestIncomingHtml(item) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(item.requester)}
      <span class="contact-name">${escapeHtml(displayName(item.requester))}</span>
    </div>
    <div class="contact-actions">
      <button class="btn btn-primary btn-sm" type="button"
        data-action="accept" data-sub="${escapeHtml(item.requester.sub)}">接受</button>
      <button class="btn btn-ghost btn-sm" type="button"
        data-action="reject" data-sub="${escapeHtml(item.requester.sub)}">拒绝</button>
    </div>
  </li>`;
}

function requestOutgoingHtml(item) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(item.addressee)}
      <span class="contact-name">${escapeHtml(displayName(item.addressee))}</span>
    </div>
    <button class="btn btn-ghost btn-sm" type="button"
      data-action="cancel" data-sub="${escapeHtml(item.addressee.sub)}">撤回</button>
  </li>`;
}

function recommendHtml(user) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(user)}
      <span class="contact-name">${escapeHtml(displayName(user))}</span>
    </div>
    <button class="btn btn-primary btn-sm" type="button"
      data-action="add" data-sub="${escapeHtml(user.sub)}">添加</button>
  </li>`;
}

function friendHtml(friend, summary) {
  const unread = summary ? summary.unread_count : 0;
  const preview = summary && summary.last_message
    ? summary.last_message.content
    : "";
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open" data-sub="${escapeHtml(friend.sub)}">
      ${avatarHtml(friend)}
      <span class="contact-main">
        <span class="contact-name">${escapeHtml(displayName(friend))}</span>
        ${preview ? `<span class="contact-preview">${escapeHtml(preview)}</span>` : ""}
      </span>
      ${unread > 0
        ? `<span class="badge badge-unread" data-role="unread" data-sub="${escapeHtml(friend.sub)}">${unread}</span>`
        : ""}
    </button>
  </li>`;
}

function searchResultHtml(result) {
  const actions = {
    none: `<button class="btn btn-primary btn-sm" type="button"
      data-action="add" data-sub="${escapeHtml(result.sub)}">添加好友</button>`,
    incoming: `<span class="badge badge-warning">待你处理</span>`,
    outgoing: `<span class="badge badge-muted">已申请</span>`,
    friends: `<button class="btn btn-secondary btn-sm" type="button"
      data-action="open" data-sub="${escapeHtml(result.sub)}">发消息</button>`,
  };
  return `<li class="contact-item search-item">
    <div class="contact-info">
      ${avatarHtml(result)}
      <span class="contact-name">${escapeHtml(displayName(result))}</span>
    </div>
    ${actions[result.friend_status] || actions.none}
  </li>`;
}

async function onSearch(event) {
  event.preventDefault();
  const input = document.getElementById("search-input");
  const query = input.value.trim();
  const results = document.getElementById("search-results");
  if (!query) {
    results.hidden = true;
    return;
  }
  const response = await api(`/api/users/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    results.hidden = true;
    return;
  }
  state.searchResults = (await response.json()).results;
  results.hidden = state.searchResults.length === 0;
  results.innerHTML = state.searchResults.map(searchResultHtml).join("");
}

async function onSearchResultClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "open") {
    openChat(button.dataset.sub);
    return;
  }
  const response = await api("/api/friends/requests", {
    method: "POST",
    body: JSON.stringify({ to_sub: button.dataset.sub }),
  });
  if (response.ok || response.status === 409) {
    await refreshSidebar();
    document.getElementById("search-input").value = "";
    document.getElementById("search-results").hidden = true;
  }
}

async function onRequestListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const sub = button.dataset.sub;
  if (button.dataset.action === "accept") {
    await api(`/api/friends/requests/${encodeURIComponent(sub)}/accept`, { method: "POST" });
  } else if (button.dataset.action === "reject") {
    await api(`/api/friends/requests/${encodeURIComponent(sub)}/reject`, { method: "POST" });
  } else if (button.dataset.action === "cancel") {
    await api(`/api/friends/${encodeURIComponent(sub)}`, { method: "DELETE" });
  }
  await refreshSidebar();
}

async function onRecommendListClick(event) {
  const button = event.target.closest("button[data-action='add']");
  if (!button) return;
  const response = await api("/api/friends/requests", {
    method: "POST",
    body: JSON.stringify({ to_sub: button.dataset.sub }),
  });
  if (response.ok || response.status === 409) await refreshSidebar();
}

async function loadRecommendations() {
  const response = await api("/api/friends/recommendations");
  if (response.ok) {
    state.recommendations = (await response.json()).friends;
    document.getElementById("recommend-empty").hidden = state.recommendations.length > 0;
    document.getElementById("recommend-list").innerHTML = state.recommendations
      .map(recommendHtml)
      .join("");
  }
}

function onFriendListClick(event) {
  const button = event.target.closest("[data-action='open']");
  if (!button) return;
  openChat(button.dataset.sub);
}

async function openChat(sub) {
  const peer =
    state.friends.find((friend) => friend.sub === sub) ||
    state.searchResults.find((result) => result.sub === sub) ||
    null;
  if (!peer) return;
  state.activeSub = sub;
  state.activePeer = peer;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = true;
  document.getElementById("chat-active").hidden = false;
  document.getElementById("chat-peer").innerHTML = `
    ${avatarHtml(peer)}
    <span class="chat-peer-name">${escapeHtml(displayName(peer))}</span>`;
  document.getElementById("message-input").value = "";
  document.getElementById("load-older").hidden = true;
  renderMessages();
  document.getElementById("app").classList.add("chat-open");
  await loadHistory();
  await markReadActive();
  if (window.innerWidth >= 768) document.getElementById("message-input").focus();
}

async function markReadActive() {
  if (!state.activeSub || state.messages.length === 0) return;
  const last = state.messages[state.messages.length - 1];
  const response = await api(
    `/api/conversations/${encodeURIComponent(state.activeSub)}/read`,
    { method: "POST", body: JSON.stringify({ last_read_id: last.id }) }
  );
  if (response.ok) clearUnread(state.activeSub, last.id);
}

function clearUnread(sub, lastReadId) {
  const item = state.conversations.find((conversation) => conversation.peer.sub === sub);
  if (item) {
    item.unread_count = 0;
    item.last_read_id = lastReadId;
  }
  renderSidebar();
}

async function loadHistory(before) {
  if (state.loadingHistory) return;
  state.loadingHistory = true;
  let url = `/api/conversations/${encodeURIComponent(state.activeSub)}/messages?limit=50`;
  if (before) url += `&before=${before}`;
  try {
    const response = await api(url);
    if (!response.ok) return;
    const page = await response.json();
    state.nextBefore = page.next_before;
    if (before) {
      state.messages = page.messages.slice().reverse().concat(state.messages);
      renderMessages();
    } else {
      state.messages = page.messages.slice().reverse();
      renderMessages();
      const container = document.getElementById("messages");
      container.scrollTop = container.scrollHeight;
    }
    document.getElementById("load-older").hidden = !page.next_before;
  } finally {
    state.loadingHistory = false;
  }
}

function loadOlder() {
  loadHistory(state.nextBefore);
}

function closeChat() {
  state.activeSub = null;
  state.activePeer = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = false;
  document.getElementById("chat-active").hidden = true;
  document.getElementById("app").classList.remove("chat-open");
}

function messageHtml(message) {
  const own = message.sender_sub === state.me.sub;
  const readByPeer = state.readUpTo[state.activeSub];
  const read = own && typeof readByPeer === "number" && message.id <= readByPeer;
  const time = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `<div class="message ${own ? "message-own" : "message-other"}">
    <div class="message-bubble">${escapeHtml(message.content)}</div>
    <div class="message-meta">${escapeHtml(time)}${read
      ? '<span class="message-read">已读</span>'
      : ""}</div>
  </div>`;
}

function renderMessages() {
  const container = document.getElementById("messages");
  container.innerHTML = state.messages
    .slice()
    .sort((a, b) => a.id - b.id)
    .map(messageHtml)
    .join("");
}

function appendMessage(message) {
  if (state.messages.some((item) => item.id === message.id)) return;
  state.messages.push(message);
  const container = document.getElementById("messages");
  container.insertAdjacentHTML("beforeend", messageHtml(message));
  container.scrollTop = container.scrollHeight;
}

async function onComposerSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("message-input");
  const content = input.value.trim();
  if (!content || !state.activeSub) return;
  const response = await api(
    `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`,
    { method: "POST", body: JSON.stringify({ content }) }
  );
  if (response.ok) {
    input.value = "";
    input.focus();
  }
}

function onComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
}

function handleServerMessage(data) {
  if (data.type === "message" && data.message) {
    const message = data.message;
    const inActive =
      state.activeSub &&
      (message.sender_sub === state.activeSub || message.recipient_sub === state.activeSub);
    if (inActive) {
      appendMessage(message);
      if (message.sender_sub !== state.me.sub) markReadActive();
    } else {
      const peer =
        message.sender_sub === state.me.sub ? message.recipient_sub : message.sender_sub;
      const item = state.conversations.find((conversation) => conversation.peer.sub === peer);
      if (item) {
        item.last_message = message;
        if (message.sender_sub !== state.me.sub) item.unread_count += 1;
        renderSidebar();
      }
    }
  } else if (data.type === "read_receipt") {
    if (data.peer_sub === state.activeSub) {
      state.readUpTo[data.by_sub] = data.last_read_id;
      renderMessages();
    }
  } else if (data.type === "friend_event") {
    refreshSidebar();
  }
}

function logout() {
  state.loggingOut = true;
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
  if (state.pingTimer) {
    window.clearInterval(state.pingTimer);
    state.pingTimer = null;
  }
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${window.location.host}/ws`);
  state.ws = socket;

  function setStatus(kind, text) {
    const dot = document.getElementById("ws-dot");
    const label = document.getElementById("ws-text");
    if (dot) dot.className = `status-dot status-${kind}`;
    if (label) label.textContent = text;
  }

  socket.addEventListener("open", () => setStatus("connected", "已连接"));
  socket.addEventListener("error", () => setStatus("disconnected", "连接已断开"));
  socket.addEventListener("message", (event) => {
    try {
      handleServerMessage(JSON.parse(event.data));
    } catch {
      /* 忽略无法解析的帧 */
    }
  });
  socket.addEventListener("close", (event) => {
    if (event.code === 4401) {
      if (state.loggingOut) {
        setStatus("disconnected", "已退出登录");
        return;
      }
      setStatus("invalid", "已退出登录，正在返回登录页…");
      window.location.href = "/";
      return;
    }
    setStatus("disconnected", "连接已断开");
  });

  state.pingTimer = window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  if (state.pingTimer) {
    window.clearInterval(state.pingTimer);
    state.pingTimer = null;
  }
  state.friends = [];
  state.requests = { incoming: [], outgoing: [] };
  state.recommendations = [];
  state.searchResults = [];
  state.conversations = [];
  state.readUpTo = {};
  state.messages = [];
  state.activeSub = null;
  state.activePeer = null;
  state.nextBefore = null;
  loadMe();
});

loadMe();
