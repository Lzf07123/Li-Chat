"use strict";

const QUICK_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🙏"];

const state = {
  me: null,
  ws: null,
  pingTimer: null,
  loggingOut: false,
  friends: [],
  requests: { incoming: [], outgoing: [] },
  recommendations: [],
  searchResults: [],
  messageHits: [],
  searchKind: "contacts",
  searchNextBefore: null,
  searchQuery: "",
  conversations: [],
  readUpTo: {},
  typingTimer: null,
  typingSent: false,
  lastTypingAt: 0,
  activeSub: null,
  activePeer: null,
  editingId: null,
  pickerMessageId: null,
  groups: [],
  activeGroupId: null,
  activeGroup: null,
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
        <div class="search-modes" role="group" aria-label="搜索类型">
          <button class="search-mode search-mode-active" type="button"
            data-kind="contacts">用户</button>
          <button class="search-mode" type="button" data-kind="messages">消息</button>
        </div>
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
      <section class="sidebar-section">
        <h2 class="sidebar-title">群聊
          <button id="group-create" class="icon-btn refresh-btn" type="button"
            aria-label="新建群聊">＋</button>
        </h2>
        <p id="groups-empty" class="sidebar-empty">还没有群聊</p>
        <ul id="groups-list" class="contact-list"></ul>
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
          <button id="attach-btn" class="icon-btn" type="button" aria-label="发送附件">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
            </svg>
          </button>
          <input id="attach-input" type="file" hidden
            accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain" />
          <label class="sr-only" for="message-input">消息内容</label>
          <textarea id="message-input" class="input" rows="1" maxlength="2000"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"></textarea>
          <button class="btn btn-primary" type="submit">发送</button>
        </form>
      </div>
      <div id="group-panel" class="group-panel" hidden></div>
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
  document.getElementById("search-form").addEventListener("click", onSearchModeClick);
  document.getElementById("search-results").addEventListener("click", onSearchResultClick);
  document.getElementById("requests-list").addEventListener("click", onRequestListClick);
  document.getElementById("recommend-list").addEventListener("click", onRecommendListClick);
  document.getElementById("recommend-refresh").addEventListener("click", loadRecommendations);
  document.getElementById("friends-list").addEventListener("click", onFriendListClick);
  document.getElementById("groups-list").addEventListener("click", onGroupListClick);
  document.getElementById("group-create").addEventListener("click", openGroupCreateModal);
  document.getElementById("composer").addEventListener("submit", onComposerSubmit);
  document.getElementById("message-input").addEventListener("keydown", onComposerKeydown);
  document.getElementById("message-input").addEventListener("input", onComposerInput);
  document.getElementById("message-input").addEventListener("blur", onComposerBlur);
  document.getElementById("attach-btn").addEventListener("click", () => {
    document.getElementById("attach-input").click();
  });
  document.getElementById("attach-input").addEventListener("change", (event) => {
    onAttachSelected(event, false);
  });
  document.getElementById("messages").addEventListener("click", onMessagesClick);
  document.getElementById("load-older").addEventListener("click", loadOlder);
  document.getElementById("chat-back").addEventListener("click", closeChat);
  document.getElementById("group-panel").addEventListener("click", onGroupPanelClick);
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
    const [friendsRes, requestsRes, recommendRes, conversationsRes, groupsRes] = await Promise.all([
      api("/api/friends"),
      api("/api/friends/requests"),
      api("/api/friends/recommendations"),
      api("/api/conversations"),
      api("/api/groups"),
    ]);
    if (friendsRes.ok) state.friends = (await friendsRes.json()).friends;
    if (requestsRes.ok) state.requests = await requestsRes.json();
    if (recommendRes.ok) {
      state.recommendations = (await recommendRes.json()).friends;
    }
    if (conversationsRes.ok) {
      state.conversations = (await conversationsRes.json()).conversations;
    }
    if (groupsRes.ok) state.groups = (await groupsRes.json()).groups;
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
  const summaries = new Map(state.conversations.map((item) => [item.peer.sub, item]));
  const friendsById = new Map(state.friends.map((friend) => [friend.sub, friend]));
  const orderedSubs = [
    ...state.conversations.map((item) => item.peer.sub),
    ...state.friends.map((friend) => friend.sub),
  ];
  const friends = [...new Set(orderedSubs)]
    .map((sub) => friendsById.get(sub))
    .filter(Boolean);
  document.getElementById("friends-empty").hidden = friends.length > 0;
  document.getElementById("friends-list").innerHTML = friends
    .map((friend) => friendHtml(friend, summaries.get(friend.sub)))
    .join("");
  document.getElementById("groups-empty").hidden = state.groups.length > 0;
  const groupSummaries = new Map(
    state.conversations
      .filter((item) => item.group)
      .map((item) => [item.group.id, item])
  );
  document.getElementById("groups-list").innerHTML = state.groups
    .map((group) => groupHtml(group, groupSummaries.get(group.id)))
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
    ? summary.last_message.deleted
      ? "消息已撤回"
      : summary.last_message.content_type === "image"
        ? "[图片]"
        : summary.last_message.content_type === "file"
          ? "[文件]"
          : summary.last_message.content
    : "";
  const online = friend.online === true;
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open" data-sub="${escapeHtml(friend.sub)}">
      ${avatarHtml(friend)}
      <span class="contact-main">
        <span class="contact-name">
          <span class="presence-dot${online ? " presence-online" : ""}" aria-hidden="true"></span>
          ${escapeHtml(displayName(friend))}
        </span>
        ${preview ? `<span class="contact-preview">${escapeHtml(preview)}</span>` : ""}
      </span>
      ${unread > 0
        ? `<span class="badge badge-unread" data-role="unread" data-sub="${escapeHtml(friend.sub)}">${unread}</span>`
        : ""}
    </button>
  </li>`;
}

function groupHtml(group, summary) {
  const count = group.members ? group.members.length : 0;
  const unread = summary ? summary.unread_count : 0;
  const preview = summary && summary.last_message
    ? summary.last_message.deleted
      ? "消息已撤回"
      : summary.last_message.content_type === "image"
        ? "[图片]"
        : summary.last_message.content_type === "file"
          ? "[文件]"
          : summary.last_message.content
    : "";
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open-group" data-id="${group.id}">
      <div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>
      <span class="contact-main">
        <span class="contact-name">${escapeHtml(group.name)}</span>
        <span class="contact-preview">${preview || `${count} 位成员`}</span>
      </span>
      ${unread > 0
        ? `<span class="badge badge-unread" data-role="unread" data-id="${group.id}">${unread}</span>`
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

function messageHitHtml(hit) {
  const label =
    hit.conversation.type === "group"
      ? hit.conversation.group_name
      : hit.conversation.peer_name;
  const target =
    hit.conversation.type === "group"
      ? `data-action="open-group-hit" data-group="${hit.conversation.group_id}"`
      : `data-action="open-dm-hit" data-peer="${escapeHtml(hit.conversation.peer_sub)}"`;
  return `<li class="contact-item search-item search-hit">
    <button class="contact-button" type="button" ${target}>
      <span class="contact-main">
        <span class="contact-name">${escapeHtml(label || "")}</span>
        <span class="contact-preview">${escapeHtml(hit.snippet)}</span>
      </span>
    </button>
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
  state.searchQuery = query;
  if (state.searchKind === "messages") {
    state.searchNextBefore = null;
    await searchMessages(query, false);
    return;
  }
  const response = await api(`/api/search?kind=contacts&q=${encodeURIComponent(query)}`);
  if (!response.ok) return;
  state.searchResults = (await response.json()).contacts;
  renderSearchResults();
}

async function searchMessages(query, append) {
  let url = `/api/search?kind=messages&q=${encodeURIComponent(query)}`;
  if (append && state.searchNextBefore) url += `&before=${state.searchNextBefore}`;
  const response = await api(url);
  if (!response.ok) return;
  const body = await response.json();
  if (!append) state.messageHits = [];
  state.messageHits = state.messageHits.concat(body.messages);
  state.searchNextBefore = body.next_before;
  renderSearchResults();
}

function renderSearchResults() {
  const results = document.getElementById("search-results");
  const hasResults =
    state.searchKind === "messages"
      ? state.messageHits.length > 0
      : state.searchResults.length > 0;
  results.hidden = !hasResults;
  const more = state.searchKind === "messages" && state.searchNextBefore
    ? `<li class="contact-item search-item"><button class="btn btn-ghost btn-sm"
        type="button" data-action="search-more">加载更多</button></li>`
    : "";
  results.innerHTML =
    (state.searchKind === "messages"
      ? state.messageHits.map(messageHitHtml).join("")
      : state.searchResults.map(searchResultHtml).join("")) + more;
}

function onSearchModeClick(event) {
  const button = event.target.closest(".search-mode[data-kind]");
  if (!button) return;
  state.searchKind = button.dataset.kind;
  document.querySelectorAll(".search-mode").forEach((item) => {
    item.classList.toggle("search-mode-active", item === button);
  });
  const input = document.getElementById("search-input");
  input.placeholder = state.searchKind === "messages" ? "搜索聊天记录" : "按昵称或邮箱搜索";
  input.focus();
}

async function onSearchResultClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  if (button.dataset.action === "search-more") {
    await searchMessages(state.searchQuery, true);
    return;
  }
  if (button.dataset.action === "open-dm-hit") {
    openChat(button.dataset.peer);
    return;
  }
  if (button.dataset.action === "open-group-hit") {
    openGroup(Number(button.dataset.group));
    return;
  }
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

function onGroupListClick(event) {
  const button = event.target.closest("[data-action='open-group']");
  if (!button) return;
  openGroup(Number(button.dataset.id));
}

async function openGroup(groupId) {
  const response = await api(`/api/groups/${groupId}`);
  if (!response.ok) return;
  state.activeGroupId = groupId;
  state.activeGroup = await response.json();
  state.activeSub = null;
  state.activePeer = null;
  state.editingId = null;
  state.pickerMessageId = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = true;
  document.getElementById("chat-active").hidden = true;
  document.getElementById("group-panel").hidden = false;
  renderGroupPanel();
  document.getElementById("app").classList.add("chat-open");
  await loadGroupHistory();
  await markGroupRead();
}

function closeGroupPanel() {
  state.activeGroupId = null;
  state.activeGroup = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = false;
  document.getElementById("group-panel").hidden = true;
  document.getElementById("app").classList.remove("chat-open");
}

function roleLabel(role) {
  if (role === "owner") return "群主";
  if (role === "admin") return "管理员";
  return "成员";
}

function groupPanelHtml(group) {
  const me = state.me.sub;
  const myRole = (group.members.find((member) => member.user.sub === me) || {}).role;
  const members = group.members
    .map((member) => {
      const isMe = member.user.sub === me;
      const canRemove =
        (myRole === "owner" || myRole === "admin") &&
        member.role !== "owner" &&
        !isMe &&
        !(myRole === "admin" && member.role === "admin");
      const ownerActions =
        myRole === "owner" && !isMe
          ? `<button class="btn btn-ghost btn-sm" type="button"
              data-action="group-toggle-admin" data-sub="${escapeHtml(member.user.sub)}"
              data-role="${member.role}">${member.role === "admin" ? "取消管理员" : "设为管理员"}</button>
             <button class="btn btn-ghost btn-sm" type="button"
              data-action="group-transfer" data-sub="${escapeHtml(member.user.sub)}">转让</button>`
          : "";
      const remove = canRemove
        ? `<button class="btn btn-ghost btn-sm" type="button"
            data-action="group-remove" data-sub="${escapeHtml(member.user.sub)}">移除</button>`
        : "";
      return `<li class="contact-item group-member">
        ${avatarHtml(member.user)}
        <span class="contact-main">
          <span class="contact-name">${escapeHtml(displayName(member.user))}</span>
          <span class="contact-preview">${roleLabel(member.role)}${isMe ? "（我）" : ""}</span>
        </span>
        <span class="contact-actions">${ownerActions}${remove}</span>
      </li>`;
    })
    .join("");
  const candidates = state.friends.filter(
    (friend) => !group.members.some((member) => member.user.sub === friend.sub)
  );
  const inviteOptions = candidates
    .map(
      (friend) =>
        `<option value="${escapeHtml(friend.sub)}">${escapeHtml(displayName(friend))}</option>`
    )
    .join("");
  const manager = myRole === "owner" || myRole === "admin";
  return `<header class="chat-header">
      <button id="group-back" class="icon-btn chat-back" type="button" aria-label="返回列表">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M15 18l-6-6 6-6"/>
        </svg>
      </button>
      <div class="chat-peer">
        <div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>
        <span class="chat-peer-main">
          <span class="chat-peer-name">${escapeHtml(group.name)}</span>
          <span class="chat-peer-status">${group.members.length} 位成员</span>
        </span>
      </div>
    </header>
    <div class="group-chat">
      <button id="group-load-older" class="btn btn-ghost btn-sm load-older" type="button"
        hidden>加载更早消息</button>
      <div id="group-messages" class="messages" role="log" aria-live="polite"
        aria-label="群聊记录"></div>
      <form id="group-composer" class="composer">
        <button id="group-attach-btn" class="icon-btn" type="button" aria-label="发送附件">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>
        <input id="group-attach-input" type="file" hidden
          accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain" />
        <label class="sr-only" for="group-message-input">消息内容</label>
        <textarea id="group-message-input" class="input" rows="1" maxlength="2000"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"></textarea>
        <button class="btn btn-primary" type="submit">发送</button>
      </form>
    </div>
    <div class="group-panel-body">
      <section class="group-section">
        <h3 class="group-section-title">成员</h3>
        <ul class="contact-list">${members}</ul>
      </section>
      ${manager
        ? `<section class="group-section">
            <h3 class="group-section-title">管理</h3>
            <div class="group-actions">
              <div class="group-rename-row">
                <input id="group-rename-input" class="input" maxlength="64"
                  placeholder="新群名称" value="${escapeHtml(group.name)}" />
                <button class="btn btn-secondary btn-sm" type="button"
                  data-action="group-rename">改名</button>
              </div>
              <div class="group-rename-row">
                <select id="group-invite-select" class="input">
                  ${inviteOptions || `<option value="">没有可邀请的好友</option>`}
                </select>
                <button class="btn btn-secondary btn-sm" type="button"
                  data-action="group-invite" ${candidates.length ? "" : "disabled"}>邀请</button>
              </div>
            </div>
          </section>`
        : ""}
      <section class="group-section">
        <button class="btn btn-ghost" type="button" data-action="group-leave">退出群聊</button>
      </section>
    </div>`;
}

function renderGroupPanel() {
  const panel = document.getElementById("group-panel");
  panel.innerHTML = groupPanelHtml(state.activeGroup);
  const back = document.getElementById("group-back");
  if (back) back.addEventListener("click", closeGroupPanel);
  const loadOlder = document.getElementById("group-load-older");
  if (loadOlder) {
    loadOlder.addEventListener("click", () => loadGroupHistory(state.nextBefore));
  }
  const composer = document.getElementById("group-composer");
  if (composer) {
    composer.addEventListener("submit", onGroupComposerSubmit);
    document.getElementById("group-message-input").addEventListener(
      "keydown",
      onGroupComposerKeydown
    );
    document.getElementById("group-attach-btn").addEventListener("click", () => {
      document.getElementById("group-attach-input").click();
    });
    document.getElementById("group-attach-input").addEventListener("change", (event) => {
      onAttachSelected(event, true);
    });
  }
}

async function onAttachSelected(event, isGroup) {
  const input = event.target;
  const file = input.files && input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const uploadResponse = await api("/api/uploads", { method: "POST", body: form });
  input.value = "";
  if (!uploadResponse.ok) return;
  const upload = await uploadResponse.json();
  const content_type = upload.mime.startsWith("image/") ? "image" : "file";
  const url = isGroup
    ? `/api/groups/${state.activeGroupId}/messages`
    : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`;
  await api(url, {
    method: "POST",
    body: JSON.stringify({
      content: "",
      content_type,
      attachment: { url: upload.url },
    }),
  });
}

async function refreshGroups() {
  const response = await api("/api/groups");
  if (!response.ok) return;
  state.groups = (await response.json()).groups;
  renderSidebar();
  if (state.activeGroupId !== null) {
    const detail = await api(`/api/groups/${state.activeGroupId}`);
    if (detail.ok) {
      state.activeGroup = await detail.json();
      renderGroupPanel();
    } else {
      closeGroupPanel();
    }
  }
}

function openGroupCreateModal() {
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="group-create-modal" role="dialog" aria-modal="true">
      <form id="group-create-form" class="modal-card">
        <h3 class="modal-title">新建群聊</h3>
        <label class="sr-only" for="group-name-input">群名称</label>
        <input id="group-name-input" class="input" maxlength="64"
          placeholder="群名称（1–64 字）" required />
        <div class="group-pick-list" id="group-pick-list">${
          state.friends.length
            ? state.friends
                .map(
                  (friend) => `<label class="group-pick">
                    <input type="checkbox" value="${escapeHtml(friend.sub)}" />
                    <span>${escapeHtml(displayName(friend))}</span>
                  </label>`
                )
                .join("")
            : `<p class="muted">还没有好友，先添加好友再建群</p>`
        }</div>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-group-create">取消</button>
          <button class="btn btn-primary" type="submit">创建</button>
        </div>
      </form>
    </div>`
  );
  const modal = document.getElementById("group-create-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-group-create']")) {
      modal.remove();
    }
  });
  document.getElementById("group-create-form").addEventListener("submit", onCreateGroupSubmit);
  document.getElementById("group-name-input").focus();
}

async function onCreateGroupSubmit(event) {
  event.preventDefault();
  const name = document.getElementById("group-name-input").value.trim();
  const memberSubs = [...document.querySelectorAll("#group-pick-list input:checked")].map(
    (input) => input.value
  );
  const response = await api("/api/groups", {
    method: "POST",
    body: JSON.stringify({ name, member_subs: memberSubs }),
  });
  if (response.ok) {
    const group = await response.json();
    document.getElementById("group-create-modal").remove();
    await refreshGroups();
    openGroup(group.id);
  }
}

async function onGroupPanelClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const groupId = state.activeGroupId;
  if (groupId === null) return;
  const action = button.dataset.action;
  if (action === "group-rename") {
    const name = document.getElementById("group-rename-input").value.trim();
    if (!name) return;
    await api(`/api/groups/${groupId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
  } else if (action === "group-invite") {
    const sub = document.getElementById("group-invite-select").value;
    if (!sub) return;
    await api(`/api/groups/${groupId}/members`, {
      method: "POST",
      body: JSON.stringify({ member_subs: [sub] }),
    });
  } else if (action === "group-remove") {
    await api(`/api/groups/${groupId}/members/${encodeURIComponent(button.dataset.sub)}`, {
      method: "DELETE",
    });
  } else if (action === "group-toggle-admin") {
    await api(`/api/groups/${groupId}/members/${encodeURIComponent(button.dataset.sub)}`, {
      method: "PATCH",
      body: JSON.stringify({ role: button.dataset.role === "admin" ? "member" : "admin" }),
    });
  } else if (action === "group-transfer") {
    await api(`/api/groups/${groupId}/transfer`, {
      method: "POST",
      body: JSON.stringify({ new_owner_sub: button.dataset.sub }),
    });
  } else if (action === "group-leave") {
    const response = await api(`/api/groups/${groupId}/leave`, { method: "POST" });
    if (response.ok) {
      closeGroupPanel();
      await refreshGroups();
      return;
    }
  }
  await refreshGroups();
}

async function openChat(sub) {
  const peer =
    state.friends.find((friend) => friend.sub === sub) ||
    state.searchResults.find((result) => result.sub === sub) ||
    null;
  if (!peer) return;
  state.activeGroupId = null;
  state.activeGroup = null;
  state.activeSub = sub;
  state.activePeer = peer;
  state.editingId = null;
  state.pickerMessageId = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = true;
  document.getElementById("chat-active").hidden = false;
  document.getElementById("group-panel").hidden = true;
  document.getElementById("chat-peer").innerHTML = `
    ${avatarHtml(peer)}
    <span class="chat-peer-main">
      <span class="chat-peer-name">${escapeHtml(displayName(peer))}</span>
      <span class="chat-peer-status" id="chat-peer-status">${
        peer.online ? "在线" : "离线"
      }</span>
    </span>
    <span id="typing-hint" class="typing-hint" hidden>正在输入…</span>`;
  clearTypingHint();
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
  sendTyping("stop");
  state.editingId = null;
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
  let body;
  if (message.deleted) {
    body = '<div class="message-bubble message-bubble-deleted">消息已撤回</div>';
  } else if (message.content_type === "image" && message.attachment) {
    body = `<div class="message-bubble message-bubble-attachment">
      <img class="attachment-image" src="${escapeHtml(message.attachment.url)}"
        alt="图片消息" loading="lazy" />
      ${message.content
        ? `<div class="attachment-caption">${escapeHtml(message.content)}</div>`
        : ""}
    </div>`;
  } else if (message.attachment) {
    body = `<div class="message-bubble message-bubble-attachment">
      <a class="attachment-link" href="${escapeHtml(message.attachment.url)}" download>
        📎 ${escapeHtml(message.attachment.name)}</a>
      ${message.content
        ? `<div class="attachment-caption">${escapeHtml(message.content)}</div>`
        : ""}
    </div>`;
  } else {
    body = `<div class="message-bubble">${escapeHtml(message.content)}</div>`;
  }
  const actions = own && !message.deleted && !state.activeGroupId
    ? `<span class="message-actions">
        <button class="message-action" type="button"
          data-action="edit" data-id="${message.id}">编辑</button>
        <button class="message-action" type="button"
          data-action="withdraw" data-id="${message.id}">撤回</button>
      </span>`
    : "";
  const editedMark = !message.deleted && message.edited_at
    ? '<span class="message-read">已编辑</span>'
    : "";
  const reactions = message.deleted || state.activeGroupId ? "" : reactionsHtml(message);
  return `<div class="message ${own ? "message-own" : "message-other"}">
    ${body}
    <div class="message-meta">${escapeHtml(time)}${read
      ? '<span class="message-read">已读</span>'
      : ""}${editedMark}${actions}</div>
    ${reactions}
  </div>`;
}

function reactionsHtml(message) {
  const reactions = message.reactions || [];
  const mine = message.my_reactions || [];
  const chips = reactions
    .map((reaction) => {
      const active = mine.includes(reaction.emoji) ? " reaction-chip-active" : "";
      return `<button class="reaction-chip${active}" type="button"
        data-action="react" data-emoji="${escapeHtml(reaction.emoji)}"
        data-id="${message.id}">${escapeHtml(reaction.emoji)} ${reaction.count}</button>`;
    })
    .join("");
  const picker = state.pickerMessageId === message.id
    ? `<span class="reaction-picker">${QUICK_EMOJIS.map(
        (emoji) => `<button class="reaction-option" type="button"
          data-action="react-emoji" data-emoji="${emoji}" data-id="${message.id}">${emoji}</button>`
      ).join("")}</span>`
    : "";
  return `<div class="reactions-row">${chips}
    <button class="reaction-add" type="button" data-action="react-picker"
      data-id="${message.id}" aria-label="添加回应">+</button>${picker}</div>`;
}

function renderMessages() {
  const container = messagesContainer();
  if (!container) return;
  container.innerHTML = state.messages
    .slice()
    .sort((a, b) => a.id - b.id)
    .map(messageHtml)
    .join("");
}

function appendMessage(message) {
  if (state.messages.some((item) => item.id === message.id)) return;
  state.messages.push(message);
  const container = messagesContainer();
  if (!container) return;
  container.insertAdjacentHTML("beforeend", messageHtml(message));
  container.scrollTop = container.scrollHeight;
}

function messagesContainer() {
  return document.getElementById(
    state.activeGroupId ? "group-messages" : "messages"
  );
}

async function loadGroupHistory(before) {
  if (state.loadingHistory || state.activeGroupId === null) return;
  state.loadingHistory = true;
  let url = `/api/groups/${state.activeGroupId}/messages?limit=50`;
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
      const container = messagesContainer();
      if (container) container.scrollTop = container.scrollHeight;
    }
    const loadOlder = document.getElementById("group-load-older");
    if (loadOlder) loadOlder.hidden = !page.next_before;
  } finally {
    state.loadingHistory = false;
  }
}

async function markGroupRead() {
  if (!state.activeGroupId || state.messages.length === 0) return;
  const last = state.messages[state.messages.length - 1];
  const response = await api(`/api/groups/${state.activeGroupId}/read`, {
    method: "POST",
    body: JSON.stringify({ last_read_id: last.id }),
  });
  if (response.ok) clearGroupUnread(state.activeGroupId, last.id);
}

function clearGroupUnread(groupId, lastReadId) {
  const item = state.conversations.find(
    (conversation) => conversation.group && conversation.group.id === groupId
  );
  if (item) {
    item.unread_count = 0;
    item.last_read_id = lastReadId;
  }
  renderSidebar();
}

async function onGroupComposerSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("group-message-input");
  const content = input.value.trim();
  if (!content || !state.activeGroupId) return;
  const response = await api(`/api/groups/${state.activeGroupId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
  if (response.ok) {
    input.value = "";
    input.focus();
  }
}

function onGroupComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("group-composer").requestSubmit();
  }
}

function updatePeerStatus(sub, online) {
  const friend = state.friends.find((item) => item.sub === sub);
  if (friend) friend.online = online;
  if (sub === state.activeSub) {
    const status = document.getElementById("chat-peer-status");
    if (status) status.textContent = online ? "在线" : "离线";
  }
}

function showTypingHint() {
  if (!state.activeSub) return;
  const hint = document.getElementById("typing-hint");
  if (hint) hint.hidden = false;
  if (state.typingTimer) window.clearTimeout(state.typingTimer);
  state.typingTimer = window.setTimeout(clearTypingHint, 2500);
}

function clearTypingHint() {
  if (state.typingTimer) {
    window.clearTimeout(state.typingTimer);
    state.typingTimer = null;
  }
  const hint = document.getElementById("typing-hint");
  if (hint) hint.hidden = true;
}

function sendTyping(action) {
  const socket = state.ws;
  if (!socket || socket.readyState !== WebSocket.OPEN || !state.activeSub) return;
  if (action === "start") {
    const now = Date.now();
    if (now - state.lastTypingAt < 1500) return;
    state.lastTypingAt = now;
    state.typingSent = true;
  } else if (!state.typingSent) {
    return;
  } else {
    state.typingSent = false;
  }
  socket.send(JSON.stringify({ type: "typing", to: state.activeSub, action }));
}

async function onComposerSubmit(event) {
  event.preventDefault();
  sendTyping("stop");
  const input = document.getElementById("message-input");
  const content = input.value.trim();
  if (!content || !state.activeSub) return;
  const editingId = state.editingId;
  const url = editingId
    ? `/api/conversations/${encodeURIComponent(state.activeSub)}/messages/${editingId}`
    : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`;
  const response = await api(url, {
    method: editingId ? "PATCH" : "POST",
    body: JSON.stringify({ content }),
  });
  if (response.ok) {
    state.editingId = null;
    input.value = "";
    input.placeholder = "输入消息，Enter 发送，Shift+Enter 换行";
    input.focus();
  }
}

async function onMessagesClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const messageId = button.dataset.id;
  const sub = state.activeSub;
  if (!sub) return;
  if (button.dataset.action === "react-picker") {
    const numericId = Number(messageId);
    state.pickerMessageId = state.pickerMessageId === numericId ? null : numericId;
    renderMessages();
    return;
  }
  if (button.dataset.action === "react" || button.dataset.action === "react-emoji") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (!message) return;
    const emoji = button.dataset.emoji;
    const mine = (message.my_reactions || []).includes(emoji);
    const url = `/api/conversations/${encodeURIComponent(sub)}/messages/${messageId}/reactions`;
    await api(url, {
      method: mine ? "DELETE" : "PUT",
      body: mine ? undefined : JSON.stringify({ emoji }),
    });
    state.pickerMessageId = null;
    return;
  }
  if (button.dataset.action !== "edit" && button.dataset.action !== "withdraw") return;
  if (button.dataset.action === "edit") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (!message || message.deleted) return;
    state.editingId = message.id;
    const input = document.getElementById("message-input");
    input.value = message.content;
    input.placeholder = "正在编辑消息，Enter 保存，Esc 取消";
    input.focus();
    return;
  }
  const response = await api(
    `/api/conversations/${encodeURIComponent(sub)}/messages/${messageId}`,
    { method: "DELETE" }
  );
  if (!response.ok && response.status === 409) {
    await loadHistory();
  }
}

function onComposerKeydown(event) {
  if (event.key === "Escape" && state.editingId) {
    cancelEditing();
    return;
  }
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
}

function cancelEditing() {
  state.editingId = null;
  const input = document.getElementById("message-input");
  input.value = "";
  input.placeholder = "输入消息，Enter 发送，Shift+Enter 换行";
}

function onComposerInput() {
  sendTyping("start");
}

function onComposerBlur() {
  sendTyping("stop");
}

function handleServerMessage(data) {
  if (data.type === "message" && data.message) {
    const message = data.message;
    const inActiveGroup =
      state.activeGroupId !== null && message.group_id === state.activeGroupId;
    const inActiveDm =
      Boolean(state.activeSub) &&
      (message.sender_sub === state.activeSub || message.recipient_sub === state.activeSub);
    if (inActiveGroup) {
      appendMessage(message);
      if (message.sender_sub !== state.me.sub) markGroupRead();
    } else if (inActiveDm) {
      appendMessage(message);
      if (message.sender_sub !== state.me.sub) markReadActive();
    } else if (message.group_id != null) {
      const item = state.conversations.find(
        (conversation) =>
          conversation.group && conversation.group.id === message.group_id
      );
      if (item) {
        item.last_message = message;
        if (message.sender_sub !== state.me.sub) item.unread_count += 1;
        renderSidebar();
      }
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
  } else if (data.type === "presence" && data.sub) {
    updatePeerStatus(data.sub, data.online === true);
    renderSidebar();
  } else if (data.type === "typing" && data.from === state.activeSub) {
    showTypingHint();
  } else if (data.type === "message_edited" && data.message) {
    replaceMessage(data.message);
  } else if (data.type === "message_deleted" && data.message) {
    replaceMessage(data.message);
  } else if (data.type === "message_reaction") {
    applyReaction(data);
  } else if (data.type === "group_event") {
    refreshGroups();
  } else if (data.type === "friend_event") {
    refreshSidebar();
  }
}

function applyReaction(event) {
  const message = state.messages.find((item) => item.id === event.message_id);
  if (!message) return;
  message.reactions = message.reactions || [];
  message.my_reactions = message.my_reactions || [];
  const index = message.reactions.findIndex(
    (reaction) => reaction.emoji === event.emoji
  );
  if (event.action === "added") {
    if (index >= 0) {
      message.reactions[index].count = event.count;
    } else {
      message.reactions.push({ emoji: event.emoji, count: event.count });
    }
    if (
      event.by_sub === state.me.sub &&
      !message.my_reactions.includes(event.emoji)
    ) {
      message.my_reactions.push(event.emoji);
    }
  } else if (index >= 0) {
    if (event.count > 0) {
      message.reactions[index].count = event.count;
    } else {
      message.reactions.splice(index, 1);
    }
    if (event.by_sub === state.me.sub) {
      message.my_reactions = message.my_reactions.filter(
        (emoji) => emoji !== event.emoji
      );
    }
  }
  renderMessages();
}

function replaceMessage(message) {
  const index = state.messages.findIndex((item) => item.id === message.id);
  if (index >= 0) {
    state.messages[index] = message;
  } else {
    state.messages.push(message);
  }
  renderMessages();
  const item = state.conversations.find(
    (conversation) => conversation.peer.sub === state.activeSub
  );
  if (item && item.last_message && item.last_message.id === message.id) {
    item.last_message = message;
    renderSidebar();
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
  state.typingSent = false;
  state.lastTypingAt = 0;
  state.typingTimer = null;
  state.messages = [];
  state.activeSub = null;
  state.activePeer = null;
  state.editingId = null;
  state.pickerMessageId = null;
  state.groups = [];
  state.activeGroupId = null;
  state.activeGroup = null;
  state.nextBefore = null;
  loadMe();
});

loadMe();
