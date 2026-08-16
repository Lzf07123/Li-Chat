"use strict";

const QUICK_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
const EMOJI_SETS = {
  常用: [
    ...QUICK_EMOJIS,
    "😀", "😁", "😆", "🤣", "😊", "😇", "🥰", "😍", "🤩", "😘", "😋", "😛", "🤪", "🤨",
    "🧐", "🤓", "😎", "🥳", "😏", "😒", "😞", "😔", "😕", "🙁", "😣", "😖", "😫", "😩",
    "🥺", "😢", "😭", "😤", "😠", "😡", "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰", "😥",
    "🤗", "🤔", "🤭", "🤫", "🤥", "😶", "😐", "😑", "😬", "🙄", "😯", "😦", "😧", "😮",
    "😲", "🥱", "😴", "🤤", "😪", "😵", "🥴", "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤑",
    "🤠", "😈", "👿", "🤡", "💩", "👻", "💀", "👽", "👾", "🤖", "🎃", "😺", "😸", "😹",
    "😻", "😼", "😽", "🙀", "😿", "😾",
  ],
  手势: [
    "👋", "🤚", "🖐️", "✋", "🖖", "👌", "🤌", "🤏", "✌️", "🤞", "🫰", "🤟", "🤘", "🤙",
    "👈", "👉", "👆", "👇", "☝️", "👍", "👎", "✊", "👊", "🤛", "🤜", "👏", "🙌", "👐",
    "🤲", "🤝", "🙏", "✍️", "💪", "🦾", "🖕",
  ],
  符号: [
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞", "💓",
    "💗", "💖", "💘", "💝", "💟", "☮️", "✝️", "☪️", "🕉️", "☸️", "✡️", "🔯", "🕎", "☯️",
    "☦️", "🛐", "♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓", "⚛️",
    "✅", "❌", "❓", "❗", "💯", "🔥", "⭐", "🌟", "✨", "⚡", "💧", "🎉", "🎊", "🎁",
  ],
};
// 与 app/main.py 的 FRONTEND_VERSION 保持一致；落后即清缓存强制刷新
const FRONTEND_VERSION = "0.3.0";
const RENDER_CHUNK_SIZE = 40;
let draftTimer = null;
let localSeq = 0;

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
  convFilter: "",
  sidebarLoading: true,
  sidebarError: false,
  conversations: [],
  archivedConversations: [],
  readUpTo: {},
  typingTimer: null,
  typingSent: false,
  lastTypingAt: 0,
  activeSub: null,
  activePeer: null,
  editingId: null,
  pickerMessageId: null,
  replyTo: null,
  forwardMessageIds: [],
  selectMode: false,
  selectedIds: [],
  mentionSubs: [],
  mentionOpen: false,
  recording: { active: false, recorder: null, isGroup: false, seconds: 0, timer: null },
  emojiOpen: false,
  wsRetry: 0,
  wsReconnectTimer: null,
  wsReconnecting: false,
  uploadCancel: null,
  uploadRetry: null,
  groups: [],
  activeGroupId: null,
  activeGroup: null,
  groupFiles: [],
  groupFilesNext: null,
  groupReadBy: {},
  messages: [],
  conversationEpoch: 0,
  notifications: [],
  notificationsUnread: 0,
  notificationsNext: null,
  call: null,
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

function toast(message, kind = "info", duration = null) {
  let region = document.getElementById("toast-region");
  if (!region) {
    region = document.createElement("div");
    region.id = "toast-region";
    region.className = "toast-region";
    region.setAttribute("aria-live", "polite");
    document.body.appendChild(region);
  }
  const item = document.createElement("div");
  item.className = `toast toast-${kind}`;
  item.setAttribute("role", "status");
  const text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = message;
  const close = document.createElement("button");
  close.className = "toast-close";
  close.type = "button";
  close.setAttribute("aria-label", "关闭提示");
  close.setAttribute("data-action", "toast-close");
  close.textContent = "×";
  item.appendChild(text);
  item.appendChild(close);
  const remove = () => {
    if (item.dataset.leaving) return;
    item.dataset.leaving = "1";
    item.classList.add("toast-leave");
    window.setTimeout(() => item.remove(), 180);
  };
  close.addEventListener("click", remove);
  item.addEventListener("click", (event) => {
    if (!event.target.closest("[data-action='toast-close']")) remove();
  });
  region.appendChild(item);
  const ttl = duration !== null ? duration : kind === "error" ? 5000 : 3000;
  window.setTimeout(remove, ttl);
  while (region.children.length > 5) {
    const oldest = region.firstElementChild;
    if (oldest) oldest.remove();
  }
  return item;
}

const ERROR_MESSAGES = {
  "request already pending": "已发送过申请，等待对方处理",
  "request already exists": "已发送过申请，等待对方处理",
  "already friends": "你们已经是好友",
  "cannot message yourself": "不能给自己发消息",
  "not friends": "对方还不是你的好友",
  "user not found": "用户不存在",
  "message must belong to the conversation": "消息不属于该会话",
  "edit window expired": "已超过可编辑时间",
  "cannot edit deleted message": "消息已撤回，无法编辑",
  "not a group member": "你已不在该群聊中",
  "group not found": "群聊不存在或已解散",
  "you are muted": "你已被禁言",
  "attachment must belong to you": "只能使用自己上传的附件",
  "file exceeds": "文件过大，超出大小限制",
  "unsupported file type": "不支持的文件类型",
};

function friendlyError(status, detail) {
  if (status >= 500) return "服务繁忙，请稍后重试";
  if (typeof detail === "string" && detail) {
    for (const [key, value] of Object.entries(ERROR_MESSAGES)) {
      if (detail.includes(key)) return value;
    }
    if (detail.startsWith("at most")) return "内容超过长度限制";
    if (detail.startsWith("file exceeds")) return "文件过大，超出大小限制";
  }
  if (status === 422) return "输入内容不符合要求";
  if (status === 403) return "没有权限执行该操作";
  if (status === 404) return "内容不存在或已被删除";
  if (status === 409) return "操作冲突，请刷新后重试";
  if (status === 429) return "操作太频繁，请稍后再试";
  return "操作失败，请稍后重试";
}

function dayLabel(iso) {
  const date = new Date(iso);
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const startOfDay = new Date(date);
  startOfDay.setHours(0, 0, 0, 0);
  const diffDays = Math.round((startOfToday - startOfDay) / 86400000);
  if (diffDays === 0) return "今天";
  if (diffDays === 1) return "昨天";
  const month = date.getMonth() + 1;
  const day = date.getDate();
  if (date.getFullYear() === startOfToday.getFullYear()) {
    return `${month}月${day}日`;
  }
  return `${date.getFullYear()}年${month}月${day}日`;
}

function relativeTime(iso) {
  const date = new Date(iso);
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const dayDiff = Math.floor(diff / 86400000);
  if (dayDiff === 1) return "昨天";
  const now = new Date();
  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1}月${date.getDate()}日`;
  }
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`;
}

function localMessage(content) {
  localSeq += 1;
  return {
    id: `local-${localSeq}`,
    sender_sub: state.me.sub,
    recipient_sub:
      state.activeGroupId !== null ? `group:${state.activeGroupId}` : state.activeSub,
    group_id: state.activeGroupId,
    conversation_type: state.activeGroupId !== null ? "group" : "dm",
    content,
    content_type: "text",
    created_at: new Date().toISOString(),
    status: "sending",
  };
}

function removeLocal(local) {
  state.messages = state.messages.filter((message) => message.id !== local.id);
  renderMessages();
}

function groupMemberMap() {
  const members = state.activeGroup && state.activeGroup.members
    ? state.activeGroup.members
    : [];
  return new Map(members.map((member) => [member.user.sub, member.user]));
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
  return user.remark || user.nickname || user.name || user.sub;
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
    toast("网络错误，请检查连接后重试", "error");
    throw new Error("网络错误，请稍后重试");
  }
  if (response.status === 401) {
    toast("登录已失效，正在返回登录页…", "error");
    window.location.href = "/";
    throw new Error("登录已失效");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = body && typeof body.detail === "string" ? body.detail : "";
    } catch {
      /* 非 JSON 错误体 */
    }
    toast(friendlyError(response.status, detail), "error");
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
  if (!localStorage.getItem("lichat-session-active")) {
    localStorage.setItem("lichat-session-active", "1");
    localStorage.setItem("lichat-login", String(Date.now()));
  }
  renderLoggedIn();
  connectWebSocket();
}

function ensureFreshFrontend() {
  const reloadedKey = "lichat-frontend-reloaded";
  fetch("/api/version", { credentials: "same-origin", cache: "no-store" })
    .then((response) => response.json())
    .then((data) => {
      if (data.frontend_version === FRONTEND_VERSION) {
        sessionStorage.removeItem(reloadedKey);
        return;
      }
      if (sessionStorage.getItem(reloadedKey) === "true") return;
      sessionStorage.setItem(reloadedKey, "true");
      if (window.caches && window.caches.keys) {
        window.caches
          .keys()
          .then((keys) => Promise.all(keys.map((key) => window.caches.delete(key))))
          .then(() => window.location.reload());
        return;
      }
      window.location.reload();
    })
    .catch(() => {
      /* 版本探测失败不阻塞使用 */
    });
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
      <button id="notify-bell" class="icon-btn notify-bell" type="button"
        aria-label="通知中心" aria-haspopup="dialog">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <span id="notify-badge" class="badge badge-primary notify-badge" hidden>0</span>
      </button>
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
          <button id="edit-profile" class="profile-menu-item" role="menuitem" type="button">
            编辑资料
          </button>
          <button id="open-stars" class="profile-menu-item" role="menuitem" type="button">
            我的收藏
          </button>
          <button id="open-sessions" class="profile-menu-item" role="menuitem" type="button">
            登录设备
          </button>
          <button id="open-calls" class="profile-menu-item" role="menuitem" type="button">
            通话记录
          </button>
          <button id="open-notify-settings" class="profile-menu-item" role="menuitem" type="button">
            通知设置
          </button>
          <button id="export-data" class="profile-menu-item" role="menuitem" type="button">
            导出数据
          </button>
          <button id="open-shortcuts" class="profile-menu-item" role="menuitem" type="button">
            快捷键
          </button>
          <button id="open-about" class="profile-menu-item" role="menuitem" type="button">
            关于
          </button>
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
      <label class="sr-only" for="conv-filter">筛选会话</label>
      <input id="conv-filter" class="input conv-filter" type="search"
        placeholder="筛选会话" autocomplete="off" />
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
      <section class="sidebar-section" id="archive-section">
        <h2 class="sidebar-title">已归档
          <span id="archived-count" class="badge badge-muted" hidden>0</span>
        </h2>
        <p id="archived-empty" class="sidebar-empty" hidden>暂无归档会话</p>
        <ul id="archived-list" class="contact-list"></ul>
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
          <button id="voice-btn" class="icon-btn" type="button" aria-label="按住说话"
            data-action="toggle-voice">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </button>
          <span id="voice-timer" class="voice-timer" hidden></span>
          <button id="emoji-btn" class="icon-btn" type="button" aria-label="插入表情"
            data-action="toggle-emoji">😊</button>
          <div id="emoji-panel" class="emoji-panel" hidden></div>
          <input id="attach-input" type="file" multiple hidden
            accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain" />
          <div id="message-reply-bar" class="reply-bar" hidden>
            <span class="reply-bar-text"></span>
            <button class="reply-bar-cancel" type="button"
              data-action="cancel-reply" aria-label="取消引用">×</button>
          </div>
          <label class="sr-only" for="message-input">消息内容</label>
          <textarea id="message-input" class="input" rows="1" maxlength="2000"
            placeholder="输入消息"></textarea>
          <span id="char-count" class="char-count" hidden></span>
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
  document.getElementById("edit-profile").addEventListener("click", openProfileModal);
  document.getElementById("open-stars").addEventListener("click", openStarsModal);
  document.getElementById("open-sessions").addEventListener("click", openSessionsModal);
  document.getElementById("open-calls").addEventListener("click", openCallsModal);
  document
    .getElementById("open-notify-settings")
    .addEventListener("click", openNotifySettingsModal);
  document.getElementById("open-shortcuts").addEventListener("click", openShortcutsModal);
  document.getElementById("open-about").addEventListener("click", openAboutModal);
  document.getElementById("notify-bell").addEventListener("click", openNotificationsModal);
  document.getElementById("export-data").addEventListener("click", () => {
    setProfileMenu(false);
    window.location.href = "/api/me/export";
  });
  document.addEventListener("keydown", onGlobalKeydown);
  document.getElementById("search-form").addEventListener("submit", onSearch);
  document.getElementById("search-form").addEventListener("click", onSearchModeClick);
  document.getElementById("search-results").addEventListener("click", onSearchResultClick);
  document.getElementById("conv-filter").addEventListener("input", (event) => {
    state.convFilter = event.target.value;
    renderSidebar();
  });
  document.getElementById("requests-list").addEventListener("click", onRequestListClick);
  document.getElementById("recommend-list").addEventListener("click", onRecommendListClick);
  document.getElementById("recommend-refresh").addEventListener("click", loadRecommendations);
  document.getElementById("friends-list").addEventListener("click", onFriendListClick);
  document.getElementById("groups-list").addEventListener("click", onGroupListClick);
  document.getElementById("archived-list").addEventListener("click", onArchivedListClick);
  document.getElementById("group-create").addEventListener("click", openGroupCreateModal);
  document.getElementById("composer").addEventListener("submit", onComposerSubmit);
  document.getElementById("composer").addEventListener("click", onComposerBarClick);
  document.getElementById("message-input").addEventListener("keydown", onComposerKeydown);
  document.getElementById("message-input").addEventListener("input", onComposerInput);
  document.getElementById("message-input").addEventListener("blur", onComposerBlur);
  bindFileDrop(document.getElementById("composer"), false);
  bindPasteUpload(document.getElementById("message-input"), false);
  document.getElementById("attach-btn").addEventListener("click", () => {
    document.getElementById("attach-input").click();
  });
  document.getElementById("voice-btn").addEventListener("click", () => toggleVoice(false));
  bindEmojiPanel("emoji-btn", "emoji-panel");
  document.getElementById("attach-input").addEventListener("change", (event) => {
    onAttachSelected(event, false);
  });
  document.getElementById("messages").addEventListener("click", onMessagesClick);
  document.getElementById("load-older").addEventListener("click", loadOlder);
  document.getElementById("chat-back").addEventListener("click", closeChat);
  document.getElementById("group-panel").addEventListener("click", onGroupPanelClick);
  document.getElementById("chat-active").addEventListener("click", onChatHeaderClick);
  refreshSidebar();
  loadNotifications();
}

function openProfileModal() {
  setProfileMenu(false);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="profile-modal" role="dialog" aria-modal="true">
      <form id="profile-form" class="modal-card">
        <h3 class="modal-title">编辑资料</h3>
        <label class="sr-only" for="profile-nickname">昵称</label>
        <input id="profile-nickname" class="input" maxlength="32" placeholder="昵称"
          value="${escapeHtml(state.me.nickname || "")}" />
        <label class="sr-only" for="profile-bio">简介</label>
        <textarea id="profile-bio" class="input" rows="3" maxlength="200"
          placeholder="简介（仅好友可见）">${escapeHtml(state.me.bio || "")}</textarea>
        <div class="profile-avatar-row">
          <span class="muted">头像</span>
          <input id="profile-avatar-input" type="file" hidden
            accept="image/png,image/jpeg,image/gif,image/webp" />
          <button id="profile-avatar-btn" class="btn btn-ghost btn-sm" type="button">
            上传新头像
          </button>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-profile">取消</button>
          <button class="btn btn-primary" type="submit">保存</button>
        </div>
      </form>
    </div>`
  );
  const modal = document.getElementById("profile-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-profile']")) {
      modal.remove();
    }
  });
  document.getElementById("profile-form").addEventListener("submit", onProfileSubmit);
  document.getElementById("profile-avatar-btn").addEventListener("click", () => {
    document.getElementById("profile-avatar-input").click();
  });
  document.getElementById("profile-avatar-input").addEventListener("change", onAvatarSelected);
  document.getElementById("profile-nickname").focus();
}

async function openStarsModal() {
  setProfileMenu(false);
  const response = await api("/api/me/stars?limit=50");
  if (!response.ok) return;
  const body = await response.json();
  const items = body.messages
    .map((item) => {
      const label =
        item.conversation.type === "group"
          ? `群：${item.conversation.group_name || ""}`
          : item.conversation.peer_name || "";
      const target =
        item.conversation.type === "group"
          ? `data-group="${item.conversation.group_id}"`
          : `data-peer="${escapeHtml(item.conversation.peer_sub || "")}"`;
      const preview = item.deleted ? "消息已撤回" : item.content || "";
      return `<li class="contact-item">
        <button class="contact-button" type="button" data-action="open-star" ${target}>
          <span class="contact-main">
            <span class="contact-name">${escapeHtml(label)}</span>
            <span class="contact-preview">${escapeHtml(preview)}</span>
          </span>
        </button>
      </li>`;
    })
    .join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="stars-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">我的收藏</h3>
        <ul class="contact-list forward-list">${
          items || '<li class="sidebar-empty">还没有收藏</li>'
        }</ul>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-stars">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("stars-modal");
  modal.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action='open-star']");
    if (target) {
      modal.remove();
      if (target.dataset.group) openGroup(Number(target.dataset.group));
      else if (target.dataset.peer) openChat(target.dataset.peer);
      return;
    }
    if (event.target === modal || event.target.closest("[data-action='close-stars']")) {
      modal.remove();
    }
  });
}

async function openSessionsModal() {
  setProfileMenu(false);
  await renderSessionsModal();
}

async function renderSessionsModal() {
  const response = await api("/api/me/sessions");
  if (!response.ok) return;
  const sessions = (await response.json()).sessions;
  const existing = document.getElementById("sessions-modal");
  if (existing) existing.remove();
  const rows = sessions
    .map((session) => {
      const time = new Date(session.last_seen_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
      return `<li class="contact-item">
        <span class="contact-main">
          <span class="contact-name">${session.current ? "当前设备" : "其他设备"} · ${escapeHtml(time)}</span>
          <span class="contact-preview">有效期至 ${escapeHtml(
            new Date(session.expires_at).toLocaleDateString()
          )}</span>
        </span>
        ${session.current
          ? '<span class="badge badge-primary">当前</span>'
          : `<button class="btn btn-ghost btn-sm" type="button"
              data-action="revoke-session" data-id="${escapeHtml(session.id)}">撤销</button>`}
      </li>`;
    })
    .join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="sessions-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">登录设备</h3>
        <ul class="contact-list forward-list">${rows || '<li class="sidebar-empty">无会话</li>'}</ul>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="revoke-others">退出其他设备</button>
          <button class="btn btn-primary" type="button" data-action="close-sessions">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("sessions-modal");
  modal.addEventListener("click", async (event) => {
    const revoke = event.target.closest("[data-action='revoke-session']");
    if (revoke) {
      const result = await api(`/api/me/sessions/${encodeURIComponent(revoke.dataset.id)}`, {
        method: "DELETE",
      });
      if (result.ok) await renderSessionsModal();
      return;
    }
    if (event.target.closest("[data-action='revoke-others']")) {
      const result = await api("/api/me/sessions", { method: "DELETE" });
      if (result.ok) await renderSessionsModal();
      return;
    }
    if (event.target === modal || event.target.closest("[data-action='close-sessions']")) {
      modal.remove();
    }
  });
}

async function openCallsModal() {
  setProfileMenu(false);
  const response = await api("/api/me/calls?limit=50");
  if (!response.ok) return;
  const calls = (await response.json()).calls;
  const statusLabel = {
    accepted: "已接通",
    rejected: "已拒绝",
    missed: "未接",
  };
  const rows = calls
    .map((call) => {
      const time = new Date(call.started_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      });
      const peer = call.peer.nickname || call.peer.name || call.peer.sub;
      return `<li class="contact-item">
        <span class="contact-main">
          <span class="contact-name">${escapeHtml(peer)} · ${
            call.kind === "video" ? "视频" : "语音"
          }</span>
          <span class="contact-preview">${escapeHtml(time)}</span>
        </span>
        <span class="badge ${call.status === "missed" ? "badge-warning" : "badge-muted"}">${
          statusLabel[call.status] || "进行中"
        }</span>
      </li>`;
    })
    .join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="calls-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">通话记录</h3>
        <ul class="contact-list forward-list">${rows || '<li class="sidebar-empty">暂无通话记录</li>'}</ul>
        <div class="modal-actions">
          <button class="btn btn-primary" type="button" data-action="close-calls">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("calls-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-calls']")) {
      modal.remove();
    }
  });
}

function openNotifySettingsModal() {
  setProfileMenu(false);
  const enabled = localStorage.getItem("lichat-desktop-notify") !== "off";
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="notify-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">通知设置</h3>
        <label class="notify-row">
          <input type="checkbox" id="notify-toggle" ${enabled ? "checked" : ""} />
          <span>桌面通知（新消息提醒）</span>
        </label>
        <p class="muted">仅在页面处于后台时提醒；首次开启需要浏览器授权。</p>
        <div class="modal-actions">
          <button class="btn btn-primary" type="button" data-action="close-notify">完成</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("notify-modal");
  document.getElementById("notify-toggle").addEventListener("change", async (event) => {
    if (event.target.checked) {
      if (window.Notification && Notification.permission === "default") {
        try {
          await Notification.requestPermission();
        } catch {
          /* 拒绝授权仅不弹通知 */
        }
      }
      localStorage.setItem("lichat-desktop-notify", "on");
    } else {
      localStorage.setItem("lichat-desktop-notify", "off");
    }
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-notify']")) {
      modal.remove();
    }
  });
}

function updateNotifyBadge() {
  const badge = document.getElementById("notify-badge");
  if (!badge) return;
  badge.hidden = state.notificationsUnread === 0;
  badge.textContent = state.notificationsUnread > 99 ? "99+" : String(state.notificationsUnread);
}

async function loadNotifications(append = false) {
  let url = "/api/me/notifications?limit=30";
  if (append && state.notificationsNext) url += `&cursor=${state.notificationsNext}`;
  const response = await api(url);
  if (!response.ok) return;
  const body = await response.json();
  if (append) {
    state.notifications = state.notifications.concat(body.notifications);
  } else {
    state.notifications = body.notifications;
  }
  state.notificationsUnread = body.unread_count;
  state.notificationsNext = body.next_cursor;
  updateNotifyBadge();
  renderNotificationsModal();
}

function notificationText(item) {
  const actor = item.actor ? displayName(item.actor) : "";
  const groupName = item.group ? item.group.name || "群聊" : "";
  switch (item.type) {
    case "friend_request":
      return `${actor || "有人"} 请求添加你为好友`;
    case "mention":
      return groupName
        ? `${actor} 在「${groupName}」中提到了你`
        : `${actor} 提到了你`;
    case "muted":
      return `你在「${groupName}」中被禁言`;
    case "unmuted":
      return `你在「${groupName}」中被解除禁言`;
    case "role_changed":
      return `你在「${groupName}」中的角色已变更为 ${
        item.payload && item.payload.role === "admin" ? "管理员" : "成员"
      }`;
    case "group_dissolved":
      return `群「${groupName}」已解散`;
    default:
      return "新通知";
  }
}

function notificationTime(item) {
  const time = new Date(item.created_at);
  return time.toLocaleString([], { dateStyle: "short", timeStyle: "short" });
}

function renderNotificationsModal() {
  const modal = document.getElementById("notifications-modal");
  if (!modal) return;
  const list = document.getElementById("notifications-list");
  const empty = document.getElementById("notifications-empty");
  if (!list || !empty) return;
  const rows = state.notifications
    .map(
      (item) => `<li class="contact-item notification-item${item.read ? "" : " notification-unread"}">
        <button class="contact-button" type="button" data-action="open-notification"
          data-id="${item.id}" data-type="${item.type}"
          data-group="${item.group ? item.group.id : ""}"
          data-message="${item.payload && item.payload.message_id ? item.payload.message_id : ""}"
          data-peer="${item.actor ? escapeHtml(item.actor.sub) : ""}">
          <span class="contact-main">
            <span class="contact-name">${escapeHtml(notificationText(item))}</span>
            <span class="contact-preview">${escapeHtml(notificationTime(item))}</span>
          </span>
        </button>
      </li>`
    )
    .join("");
  list.innerHTML = rows;
  empty.hidden = state.notifications.length > 0;
  const more = document.getElementById("notifications-more");
  if (more) more.hidden = !state.notificationsNext;
}

async function openNotificationsModal() {
  await loadNotifications();
  let modal = document.getElementById("notifications-modal");
  if (!modal) {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div class="modal-overlay" id="notifications-modal" role="dialog" aria-modal="true">
        <div class="modal-card">
          <h3 class="modal-title">通知</h3>
          <p id="notifications-empty" class="sidebar-empty" hidden>暂无通知</p>
          <ul id="notifications-list" class="contact-list forward-list"></ul>
          <div class="modal-actions">
            <button class="btn btn-ghost btn-sm" type="button" id="notifications-more" hidden>加载更多</button>
            <button class="btn btn-ghost" type="button" id="notifications-read-all">全部已读</button>
            <button class="btn btn-primary" type="button" data-action="close-notifications">关闭</button>
          </div>
        </div>
      </div>`
    );
    modal = document.getElementById("notifications-modal");
    document.getElementById("notifications-more").addEventListener("click", () => {
      loadNotifications(true);
    });
    document.getElementById("notifications-read-all").addEventListener("click", async () => {
      const response = await api("/api/me/notifications/read", { method: "POST" });
      if (response.ok) {
        state.notificationsUnread = 0;
        state.notifications = state.notifications.map((item) => ({
          ...item,
          read: true,
        }));
        updateNotifyBadge();
        renderNotificationsModal();
      }
    });
    modal.addEventListener("click", (event) => {
      const target = event.target.closest("[data-action='open-notification']");
      if (target) {
        modal.remove();
        openNotificationTarget(target);
        return;
      }
      if (
        event.target === modal ||
        event.target.closest("[data-action='close-notifications']")
      ) {
        modal.remove();
      }
    });
  }
  renderNotificationsModal();
}

function openNotificationTarget(target) {
  const type = target.dataset.type;
  const groupId = Number(target.dataset.group || 0);
  const messageId = Number(target.dataset.message || 0);
  if (type === "mention") {
    if (groupId) openGroup(groupId, messageId || null);
    else if (target.dataset.peer) openChat(target.dataset.peer, messageId || null);
    return;
  }
  if (groupId) {
    openGroup(groupId);
    return;
  }
  refreshSidebar();
}

const SHORTCUTS = [
  ["Ctrl/Cmd + K", "聚焦搜索框"],
  ["Ctrl/Cmd + Enter", "发送当前消息"],
  ["Esc", "关闭弹层 / 退出编辑"],
  ["?", "打开快捷键帮助"],
];

function openShortcutsModal() {
  setProfileMenu(false);
  const rows = SHORTCUTS.map(
    ([keys, description]) =>
      `<li class="shortcut-row">
        <kbd class="shortcut-keys">${escapeHtml(keys)}</kbd>
        <span class="shortcut-desc">${escapeHtml(description)}</span>
      </li>`
  ).join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="shortcuts-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">键盘快捷键</h3>
        <ul class="shortcut-list">${rows}</ul>
        <div class="modal-actions">
          <button class="btn btn-primary" type="button" data-action="close-shortcuts">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("shortcuts-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-shortcuts']")) {
      modal.remove();
    }
  });
}

async function openAboutModal() {
  setProfileMenu(false);
  let appVersion = "0.1.0";
  try {
    const response = await fetch("/api/version", { credentials: "same-origin" });
    if (response.ok) {
      const body = await response.json();
      if (body.app_version) appVersion = body.app_version;
    }
  } catch {
    /* 版本获取失败使用默认值 */
  }
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="about-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">关于 Li&Chat</h3>
        <p class="about-line">${escapeHtml(BRAND.name)} · ${escapeHtml(BRAND.slogan)}</p>
        <p class="muted">应用版本 ${escapeHtml(appVersion)} · 前端 ${escapeHtml(FRONTEND_VERSION)}</p>
        <p class="muted">统一 Li&Pass 登录；消息、群聊、投票、语音、通话等能力持续迭代。</p>
        <p class="muted">快捷键：Ctrl/Cmd+K 搜索 · ? 帮助 · Ctrl/Cmd+Enter 发送</p>
        <div class="modal-actions">
          <button class="btn btn-primary" type="button" data-action="close-about">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("about-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-about']")) {
      modal.remove();
    }
  });
}

function confirmModal(title, message, onConfirm, confirmLabel = "确认") {
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="confirm-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">${escapeHtml(title)}</h3>
        <p class="confirm-message">${escapeHtml(message)}</p>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-confirm">取消</button>
          <button class="btn btn-danger" type="button" id="confirm-ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("confirm-modal");
  const close = () => modal.remove();
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-confirm']")) {
      close();
    }
  });
  document.getElementById("confirm-ok").addEventListener("click", async () => {
    close();
    await onConfirm();
  });
}

function onGlobalKeydown(event) {
  const mod = event.ctrlKey || event.metaKey;
  if (event.key === "Tab") {
    const modal = document.querySelector(".modal-overlay");
    if (modal) trapTab(modal, event);
  }
  if (mod && event.key.toLowerCase() === "k") {
    event.preventDefault();
    const input = document.getElementById("search-input");
    if (input) input.focus();
    return;
  }
  if (mod && event.key === "Enter") {
    const composer =
      state.activeGroupId !== null
        ? document.getElementById("group-composer")
        : state.activeSub
          ? document.getElementById("composer")
          : null;
    if (composer && !composer.hidden) {
      event.preventDefault();
      composer.requestSubmit();
    }
    return;
  }
  if (event.key === "Escape") {
    const modal = document.querySelector(".modal-overlay");
    if (modal) {
      modal.remove();
      return;
    }
    const viewer = document.getElementById("image-viewer");
    if (viewer) {
      viewer.remove();
      document.removeEventListener("keydown", closeImageKeydown);
      return;
    }
    const dropdown = document.getElementById("profile-dropdown");
    if (dropdown && !dropdown.hidden) {
      setProfileMenu(false);
      return;
    }
    if (state.emojiOpen) {
      state.emojiOpen = false;
      renderEmojiPanel();
      return;
    }
    if (state.editingId) {
      cancelEditing();
    }
    return;
  }
  if (event.key === "?" && !mod && !event.altKey) {
    const target = event.target;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
    event.preventDefault();
    openShortcutsModal();
  }
}

let lastFocusElement = null;

function trapTab(modal, event) {
  const focusable = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function initFocusTracking() {
  const observer = new MutationObserver(() => {
    const openModal = document.querySelector(".modal-overlay");
    if (openModal) {
      if (!openModal.contains(document.activeElement)) {
        if (!lastFocusElement || !document.contains(lastFocusElement)) {
          lastFocusElement = document.activeElement;
        }
        const focusable = openModal.querySelector(
          "input, textarea, select, button, [href]"
        );
        if (focusable) focusable.focus();
      }
    } else if (lastFocusElement && document.contains(lastFocusElement)) {
      lastFocusElement.focus();
      lastFocusElement = null;
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function updateTitleBadge() {
  const total = state.conversations.reduce(
    (sum, conversation) => sum + (conversation.unread_count || 0),
    0
  );
  document.title = total > 0 ? `(${total}) Li&Chat` : "Li&Chat";
}

function desktopNotify(title, body) {
  try {
    if (
      document.hidden &&
      window.Notification &&
      Notification.permission === "granted" &&
      localStorage.getItem("lichat-desktop-notify") !== "off"
    ) {
      new Notification(title, {
        body,
        tag: "lichat",
        icon: "/favicon.svg",
      });
    }
  } catch {
    /* 通知失败不影响聊天 */
  }
}

function notifyMessage(message) {
  if (!document.hidden || message.sender_sub === state.me.sub) return;
  let title = "Li&Chat";
  if (message.group_id != null) {
    const group = state.groups.find((item) => item.id === message.group_id);
    if (group) title = group.name;
  } else {
    const peer = state.friends.find((item) => item.sub === message.sender_sub);
    if (peer) title = displayName(peer);
  }
  let body = message.deleted ? "消息已撤回" : message.content || "";
  if (!body && message.content_type === "image") body = "[图片]";
  if (!body && message.content_type === "file") body = "[文件]";
  desktopNotify(title, body);
}

async function onProfileSubmit(event) {
  event.preventDefault();
  const nickname = document.getElementById("profile-nickname").value.trim();
  const bio = document.getElementById("profile-bio").value.trim();
  const response = await api("/api/me", {
    method: "PATCH",
    body: JSON.stringify({ nickname, bio }),
  });
  if (response.ok) {
    applyMeUpdate(await response.json());
    document.getElementById("profile-modal").remove();
    toast("资料已保存", "success");
  }
}

async function onAvatarSelected(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const uploadResponse = await api("/api/uploads", { method: "POST", body: form });
  if (!uploadResponse.ok) return;
  const upload = await uploadResponse.json();
  const avatarResponse = await api("/api/me/avatar", {
    method: "POST",
    body: JSON.stringify({ url: upload.url }),
  });
  if (avatarResponse.ok) {
    applyMeUpdate(await avatarResponse.json());
    toast("头像已更新", "success");
  }
}

function applyMeUpdate(me) {
  state.me.nickname = me.nickname;
  state.me.bio = me.bio;
  state.me.picture = me.picture;
  const name = document.querySelector(".app-profile .profile-name");
  if (name) name.textContent = displayName(state.me);
  const toggle = document.getElementById("profile-toggle");
  const existing = toggle.querySelector(".avatar");
  if (existing) {
    const holder = document.createElement("div");
    holder.innerHTML = avatarHtml(state.me);
    existing.replaceWith(holder.firstChild);
  }
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
  const firstLoad = state.friends.length === 0 && state.groups.length === 0;
  if (firstLoad) {
    state.sidebarLoading = true;
    state.sidebarError = false;
    renderSidebar();
  }
  let failed = false;
  try {
    const [
      friendsRes,
      requestsRes,
      recommendRes,
      conversationsRes,
      archivedRes,
      groupsRes,
    ] = await Promise.all([
      api("/api/friends"),
      api("/api/friends/requests"),
      api("/api/friends/recommendations"),
      api("/api/conversations"),
      api("/api/conversations?archived=true"),
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
    if (archivedRes.ok) {
      state.archivedConversations = (await archivedRes.json()).conversations;
    }
    if (groupsRes.ok) state.groups = (await groupsRes.json()).groups;
    failed =
      !friendsRes.ok || !conversationsRes.ok || !groupsRes.ok;
  } catch {
    /* 登录失效已由 api() 统一跳转 */
    failed = true;
  } finally {
    state.sidebarLoading = false;
    state.sidebarError = failed;
    renderSidebar();
  }
}

function summaryPreview(summary) {
  const last = summary && summary.last_message;
  if (!last) return "";
  if (last.deleted) return "消息已撤回";
  if (last.content_type === "image") return "[图片]";
  if (last.content_type === "file") return "[文件]";
  if (last.content_type === "audio") return "[语音]";
  return last.content || "";
}

function sidebarSkeletonHtml(count) {
  return Array.from(
    { length: count },
    () => `<li class="contact-item skeleton-item">
      <div class="skeleton skeleton-avatar"></div>
      <div class="skeleton-lines">
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line skeleton-line-short"></div>
      </div>
    </li>`
  ).join("");
}

function sidebarRetryHtml() {
  return `<li class="contact-item">
    <button class="contact-button" type="button" data-action="sidebar-retry">
      <span class="contact-main">
        <span class="contact-name">加载失败，点击重试</span>
      </span>
    </button>
  </li>`;
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
    state.conversations
      .filter((item) => item.peer)
      .map((item) => [item.peer.sub, item])
  );
  const friendsById = new Map(state.friends.map((friend) => [friend.sub, friend]));
  const orderedSubs = [
    ...state.conversations
      .map((item) => (item.peer ? item.peer.sub : null))
      .filter((sub) => typeof sub === "string"),
    ...state.friends.map((friend) => friend.sub),
  ];
  const friends = [...new Set(orderedSubs)]
    .map((sub) => friendsById.get(sub))
    .filter(Boolean);
  const filterText = state.convFilter.trim().toLowerCase();
  const matchesConv = (name, preview) =>
    !filterText || `${name} ${preview || ""}`.toLowerCase().includes(filterText);
  const visibleFriends = friends.filter((friend) =>
    matchesConv(displayName(friend), summaryPreview(summaries.get(friend.sub)))
  );
  const friendsLoading = state.sidebarLoading && friends.length === 0;
  const friendsFailed =
    state.sidebarError && friends.length === 0 && state.groups.length === 0;
  document.getElementById("friends-empty").hidden =
    friendsLoading || friendsFailed || visibleFriends.length > 0;
  document.getElementById("friends-list").innerHTML = friendsLoading
    ? sidebarSkeletonHtml(5)
    : friendsFailed
      ? sidebarRetryHtml()
    : visibleFriends
        .map((friend) => friendHtml(friend, summaries.get(friend.sub)))
        .join("");
  const groupSummaries = new Map(
    state.conversations
      .filter((item) => item.group)
      .map((item) => [item.group.id, item])
  );
  const visibleGroups = state.groups.filter((group) =>
    matchesConv(group.name, summaryPreview(groupSummaries.get(group.id)))
  );
  const groupsLoading = state.sidebarLoading && state.groups.length === 0;
  document.getElementById("groups-empty").hidden =
    groupsLoading || friendsFailed || visibleGroups.length > 0;
  document.getElementById("groups-list").innerHTML = groupsLoading
    ? sidebarSkeletonHtml(3)
    : friendsFailed
      ? ""
    : visibleGroups
        .map((group) => groupHtml(group, groupSummaries.get(group.id)))
        .join("");
  document.getElementById("archived-empty").hidden =
    state.archivedConversations.length > 0;
  const archivedCount = document.getElementById("archived-count");
  archivedCount.hidden = state.archivedConversations.length === 0;
  archivedCount.textContent = String(state.archivedConversations.length);
  document.getElementById("archived-list").innerHTML = state.archivedConversations
    .map(archivedRowHtml)
    .join("");
  updateTitleBadge();
}

function requestIncomingHtml(item) {
  return `<li class="contact-item">
    <div class="contact-info">
      ${avatarHtml(item.requester)}
      <span class="contact-name">${escapeHtml(displayName(item.requester))}</span>
      ${item.reason ? `<span class="contact-preview">${escapeHtml(item.reason)}</span>` : ""}
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
      ${item.reason ? `<span class="contact-preview">${escapeHtml(item.reason)}</span>` : ""}
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
  const pinned = summary ? summary.pinned : false;
  const muted = summary ? summary.muted : false;
  const dmKey = [state.me.sub, friend.sub].sort().join(":");
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
  const lastTime = summary && summary.last_message
    ? relativeTime(summary.last_message.created_at)
    : "";
  const lastFull = summary && summary.last_message
    ? new Date(summary.last_message.created_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "";
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open" data-sub="${escapeHtml(friend.sub)}">
      ${avatarHtml(friend)}
      <span class="contact-main">
        <span class="contact-name">
          <span class="presence-dot${online ? " presence-online" : ""}" aria-hidden="true"></span>
          ${escapeHtml(displayName(friend))}
        </span>
        ${preview
          ? `<span class="contact-preview" title="${escapeHtml(lastFull)}">${escapeHtml(preview)}${
              lastTime ? ` · ${lastTime}` : ""
            }</span>`
          : ""}
      </span>
      ${unread > 0
        ? `<span class="badge badge-unread${muted ? " badge-muted-unread" : ""}"
            data-role="unread" data-sub="${escapeHtml(friend.sub)}">${unread}</span>`
        : ""}
    </button>
    <span class="contact-actions conv-actions">
      <button class="icon-btn conv-toggle${pinned ? " conv-toggle-on" : ""}" type="button"
        data-action="toggle-pin" data-kind="dm" data-key="${dmKey}"
        data-value="${pinned}" aria-label="置顶">📌</button>
      <button class="icon-btn conv-toggle${muted ? " conv-toggle-on" : ""}" type="button"
        data-action="toggle-mute" data-kind="dm" data-key="${dmKey}"
        data-value="${muted}" aria-label="免打扰">🔕</button>
      <button class="icon-btn conv-toggle" type="button"
        data-action="toggle-archive" data-kind="dm" data-key="${dmKey}"
        data-value="false" aria-label="归档">🗄️</button>
    </span>
  </li>`;
}

function groupHtml(group, summary) {
  const count = group.members ? group.members.length : 0;
  const unread = summary ? summary.unread_count : 0;
  const pinned = summary ? summary.pinned : false;
  const muted = summary ? summary.muted : false;
  const preview = summary && summary.last_message
    ? summary.last_message.deleted
      ? "消息已撤回"
      : summary.last_message.content_type === "image"
        ? "[图片]"
        : summary.last_message.content_type === "file"
          ? "[文件]"
          : summary.last_message.content
    : "";
  const lastTime = summary && summary.last_message
    ? relativeTime(summary.last_message.created_at)
    : "";
  const lastFull = summary && summary.last_message
    ? new Date(summary.last_message.created_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "";
  return `<li class="contact-item">
    <button class="contact-button" type="button"
      data-action="open-group" data-id="${group.id}">
      ${group.avatar_url
        ? `<img class="avatar group-avatar-img" src="${escapeHtml(group.avatar_url)}" alt="群头像" />`
        : '<div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>'}
      <span class="contact-main">
        <span class="contact-name">${escapeHtml(group.name)}</span>
        <span class="contact-preview" title="${escapeHtml(lastFull)}">${
          preview || `${count} 位成员`
        }${lastTime ? ` · ${lastTime}` : ""}</span>
      </span>
      ${unread > 0
        ? `<span class="badge badge-unread${muted ? " badge-muted-unread" : ""}"
            data-role="unread" data-id="${group.id}">${unread}</span>`
        : ""}
    </button>
    <span class="contact-actions conv-actions">
      <button class="icon-btn conv-toggle${pinned ? " conv-toggle-on" : ""}" type="button"
        data-action="toggle-pin" data-kind="group" data-key="${group.id}"
        data-value="${pinned}" aria-label="置顶">📌</button>
      <button class="icon-btn conv-toggle${muted ? " conv-toggle-on" : ""}" type="button"
        data-action="toggle-mute" data-kind="group" data-key="${group.id}"
        data-value="${muted}" aria-label="免打扰">🔕</button>
      <button class="icon-btn conv-toggle" type="button"
        data-action="toggle-archive" data-kind="group" data-key="${group.id}"
        data-value="false" aria-label="归档">🗄️</button>
    </span>
  </li>`;
}

function archivedRowHtml(item) {
  const peer = item.peer;
  const kind = peer ? "dm" : "group";
  const key = peer ? [state.me.sub, peer.sub].sort().join(":") : String(item.group.id);
  const label = peer ? displayName(peer) : item.group.name;
  const avatar = peer
    ? avatarHtml(peer)
    : item.group && item.group.avatar_url
      ? `<img class="avatar group-avatar-img" src="${escapeHtml(item.group.avatar_url)}" alt="群头像" />`
      : '<div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>';
  const openAction = peer
    ? `data-action="open-archived" data-sub="${escapeHtml(peer.sub)}"`
    : `data-action="open-archived-group" data-id="${item.group.id}"`;
  const lastTime = item.last_message ? relativeTime(item.last_message.created_at) : "";
  const lastFull = item.last_message
    ? new Date(item.last_message.created_at).toLocaleString([], {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "";
  return `<li class="contact-item">
    <button class="contact-button" type="button" ${openAction}>
      ${avatar}
      <span class="contact-main">
        <span class="contact-name">${escapeHtml(label)}</span>
        <span class="contact-preview" title="${escapeHtml(lastFull)}">${
          escapeHtml(summaryPreview(item)) || "归档会话"
        }${lastTime ? ` · ${lastTime}` : ""}</span>
      </span>
    </button>
    <button class="btn btn-ghost btn-sm" type="button" data-action="unarchive"
      data-kind="${kind}" data-key="${key}">取消归档</button>
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
      ? `data-action="open-group-hit" data-group="${hit.conversation.group_id}" data-message="${hit.id}"`
      : `data-action="open-dm-hit" data-peer="${escapeHtml(hit.conversation.peer_sub)}" data-message="${hit.id}"`;
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
  results.hidden = !hasResults && !state.searchQuery;
  const more = state.searchKind === "messages" && state.searchNextBefore
    ? `<li class="contact-item search-item"><button class="btn btn-ghost btn-sm"
        type="button" data-action="search-more">加载更多</button></li>`
    : "";
  results.innerHTML = hasResults
    ? (state.searchKind === "messages"
        ? state.messageHits.map(messageHitHtml).join("")
        : state.searchResults.map(searchResultHtml).join("")) + more
    : state.searchQuery
      ? '<li class="sidebar-empty">没有找到相关内容</li>'
      : "";
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
    openChat(button.dataset.peer, Number(button.dataset.message));
    return;
  }
  if (button.dataset.action === "open-group-hit") {
    openGroup(Number(button.dataset.group), Number(button.dataset.message));
    return;
  }
  if (button.dataset.action === "open") {
    openChat(button.dataset.sub);
    return;
  }
  openRequestModal(button.dataset.sub);
}

async function onRequestListClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const sub = button.dataset.sub;
  if (button.dataset.action === "accept") {
    const response = await api(`/api/friends/requests/${encodeURIComponent(sub)}/accept`, {
      method: "POST",
    });
    if (response.ok) toast("已添加好友", "success");
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
  openRequestModal(button.dataset.sub);
}

function openRequestModal(sub) {
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="request-modal" role="dialog" aria-modal="true">
      <form id="request-form" class="modal-card">
        <h3 class="modal-title">添加好友</h3>
        <label class="sr-only" for="request-reason">附言</label>
        <textarea id="request-reason" class="input" rows="3" maxlength="200"
          placeholder="附言（可选，200 字以内）"></textarea>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-request">取消</button>
          <button class="btn btn-primary" type="submit">发送申请</button>
        </div>
      </form>
    </div>`
  );
  const modal = document.getElementById("request-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-request']")) {
      modal.remove();
    }
  });
  document.getElementById("request-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.getElementById("request-reason").value.trim();
    const response = await api("/api/friends/requests", {
      method: "POST",
      body: JSON.stringify({ to_sub: sub, message }),
    });
    if (response.ok) {
      modal.remove();
      await refreshSidebar();
      const input = document.getElementById("search-input");
      if (input) input.value = "";
      const results = document.getElementById("search-results");
      if (results) results.hidden = true;
      toast("好友申请已发送", "success");
    }
  });
  document.getElementById("request-reason").focus();
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
  const button = event.target.closest("[data-action]");
  if (!button) return;
  if (button.dataset.action === "sidebar-retry") {
    refreshSidebar();
    return;
  }
  if (button.dataset.action.startsWith("toggle-")) {
    toggleConversationSetting(button);
    return;
  }
  if (button.dataset.action !== "open") return;
  openChat(button.dataset.sub);
}

function onGroupListClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  if (button.dataset.action.startsWith("toggle-")) {
    toggleConversationSetting(button);
    return;
  }
  if (button.dataset.action !== "open-group") return;
  openGroup(Number(button.dataset.id));
}

async function onArchivedListClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  if (button.dataset.action === "unarchive") {
    const response = await api("/api/conversations/settings", {
      method: "PATCH",
      body: JSON.stringify({
        kind: button.dataset.kind,
        key: button.dataset.key,
        archived: false,
      }),
    });
    if (response.ok) {
      toast("已取消归档", "success");
      await refreshSidebar();
    }
    return;
  }
  if (button.dataset.action === "open-archived") {
    openChat(button.dataset.sub);
    return;
  }
  if (button.dataset.action === "open-archived-group") {
    openGroup(Number(button.dataset.id));
  }
}

async function toggleConversationSetting(button) {
  const field =
    button.dataset.action === "toggle-pin"
      ? "pinned"
      : button.dataset.action === "toggle-mute"
        ? "muted"
        : "archived";
  const value = button.dataset.value === "true";
  const response = await api("/api/conversations/settings", {
    method: "PATCH",
    body: JSON.stringify({
      kind: button.dataset.kind,
      key: button.dataset.key,
      [field]: !value,
    }),
  });
  if (response.ok) {
    const label =
      field === "pinned"
        ? value
          ? "已取消置顶"
          : "已置顶"
        : field === "muted"
          ? value
            ? "已开启提醒"
            : "已开启免打扰"
          : value
            ? "已取消归档"
            : "已归档";
    toast(label, "success");
  }
  await refreshSidebar();
}

async function openGroup(groupId, locateId = null) {
  if (state.recording.active) stopVoice();
  exitSelectMode();
  state.conversationEpoch += 1;
  const response = await api(`/api/groups/${groupId}`);
  if (!response.ok) return;
  state.activeGroupId = groupId;
  state.activeGroup = await response.json();
  state.activeSub = null;
  state.activePeer = null;
  state.editingId = null;
  state.pickerMessageId = null;
  state.replyTo = null;
  state.mentionSubs = [];
  state.mentionOpen = false;
  state.groupFiles = [];
  state.groupFilesNext = null;
  state.groupReadBy = {};
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = true;
  document.getElementById("chat-active").hidden = true;
  document.getElementById("group-panel").hidden = false;
  renderGroupPanel();
  loadDraft();
  document.getElementById("app").classList.add("chat-open");
  await loadGroupHistory();
  await markGroupRead();
  await loadGroupFiles();
  if (locateId) await locateMessage(locateId);
}

function closeGroupPanel() {
  if (state.recording.active) stopVoice();
  exitSelectMode();
  state.conversationEpoch += 1;
  state.activeGroupId = null;
  state.activeGroup = null;
  state.replyTo = null;
  state.groupFiles = [];
  state.groupFilesNext = null;
  state.groupReadBy = {};
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
  const myMuted =
    (group.members.find((member) => member.user.sub === me) || {}).muted === true;
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
      const canMute =
        (myRole === "owner" || myRole === "admin") &&
        member.role === "member" &&
        !isMe;
      const mute = canMute
        ? `<button class="btn btn-ghost btn-sm" type="button"
            data-action="group-mute" data-sub="${escapeHtml(member.user.sub)}"
            data-muted="${member.muted}">${member.muted ? "解除禁言" : "禁言"}</button>`
        : "";
      return `<li class="contact-item group-member">
        ${avatarHtml(member.user)}
        <span class="contact-main">
          <span class="contact-name">${escapeHtml(displayName(member.user))}</span>
          <span class="contact-preview">${roleLabel(member.role)}${isMe ? "（我）" : ""}${
            member.muted ? " · 已禁言" : ""
          }</span>
        </span>
        <span class="contact-actions">${ownerActions}${mute}${remove}</span>
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
        ${group.avatar_url
          ? `<img class="avatar group-avatar-img" src="${escapeHtml(group.avatar_url)}" alt="群头像" />`
          : '<div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>'}
        <span class="chat-peer-main">
          <span class="chat-peer-name">${escapeHtml(group.name)}</span>
          <span class="chat-peer-status">${group.members.length} 位成员</span>
        </span>
      </div>
      <span class="chat-peer-actions">
        <button class="icon-btn" type="button" data-action="toggle-select" aria-label="多选消息">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
        </button>
      </span>
    </header>
    <div class="group-chat">
      <button id="group-load-older" class="btn btn-ghost btn-sm load-older" type="button"
        hidden>加载更早消息</button>
      <div id="group-messages" class="messages" role="log" aria-live="polite"
        aria-label="群聊记录"></div>
      <form id="group-composer" class="composer">
        <div id="group-mention-list" class="mention-list" hidden></div>
        <button id="group-mention-btn" class="icon-btn" type="button"
          aria-label="提及成员" ${myMuted ? "disabled" : ""}>@</button>
        <button id="group-poll-btn" class="icon-btn" type="button"
          aria-label="发起投票" data-action="open-poll" ${myMuted ? "disabled" : ""}>📊</button>
        <button id="group-attach-btn" class="icon-btn" type="button" aria-label="发送附件"
          ${myMuted ? "disabled" : ""}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>
        <button id="group-voice-btn" class="icon-btn" type="button" aria-label="按住说话"
          data-action="toggle-voice" ${myMuted ? "disabled" : ""}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </button>
        <span id="group-voice-timer" class="voice-timer" hidden></span>
        <button id="group-emoji-btn" class="icon-btn" type="button" aria-label="插入表情"
          data-action="toggle-emoji" ${myMuted ? "disabled" : ""}>😊</button>
        <div id="group-emoji-panel" class="emoji-panel" hidden></div>
        <input id="group-attach-input" type="file" multiple hidden
          accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain" />
        <div id="group-reply-bar" class="reply-bar" hidden>
          <span class="reply-bar-text"></span>
          <button class="reply-bar-cancel" type="button"
            data-action="cancel-reply" aria-label="取消引用">×</button>
        </div>
        <label class="sr-only" for="group-message-input">消息内容</label>
        <textarea id="group-message-input" class="input" rows="1" maxlength="2000"
          placeholder="${myMuted ? "你已被禁言" : "输入消息"}" ${myMuted ? "disabled" : ""}></textarea>
        <span id="group-char-count" class="char-count" hidden></span>
        <button class="btn btn-primary" type="submit" ${myMuted ? "disabled" : ""}>发送</button>
      </form>
    </div>
    <div class="group-panel-body">
      <section class="group-section">
        <h3 class="group-section-title">公告</h3>
        <div class="group-announcement">
          <p id="group-announcement-text" class="${
            group.announcement ? "" : "group-announcement-empty"
          }">${escapeHtml(group.announcement || "暂无公告，等待群主发布")}</p>
          ${
            group.announcement_updated_at
              ? `<span class="muted announcement-time">发布于 ${new Date(
                  group.announcement_updated_at
                ).toLocaleString([], {
                  dateStyle: "short",
                  timeStyle: "short",
                })}</span>`
              : ""
          }
          ${manager
            ? `<div class="group-rename-row">
                <textarea id="group-announcement-input" class="input" rows="2"
                  maxlength="2000" placeholder="编辑群公告">${escapeHtml(group.announcement || "")}</textarea>
                <button class="btn btn-secondary btn-sm" type="button"
                  data-action="group-announcement">发布</button>
              </div>`
            : ""}
          </div>
      </section>
      <section class="group-section">
        <h3 class="group-section-title">文件</h3>
        <p id="group-files-empty" class="sidebar-empty">暂无共享文件</p>
        <ul id="group-files-list" class="contact-list"></ul>
      </section>
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
              <div class="group-rename-row">
                <span class="muted">群头像</span>
                <input id="group-avatar-input" type="file" hidden
                  accept="image/png,image/jpeg,image/gif,image/webp" />
                <button class="btn btn-ghost btn-sm" type="button"
                  data-action="group-avatar-pick">上传头像</button>
              </div>
            </div>
          </section>`
        : ""}
      <section class="group-section">
        ${myRole === "owner"
          ? `<button class="btn btn-danger" type="button" data-action="group-dissolve">解散群聊</button>`
          : ""}
        <button class="btn btn-ghost" type="button" data-action="group-leave">退出群聊</button>
      </section>
    </div>`;
}

function renderGroupPanel() {
  const panel = document.getElementById("group-panel");
  panel.innerHTML = groupPanelHtml(state.activeGroup);
  renderGroupFiles();
  const back = document.getElementById("group-back");
  if (back) back.addEventListener("click", closeGroupPanel);
  const loadOlder = document.getElementById("group-load-older");
  if (loadOlder) {
    loadOlder.addEventListener("click", () => loadGroupHistory(state.nextBefore));
  }
  const groupMessages = document.getElementById("group-messages");
  if (groupMessages) {
    groupMessages.addEventListener("click", onMessagesClick);
  }
  const composer = document.getElementById("group-composer");
  if (composer) {
    composer.addEventListener("submit", onGroupComposerSubmit);
    composer.addEventListener("click", onComposerBarClick);
    bindFileDrop(composer, true);
    document.getElementById("group-mention-btn").addEventListener("click", toggleMentionList);
    document.getElementById("group-poll-btn").addEventListener("click", openPollModal);
    const mentionList = document.getElementById("group-mention-list");
    if (mentionList) {
      mentionList.addEventListener("click", onMentionPick);
    }
    document.getElementById("group-message-input").addEventListener(
      "keydown",
      onGroupComposerKeydown
    );
    document.getElementById("group-message-input").addEventListener("input", (event) => {
      autoGrowInput(event.target);
      updateCharCount(event.target, "group-char-count");
      saveDraftDebounced(event.target.value);
    });
    bindPasteUpload(document.getElementById("group-message-input"), true);
    document.getElementById("group-attach-btn").addEventListener("click", () => {
      document.getElementById("group-attach-input").click();
    });
    document.getElementById("group-voice-btn").addEventListener("click", () => {
      toggleVoice(true);
    });
    bindEmojiPanel("group-emoji-btn", "group-emoji-panel");
    document.getElementById("group-attach-input").addEventListener("change", (event) => {
      onAttachSelected(event, true);
    });
    const avatarPick = document.querySelector("[data-action='group-avatar-pick']");
    if (avatarPick) {
      avatarPick.addEventListener("click", () => {
        document.getElementById("group-avatar-input").click();
      });
      document.getElementById("group-avatar-input").addEventListener(
        "change",
        onGroupAvatarSelected
      );
    }
  }
}

async function onGroupAvatarSelected(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  if (!file || !state.activeGroupId) return;
  const form = new FormData();
  form.append("file", file);
  const uploadResponse = await api("/api/uploads", { method: "POST", body: form });
  if (!uploadResponse.ok) return;
  const upload = await uploadResponse.json();
  const avatarResponse = await api(`/api/groups/${state.activeGroupId}/avatar`, {
    method: "POST",
    body: JSON.stringify({ url: upload.url }),
  });
  if (avatarResponse.ok) await refreshGroups();
}

async function sendFiles(files, isGroup) {
  const list = Array.from(files || []).filter((file) => file instanceof File);
  if (list.length === 0) return;
  let sent = 0;
  showUploadProgress();
  for (const file of list) {
    const upload = await uploadWithProgress(file, isGroup);
    if (!upload) continue;
    const content_type = upload.mime.startsWith("image/")
      ? "image"
      : upload.mime.startsWith("audio/")
        ? "audio"
        : "file";
    const url = isGroup
      ? `/api/groups/${state.activeGroupId}/messages`
      : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`;
    const messageResponse = await api(url, {
      method: "POST",
      body: JSON.stringify({
        content: "",
        content_type,
        attachment: { url: upload.url },
      }),
    });
    if (messageResponse.ok) sent += 1;
  }
  if (!state.uploadRetry) hideUploadProgress();
  if (sent > 0) {
    toast(sent === 1 ? "附件已发送" : `已发送 ${sent} 个附件`, "success");
  }
}

function showUploadProgress() {
  let region = document.getElementById("upload-progress");
  if (!region) {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div class="upload-progress" id="upload-progress" hidden>
        <div class="upload-progress-bar">
          <div class="upload-progress-fill" id="upload-progress-fill"></div>
        </div>
        <span class="upload-progress-text" id="upload-progress-text"></span>
        <button class="btn btn-ghost btn-sm" type="button" id="upload-retry" hidden>重试</button>
        <button class="icon-btn upload-progress-cancel" id="upload-progress-cancel"
          type="button" aria-label="取消上传">×</button>
      </div>`
    );
    region = document.getElementById("upload-progress");
    document.getElementById("upload-progress-cancel").addEventListener("click", () => {
      if (state.uploadCancel) state.uploadCancel();
    });
    document.getElementById("upload-retry").addEventListener("click", () => {
      const retry = state.uploadRetry;
      state.uploadRetry = null;
      if (!retry) return;
      document.getElementById("upload-retry").hidden = true;
      const fill = document.getElementById("upload-progress-fill");
      if (fill) {
        fill.style.width = "0%";
        fill.classList.remove("upload-progress-failed");
      }
      sendFiles([retry.file], retry.isGroup);
    });
  }
  region.hidden = false;
  document.getElementById("upload-retry").hidden = true;
  document.getElementById("upload-progress-cancel").hidden = false;
  const fill = document.getElementById("upload-progress-fill");
  if (fill) fill.classList.remove("upload-progress-failed");
  renderUploadProgress("", 0);
}

function renderUploadProgress(name, ratio) {
  const fill = document.getElementById("upload-progress-fill");
  const text = document.getElementById("upload-progress-text");
  if (!fill || !text) return;
  const percent = Math.max(0, Math.min(100, Math.round(ratio * 100)));
  fill.style.width = `${percent}%`;
  text.textContent = name ? `正在上传 ${name}（${percent}%）` : "准备上传…";
}

function hideUploadProgress() {
  const region = document.getElementById("upload-progress");
  if (region) region.hidden = true;
  state.uploadCancel = null;
  state.uploadRetry = null;
}

function showUploadError(name) {
  const region = document.getElementById("upload-progress");
  if (!region) return;
  region.hidden = false;
  const fill = document.getElementById("upload-progress-fill");
  const text = document.getElementById("upload-progress-text");
  if (fill) {
    fill.style.width = "100%";
    fill.classList.add("upload-progress-failed");
  }
  if (text) text.textContent = `上传失败：${name}`;
  document.getElementById("upload-retry").hidden = false;
  document.getElementById("upload-progress-cancel").hidden = true;
}

function uploadWithProgress(file, isGroup) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    state.uploadCancel = () => xhr.abort();
    xhr.open("POST", "/api/uploads");
    if (state.me) xhr.setRequestHeader("X-CSRF-Token", state.me.csrf_token);
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        renderUploadProgress(file.name, event.loaded / event.total);
      }
    });
    xhr.onload = () => {
      if (xhr.status === 401) {
        window.location.href = "/";
        resolve(null);
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve(null);
        }
        return;
      }
      let detail = "";
      try {
        const body = JSON.parse(xhr.responseText);
        detail = body && typeof body.detail === "string" ? body.detail : "";
      } catch {
        /* 非 JSON 错误体 */
      }
      toast(friendlyError(xhr.status, detail), "error");
      state.uploadRetry = { file, isGroup };
      showUploadError(file.name);
      resolve(null);
    };
    xhr.onerror = () => {
      toast("网络错误，请检查连接后重试", "error");
      state.uploadRetry = { file, isGroup };
      showUploadError(file.name);
      resolve(null);
    };
    xhr.onabort = () => {
      toast("已取消上传", "info");
      state.uploadRetry = null;
      resolve(null);
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

function onAttachSelected(event, isGroup) {
  const input = event.target;
  sendFiles(input.files, isGroup);
  input.value = "";
}

function bindFileDrop(form, isGroup) {
  form.addEventListener("dragover", (event) => {
    event.preventDefault();
    form.classList.add("composer-dragging");
  });
  form.addEventListener("dragleave", () => {
    form.classList.remove("composer-dragging");
  });
  form.addEventListener("drop", (event) => {
    event.preventDefault();
    form.classList.remove("composer-dragging");
    const files = event.dataTransfer && event.dataTransfer.files;
    if (files && files.length) sendFiles(files, isGroup);
  });
}

function bindPasteUpload(input, isGroup) {
  input.addEventListener("paste", (event) => {
    const text = event.clipboardData
      ? event.clipboardData.getData("text")
      : "";
    if (text.length + input.value.length > 2000) {
      toast("消息过长，已按 2000 字上限截断", "info");
    }
    const items = event.clipboardData && event.clipboardData.items;
    if (!items) return;
    const files = Array.from(items)
      .filter((item) => item.kind === "file")
      .map((item) => item.getAsFile())
      .filter((file) => file instanceof File);
    if (files.length) {
      event.preventDefault();
      sendFiles(files, isGroup);
    }
  });
}

function voiceFormat(seconds) {
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return `${minutes}:${rest}`;
}

function renderVoiceState() {
  const active = state.recording.active;
  const isGroup = state.recording.isGroup;
  const button = document.getElementById(isGroup ? "group-voice-btn" : "voice-btn");
  if (button) {
    button.classList.toggle("voice-recording", active);
    button.setAttribute("aria-label", active ? "停止录音" : "按住说话");
  }
  const timer = document.getElementById(isGroup ? "group-voice-timer" : "voice-timer");
  if (timer) {
    timer.hidden = !active;
    timer.textContent = active ? voiceFormat(state.recording.seconds) : "";
  }
}

function updateVoiceTimer() {
  state.recording.seconds += 1;
  renderVoiceState();
}

async function toggleVoice(isGroup) {
  if (state.recording.active) {
    stopVoice();
    return;
  }
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    toast("当前浏览器不支持录音", "error");
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    toast("无法访问麦克风，请检查浏览器权限", "error");
    return;
  }
  const mimeType =
    window.MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "audio/webm";
  let recorder;
  try {
    recorder = new MediaRecorder(stream, { mimeType });
  } catch {
    recorder = new MediaRecorder(stream);
  }
  const chunks = [];
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size) chunks.push(event.data);
  });
  recorder.addEventListener("stop", () => {
    stream.getTracks().forEach((track) => track.stop());
    state.recording.active = false;
    renderVoiceState();
    const type = recorder.mimeType || "audio/webm";
    const extension = type.includes("mp4") ? "m4a" : "webm";
    const blob = new Blob(chunks, { type });
    if (blob.size === 0) {
      toast("没有录制到声音", "error");
      return;
    }
    sendFiles([new File([blob], `语音消息.${extension}`, { type })], isGroup);
  });
  recorder.start();
  state.recording = {
    active: true,
    recorder,
    isGroup,
    seconds: 0,
    timer: window.setInterval(updateVoiceTimer, 1000),
  };
  renderVoiceState();
}

function stopVoice() {
  const recording = state.recording;
  if (!recording.active) return;
  recording.active = false;
  if (recording.timer) window.clearInterval(recording.timer);
  try {
    recording.recorder.stop();
  } catch {
    /* 已停止 */
  }
  renderVoiceState();
}

function toggleEmojiPanel() {
  state.emojiOpen = !state.emojiOpen;
  renderEmojiPanel();
}

function renderEmojiPanel() {
  const panel = document.getElementById(
    state.activeGroupId !== null ? "group-emoji-panel" : "emoji-panel"
  );
  if (!panel) return;
  panel.hidden = !state.emojiOpen;
  if (!state.emojiOpen) return;
  panel.innerHTML = Object.entries(EMOJI_SETS)
    .map(
      ([category, emojis]) => `<div class="emoji-category">
        <span class="emoji-category-name">${escapeHtml(category)}</span>
        <div class="emoji-grid">${emojis
          .map(
            (emoji) =>
              `<button class="emoji-option" type="button" data-emoji="${emoji}">${emoji}</button>`
          )
          .join("")}</div>
      </div>`
    )
    .join("");
}

function insertEmoji(emoji) {
  const input =
    state.activeGroupId !== null
      ? document.getElementById("group-message-input")
      : document.getElementById("message-input");
  if (!input) return;
  const start = input.selectionStart ?? input.value.length;
  const end = input.selectionEnd ?? input.value.length;
  input.value = input.value.slice(0, start) + emoji + input.value.slice(end);
  const caret = start + emoji.length;
  input.setSelectionRange(caret, caret);
  input.focus();
  autoGrowInput(input);
  saveDraftDebounced(input.value);
}

function bindEmojiPanel(buttonId, panelId) {
  document.getElementById(buttonId).addEventListener("click", (event) => {
    event.stopPropagation();
    toggleEmojiPanel();
  });
  document.getElementById(panelId).addEventListener("click", (event) => {
    const option = event.target.closest(".emoji-option");
    if (!option) return;
    insertEmoji(option.dataset.emoji);
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

function fileSizeLabel(size) {
  if (size === null || size === undefined) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function loadGroupFiles(before) {
  if (state.activeGroupId === null) return;
  const epoch = state.conversationEpoch;
  let url = `/api/groups/${state.activeGroupId}/files?limit=30`;
  if (before) url += `&before=${before}`;
  const response = await api(url);
  if (!response.ok) return;
  if (epoch !== state.conversationEpoch) return;
  const body = await response.json();
  if (before) {
    state.groupFiles = state.groupFiles.concat(body.files);
  } else {
    state.groupFiles = body.files;
  }
  state.groupFilesNext = body.next_before;
  renderGroupFiles();
}

function renderGroupFiles() {
  const list = document.getElementById("group-files-list");
  if (!list) return;
  const empty = document.getElementById("group-files-empty");
  const items = state.groupFiles
    .map((file) => {
      const icon = file.mime && file.mime.startsWith("audio/") ? "🎵" : "📎";
      const time = new Date(file.created_at).toLocaleDateString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
      return `<li class="contact-item">
        <a class="contact-button group-file-link" href="${escapeHtml(file.url || "")}" download>
          <span class="contact-main">
            <span class="contact-name">${icon} ${escapeHtml(file.name || "附件")}</span>
            <span class="contact-preview">${fileSizeLabel(file.size)} · ${escapeHtml(time)}</span>
          </span>
        </a>
      </li>`;
    })
    .join("");
  const more = state.groupFilesNext
    ? `<li class="contact-item"><button class="btn btn-ghost btn-sm" type="button"
        data-action="group-files-more" data-before="${state.groupFilesNext}">加载更多</button></li>`
    : "";
  list.innerHTML = items + more;
  if (empty) empty.hidden = state.groupFiles.length > 0;
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

function pollOptionRowHtml(index) {
  return `<label class="sr-only" for="poll-option-${index}">选项 ${index + 1}</label>
    <input id="poll-option-${index}" class="input poll-option-input" maxlength="60"
      placeholder="选项 ${index + 1}" />`;
}

function openPollModal() {
  if (!state.activeGroupId) return;
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="poll-modal" role="dialog" aria-modal="true">
      <form id="poll-form" class="modal-card">
        <h3 class="modal-title">发起投票</h3>
        <label class="sr-only" for="poll-question">投票问题</label>
        <input id="poll-question" class="input" maxlength="120" placeholder="投票问题" />
        <div id="poll-options">${pollOptionRowHtml(0)}${pollOptionRowHtml(1)}</div>
        <div class="poll-modal-row">
          <button class="btn btn-ghost btn-sm" type="button" id="poll-add-option">＋ 添加选项</button>
          <label class="notify-row">
            <input type="checkbox" id="poll-multiple" />
            <span>允许多选</span>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-poll">取消</button>
          <button class="btn btn-primary" type="submit">发起</button>
        </div>
      </form>
    </div>`
  );
  let optionCount = 2;
  const modal = document.getElementById("poll-modal");
  document.getElementById("poll-add-option").addEventListener("click", () => {
    if (optionCount >= 10) {
      toast("最多 10 个选项", "error");
      return;
    }
    document
      .getElementById("poll-options")
      .insertAdjacentHTML("beforeend", pollOptionRowHtml(optionCount));
    optionCount += 1;
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-poll']")) {
      modal.remove();
    }
  });
  document.getElementById("poll-form").addEventListener("submit", onPollSubmit);
  document.getElementById("poll-question").focus();
}

async function onPollSubmit(event) {
  event.preventDefault();
  const question = document.getElementById("poll-question").value.trim();
  const options = Array.from(document.querySelectorAll(".poll-option-input"))
    .map((input) => input.value.trim())
    .filter(Boolean);
  const multiple = document.getElementById("poll-multiple").checked;
  const response = await api(`/api/groups/${state.activeGroupId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      content: "",
      content_type: "poll",
      poll: { question, options, multiple },
    }),
  });
  if (response.ok) {
    document.getElementById("poll-modal").remove();
    toast("投票已发起", "success");
  }
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
    toast("群聊已创建", "success");
  }
}

async function onGroupPanelClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const groupId = state.activeGroupId;
  if (groupId === null) return;
  const action = button.dataset.action;
  if (action === "toggle-select") {
    toggleSelectMode();
    return;
  }
  if (action === "group-files-more") {
    await loadGroupFiles(Number(button.dataset.before));
    return;
  }
  if (action === "group-rename") {
    const name = document.getElementById("group-rename-input").value.trim();
    if (!name) return;
    const response = await api(`/api/groups/${groupId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    if (response.ok) toast("群名称已更新", "success");
  } else if (action === "group-invite") {
    const sub = document.getElementById("group-invite-select").value;
    if (!sub) return;
    const response = await api(`/api/groups/${groupId}/members`, {
      method: "POST",
      body: JSON.stringify({ member_subs: [sub] }),
    });
    if (response.ok) toast("已邀请新成员", "success");
  } else if (action === "group-announcement") {
    const text = document.getElementById("group-announcement-input").value.trim();
    const response = await api(`/api/groups/${groupId}/announcement`, {
      method: "PATCH",
      body: JSON.stringify({ text }),
    });
    if (response.ok) toast("公告已发布", "success");
  } else if (action === "group-remove") {
    confirmModal("移除成员", "移除后该成员将无法再查看群消息。", async () => {
      const response = await api(`/api/groups/${groupId}/members/${encodeURIComponent(button.dataset.sub)}`, {
        method: "DELETE",
      });
      if (response.ok) toast("已移除成员", "success");
      await refreshGroups();
    }, "移除");
    return;
  } else if (action === "group-toggle-admin") {
    const response = await api(`/api/groups/${groupId}/members/${encodeURIComponent(button.dataset.sub)}`, {
      method: "PATCH",
      body: JSON.stringify({ role: button.dataset.role === "admin" ? "member" : "admin" }),
    });
    if (response.ok) toast("角色已更新", "success");
  } else if (action === "group-mute") {
    const muted = button.dataset.muted === "true";
    const response = await api(
      `/api/groups/${groupId}/members/${encodeURIComponent(button.dataset.sub)}/mute`,
      {
        method: "PATCH",
        body: JSON.stringify({ muted: !muted }),
      }
    );
    if (response.ok) toast(muted ? "已解除禁言" : "已禁言该成员", "success");
  } else if (action === "group-transfer") {
    const response = await api(`/api/groups/${groupId}/transfer`, {
      method: "POST",
      body: JSON.stringify({ new_owner_sub: button.dataset.sub }),
    });
    if (response.ok) toast("群主已转让", "success");
  } else if (action === "group-leave") {
    confirmModal("退出群聊", "退出后将无法查看该群消息。", async () => {
      const response = await api(`/api/groups/${groupId}/leave`, { method: "POST" });
      if (response.ok) {
        closeGroupPanel();
        await refreshGroups();
        toast("已退出群聊", "success");
      }
    }, "退出");
    return;
  } else if (action === "group-dissolve") {
    confirmModal(
      "解散群聊",
      "解散后群聊与全部消息将永久删除，且无法恢复。确定要解散吗？",
      async () => {
        const response = await api(`/api/groups/${groupId}/dissolve`, { method: "POST" });
        if (response.ok) {
          closeGroupPanel();
          await refreshGroups();
          toast("群聊已解散", "success");
        }
      },
      "解散"
    );
    return;
  }
  await refreshGroups();
}

async function openChat(sub, locateId = null) {
  if (state.recording.active) stopVoice();
  exitSelectMode();
  state.conversationEpoch += 1;
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
  state.replyTo = null;
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
    <span class="chat-peer-actions">
      <button class="icon-btn" type="button" data-action="friend-remark"
        aria-label="设置备注">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>
      <button class="icon-btn" type="button" data-action="friend-delete"
        aria-label="删除好友">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 6h18"/>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
          <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>
      </button>
      <button class="icon-btn" type="button" data-action="call-audio"
        aria-label="语音通话">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.08 4.18 2 2 0 0 1 4.06 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>
        </svg>
      </button>
      <button class="icon-btn" type="button" data-action="call-video"
        aria-label="视频通话">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M23 7l-7 5 7 5V7z"/>
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
        </svg>
      </button>
      <button class="icon-btn" type="button" data-action="toggle-select" aria-label="多选消息">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 11l3 3L22 4"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
      </button>
    </span>
    <span id="typing-hint" class="typing-hint" hidden>正在输入…</span>`;
  clearTypingHint();
  const messageInput = document.getElementById("message-input");
  messageInput.value = "";
  autoGrowInput(messageInput);
  loadDraft();
  document.getElementById("load-older").hidden = true;
  renderMessages();
  document.getElementById("app").classList.add("chat-open");
  await loadHistory();
  await markReadActive();
  if (locateId) await locateMessage(locateId);
  if (window.innerWidth >= 768) document.getElementById("message-input").focus();
}

async function markReadActive() {
  if (!state.activeSub || state.messages.length === 0) return;
  const epoch = state.conversationEpoch;
  const last = state.messages[state.messages.length - 1];
  const response = await api(
    `/api/conversations/${encodeURIComponent(state.activeSub)}/read`,
    { method: "POST", body: JSON.stringify({ last_read_id: last.id }) }
  );
  if (response.ok && epoch === state.conversationEpoch) {
    clearUnread(state.activeSub, last.id);
  }
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
  const epoch = state.conversationEpoch;
  let url = `/api/conversations/${encodeURIComponent(state.activeSub)}/messages?limit=50`;
  if (before) url += `&before=${before}`;
  try {
    const response = await api(url);
    if (!response.ok) return;
    if (epoch !== state.conversationEpoch) return;
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

async function reconcileMessages() {
  let url;
  if (state.activeGroupId !== null) {
    url = `/api/groups/${state.activeGroupId}/messages?limit=50`;
  } else if (state.activeSub) {
    url = `/api/conversations/${encodeURIComponent(state.activeSub)}/messages?limit=50`;
  } else {
    return;
  }
  const response = await api(url);
  if (!response.ok) return;
  const page = await response.json();
  const existing = new Map(state.messages.map((message) => [message.id, message]));
  let changed = false;
  for (const fresh of page.messages) {
    const current = existing.get(fresh.id);
    if (current) {
      if (JSON.stringify(current) !== JSON.stringify(fresh)) {
        existing.set(fresh.id, fresh);
        changed = true;
      }
    } else {
      state.messages.push(fresh);
      changed = true;
    }
  }
  if (changed) renderMessages();
}

function closeChat() {
  if (state.recording.active) stopVoice();
  exitSelectMode();
  state.conversationEpoch += 1;
  sendTyping("stop");
  state.editingId = null;
  state.replyTo = null;
  state.activeSub = null;
  state.activePeer = null;
  state.messages = [];
  state.nextBefore = null;
  document.getElementById("chat-empty").hidden = false;
  document.getElementById("chat-active").hidden = true;
  document.getElementById("app").classList.remove("chat-open");
}

function messageHtml(message, previous) {
  const own = message.sender_sub === state.me.sub;
  const sending = message.status === "sending";
  const failed = message.status === "failed";
  const mentioned = (message.mentions || []).includes(state.me.sub);
  const readByPeer = state.readUpTo[state.activeSub];
  const read = own && typeof readByPeer === "number" && message.id <= readByPeer;
  const time = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const day = dayLabel(message.created_at);
  const previousDay = previous ? dayLabel(previous.created_at) : null;
  const dayDivider =
    day !== previousDay ? `<div class="message-day">${escapeHtml(day)}</div>` : "";
  const sameAuthor = Boolean(
    previous &&
      previous.sender_sub === message.sender_sub &&
      !previous.deleted &&
      !message.deleted
  );
  const closeInTime = Boolean(
    previous &&
      new Date(message.created_at).getTime() -
        new Date(previous.created_at).getTime() <
        5 * 60 * 1000
  );
  const merged = Boolean(sameAuthor && closeInTime && previousDay === day);
  const senderHeader = (() => {
    if (own || state.activeGroupId === null) return "";
    const sender = groupMemberMap().get(message.sender_sub) || {
      sub: message.sender_sub,
    };
    return `<div class="message-sender">
      ${avatarHtml(sender)}
      <span class="message-sender-name">${escapeHtml(displayName(sender))}</span>
    </div>`;
  })();
  const replyPreview = message.reply_to
    ? `<div class="message-reply-preview">${
        message.reply_to.deleted
          ? "消息已撤回"
          : escapeHtml(message.reply_to.content || "")
      }</div>`
    : "";
  let body;
  if (message.deleted) {
    body = '<div class="message-bubble message-bubble-deleted">消息已撤回</div>';
  } else if (message.content_type === "image" && message.attachment) {
    body = `<div class="message-bubble message-bubble-attachment">
      ${replyPreview}
      <img class="attachment-image" src="${escapeHtml(message.attachment.url)}"
        alt="图片消息" loading="lazy" />
      ${message.content
        ? `<div class="attachment-caption">${escapeHtml(message.content)}</div>`
        : ""}
    </div>`;
  } else if (message.content_type === "audio" && message.attachment) {
    body = `<div class="message-bubble message-bubble-attachment">
      ${replyPreview}
      <audio class="voice-player" controls preload="metadata"
        src="${escapeHtml(message.attachment.url)}"></audio>
      ${message.content
        ? `<div class="attachment-caption">${escapeHtml(message.content)}</div>`
        : ""}
    </div>`;
  } else if (message.content_type === "poll" && message.poll) {
    body = `<div class="message-bubble message-poll">${replyPreview}${pollCardHtml(message.poll)}</div>`;
  } else if (message.attachment) {
    body = `<div class="message-bubble message-bubble-attachment">
      ${replyPreview}
      <a class="attachment-link" href="${escapeHtml(message.attachment.url)}" download>
        📎 ${escapeHtml(message.attachment.name)}</a>
      ${message.content
        ? `<div class="attachment-caption">${escapeHtml(message.content)}</div>`
        : ""}
    </div>`;
  } else {
    body = `<div class="message-bubble${sending ? " message-sending" : ""}${
      failed ? " message-failed" : ""
    }">${sending ? '<span class="message-spinner" aria-label="发送中"></span>' : ""}${
      replyPreview
    }${escapeHtml(message.content)}</div>`;
  }
  const editActions =
    own && !sending && !failed
      ? `<button class="message-action" type="button"
          data-action="edit" data-id="${message.id}">编辑</button>
         <button class="message-action" type="button"
          data-action="withdraw" data-id="${message.id}">撤回</button>`
      : "";
  const retryAction = failed
    ? `<button class="message-action" type="button"
        data-action="retry-send" data-id="${message.id}">重试</button>`
    : "";
  const hideAction = !message.status
    ? `<button class="message-action" type="button"
        data-action="hide-message" data-id="${message.id}">删除</button>`
    : "";
  const actions = !message.deleted
    ? `<span class="message-actions">${editActions}
        ${retryAction}
        ${hideAction}
        <button class="message-action" type="button"
          data-action="forward" data-id="${message.id}">转发</button>
        <button class="message-action${message.starred ? " message-star-on" : ""}" type="button"
          data-action="star" data-id="${message.id}">${message.starred ? "取消收藏" : "收藏"}</button>
        <button class="message-action" type="button"
          data-action="reply" data-id="${message.id}">回复</button>
      </span>`
    : "";
  const editedMark = !message.deleted && message.edited_at
    ? '<span class="message-read">已编辑</span>'
    : "";
  const forwardMark = message.forwarded
    ? '<span class="message-read">已转发</span>'
    : "";
  const mentionMark = mentioned ? '<span class="message-read">@我</span>' : "";
  const statusText = sending
    ? '<span class="message-read">发送中…</span>'
    : failed
      ? '<span class="message-read message-failed-text">发送失败</span>'
      : "";
  const groupReadInfo =
    own && state.activeGroupId !== null
      ? `<button class="message-action" type="button"
          data-action="show-reads" data-id="${message.id}">${
          message.read_count || 0
        } 人已读</button>`
      : "";
  const reactions = message.deleted ? "" : reactionsHtml(message);
  const selectCheck =
    state.selectMode && !message.deleted
      ? `<button class="message-check${
          state.selectedIds.includes(message.id) ? " message-check-on" : ""
        }" type="button" data-action="select-message" data-id="${message.id}"
          aria-label="选择消息">✓</button>`
      : "";
  return `<div class="message ${own ? "message-own" : "message-other"}${
    mentioned ? " message-mentioned" : ""
  }${merged ? " message-merged" : ""}" data-message-id="${message.id}">
    ${dayDivider}
    ${senderHeader}
    ${selectCheck}
    ${body}
    <div class="message-meta">${escapeHtml(time)}${statusText}${read
      ? '<span class="message-read">已读</span>'
      : ""}${editedMark}${forwardMark}${mentionMark}${groupReadInfo}${actions}</div>
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

function isGroupManager() {
  const group = state.activeGroup;
  if (!group || !state.me) return false;
  const member = group.members.find((item) => item.user.sub === state.me.sub);
  return Boolean(member && (member.role === "owner" || member.role === "admin"));
}

function pollCardHtml(poll) {
  const total = poll.total_votes || 0;
  const closed = poll.closed;
  const options = (poll.options || [])
    .map((option) => {
      const percent = total > 0 ? Math.round((option.count / total) * 100) : 0;
      const selected = (poll.my_votes || []).includes(option.index);
      return `<button class="poll-option${selected ? " poll-option-selected" : ""}"
        type="button" data-action="poll-vote" data-poll="${poll.id}"
        data-index="${option.index}" data-multiple="${poll.multiple}"
        ${closed ? "disabled" : ""}>
        <span class="poll-option-bar" style="width:${percent}%"></span>
        <span class="poll-option-text">${escapeHtml(option.text)}</span>
        <span class="poll-option-count">${option.count} 票 · ${percent}%</span>
      </button>`;
    })
    .join("");
  const closeButton =
    !closed && (poll.creator_sub === state.me.sub || isGroupManager())
      ? `<button class="btn btn-ghost btn-sm" type="button"
          data-action="poll-close" data-poll="${poll.id}">结束投票</button>`
      : "";
  return `<div class="poll-card">
    <div class="poll-question">📊 ${escapeHtml(poll.question)}</div>
    <div class="poll-options">${options}</div>
    <div class="poll-footer">
      <span class="poll-meta">${total} 人参与${closed ? " · 已结束" : ""}${
        poll.multiple ? " · 可多选" : ""
      }</span>
      ${closeButton}
    </div>
  </div>`;
}

function closeImageKeydown(event) {
  if (event.key !== "Escape") return;
  const viewer = document.getElementById("image-viewer");
  if (!viewer) return;
  viewer.remove();
  document.removeEventListener("keydown", closeImageKeydown);
}

function openImageViewer(src) {
  const existing = document.getElementById("image-viewer");
  if (existing) existing.remove();
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="image-viewer" id="image-viewer" role="dialog" aria-modal="true"
      aria-label="图片查看器">
      <button class="image-viewer-close" type="button"
        data-action="close-image-viewer" aria-label="关闭查看器">×</button>
      <img class="image-viewer-img" src="${escapeHtml(src)}" alt="查看大图" />
    </div>`
  );
  const viewer = document.getElementById("image-viewer");
  const close = () => {
    viewer.remove();
    document.removeEventListener("keydown", closeImageKeydown);
  };
  viewer.addEventListener("click", (event) => {
    if (
      event.target === viewer ||
      event.target.closest("[data-action='close-image-viewer']")
    ) {
      close();
    }
  });
  document.addEventListener("keydown", closeImageKeydown);
}

function renderMessages() {
  const container = messagesContainer();
  if (!container) return;
  container.classList.toggle("select-active", state.selectMode);
  const sortKey = (message) =>
    typeof message.id === "number" ? message.id : Number.MAX_SAFE_INTEGER;
  const sorted = state.messages
    .slice()
    .sort((a, b) => sortKey(a) - sortKey(b));
  if (sorted.length === 0) {
    container.innerHTML = '<div class="messages-empty">还没有消息，打个招呼吧</div>';
    return;
  }
  if (sorted.length <= RENDER_CHUNK_SIZE) {
    container.innerHTML = sorted
      .map((message, index) => messageHtml(message, sorted[index - 1]))
      .join("");
    return;
  }
  container.innerHTML = "";
  let index = 0;
  const renderChunk = () => {
    const chunk = sorted.slice(index, index + RENDER_CHUNK_SIZE);
    if (chunk.length === 0) {
      container.scrollTop = container.scrollHeight;
      return;
    }
    const html = chunk
      .map((message, offset) =>
        messageHtml(message, sorted[index + offset - 1])
      )
      .join("");
    container.insertAdjacentHTML("beforeend", html);
    index += chunk.length;
    requestAnimationFrame(renderChunk);
  };
  renderChunk();
}

function appendMessage(message) {
  if (state.messages.some((item) => item.id === message.id)) return;
  const previous = state.messages[state.messages.length - 1];
  state.messages.push(message);
  const container = messagesContainer();
  if (!container) return;
  container.insertAdjacentHTML("beforeend", messageHtml(message, previous));
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
  const epoch = state.conversationEpoch;
  let url = `/api/groups/${state.activeGroupId}/messages?limit=50`;
  if (before) url += `&before=${before}`;
  try {
    const response = await api(url);
    if (!response.ok) return;
    if (epoch !== state.conversationEpoch) return;
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
  const epoch = state.conversationEpoch;
  const last = state.messages[state.messages.length - 1];
  const response = await api(`/api/groups/${state.activeGroupId}/read`, {
    method: "POST",
    body: JSON.stringify({ last_read_id: last.id }),
  });
  if (response.ok && epoch === state.conversationEpoch) {
    clearGroupUnread(state.activeGroupId, last.id);
  }
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

async function locateMessage(messageId) {
  state.locateMessageId = messageId;
  await ensureMessageLoaded(messageId, 0);
  scrollToMessage(messageId);
}

async function ensureMessageLoaded(messageId, depth) {
  if (!messageId || depth >= 20) return;
  if (state.messages.some((item) => item.id === messageId)) return;
  if (!state.nextBefore) return;
  if (state.activeGroupId !== null) await loadGroupHistory(state.nextBefore);
  else await loadHistory(state.nextBefore);
  await ensureMessageLoaded(messageId, depth + 1);
}

function scrollToMessage(messageId) {
  const container = messagesContainer();
  if (!container) return;
  const element = container.querySelector(`[data-message-id="${messageId}"]`);
  if (!element) return;
  element.scrollIntoView({ block: "center" });
  element.classList.remove("message-flash");
  void element.offsetWidth;
  element.classList.add("message-flash");
  window.setTimeout(() => element.classList.remove("message-flash"), 1600);
}

function toggleSelectMode() {
  state.selectMode = !state.selectMode;
  state.selectedIds = [];
  renderMessages();
  renderSelectBar();
}

function exitSelectMode() {
  if (state.selectMode) toggleSelectMode();
}

function renderSelectBar() {
  let bar = document.getElementById("select-bar");
  if (!state.selectMode) {
    if (bar) bar.remove();
    return;
  }
  if (!bar) {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div class="select-bar" id="select-bar">
        <span id="select-count" class="select-count">已选 0 条</span>
        <button class="btn btn-ghost btn-sm" type="button" id="select-cancel">取消</button>
        <button class="btn btn-primary btn-sm" type="button" id="select-forward" disabled>转发</button>
      </div>`
    );
    bar = document.getElementById("select-bar");
    document.getElementById("select-cancel").addEventListener("click", toggleSelectMode);
    document.getElementById("select-forward").addEventListener("click", () => {
      const messages = state.messages.filter(
        (message) => state.selectedIds.includes(message.id) && !message.deleted
      );
      if (messages.length) openForwardModal(messages);
    });
  }
  document.getElementById("select-count").textContent = `已选 ${state.selectedIds.length} 条`;
  document.getElementById("select-forward").disabled = state.selectedIds.length === 0;
}

async function onGroupComposerSubmit(event) {
  event.preventDefault();
  const input = document.getElementById("group-message-input");
  const content = input.value.trim();
  if (!content || !state.activeGroupId) return;
  const editingId = state.editingId;
  let local = null;
  if (!editingId) {
    local = localMessage(content);
    state.messages.push(local);
    renderMessages();
    const container = messagesContainer();
    if (container) container.scrollTop = container.scrollHeight;
  }
  const url = editingId
    ? `/api/groups/${state.activeGroupId}/messages/${editingId}`
    : `/api/groups/${state.activeGroupId}/messages`;
  const body = { content };
  if (!editingId && state.replyTo) body.reply_to_id = state.replyTo.id;
  if (!editingId) body.mentions = state.mentionSubs;
  const response = await api(url, {
    method: editingId ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
  if (response.ok) {
    if (local) removeLocal(local);
    clearReply();
    state.editingId = null;
    input.placeholder = "输入消息";
    state.mentionSubs = [];
    state.mentionOpen = false;
    const mentionList = document.getElementById("group-mention-list");
    if (mentionList) mentionList.hidden = true;
    input.value = "";
    saveDraft("");
    autoGrowInput(input);
    input.focus();
  } else if (local) {
    local.status = "failed";
    renderMessages();
  }
}

function toggleMentionList() {
  state.mentionOpen = !state.mentionOpen;
  renderMentionList();
}

function renderMentionList() {
  const list = document.getElementById("group-mention-list");
  if (!list) return;
  list.hidden = !state.mentionOpen;
  if (!state.mentionOpen) return;
  const members = state.activeGroup
    ? state.activeGroup.members.filter((member) => member.user.sub !== state.me.sub)
    : [];
  list.innerHTML = members
    .map(
      (member) => `<button class="mention-option" type="button"
        data-sub="${escapeHtml(member.user.sub)}">@${escapeHtml(displayName(member.user))}</button>`
    )
    .join("") || '<span class="muted">没有可提及的成员</span>';
}

function onMentionPick(event) {
  const button = event.target.closest(".mention-option[data-sub]");
  if (!button) return;
  const sub = button.dataset.sub;
  const member = state.activeGroup.members.find((item) => item.user.sub === sub);
  if (!member) return;
  if (!state.mentionSubs.includes(sub)) state.mentionSubs.push(sub);
  const input = document.getElementById("group-message-input");
  const label = `@${displayName(member.user)} `;
  input.value = input.value ? `${input.value}${label}` : label;
  input.focus();
  state.mentionOpen = false;
  renderMentionList();
}

function onGroupComposerKeydown(event) {
  if (event.key === "Escape" && state.editingId) {
    cancelEditing();
    return;
  }
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    document.getElementById("group-composer").requestSubmit();
  }
}

function onComposerBarClick(event) {
  const button = event.target.closest("[data-action='cancel-reply']");
  if (button) clearReply();
}

function setReply(message) {
  state.replyTo = {
    id: message.id,
    text: message.deleted ? "消息已撤回" : message.content || "",
  };
  renderReplyBars();
}

function clearReply() {
  state.replyTo = null;
  renderReplyBars();
}

function renderReplyBars() {
  for (const id of ["message-reply-bar", "group-reply-bar"]) {
    const bar = document.getElementById(id);
    if (!bar) continue;
    bar.hidden = !state.replyTo;
    if (state.replyTo) {
      bar.querySelector(".reply-bar-text").textContent = state.replyTo.text;
    }
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
  let local = null;
  if (!editingId) {
    local = localMessage(content);
    state.messages.push(local);
    renderMessages();
    const container = messagesContainer();
    if (container) container.scrollTop = container.scrollHeight;
  }
  const url = editingId
    ? `/api/conversations/${encodeURIComponent(state.activeSub)}/messages/${editingId}`
    : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`;
  const body = { content };
  if (!editingId && state.replyTo) body.reply_to_id = state.replyTo.id;
  const response = await api(url, {
    method: editingId ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
  if (response.ok) {
    if (local) removeLocal(local);
    state.editingId = null;
    clearReply();
    input.value = "";
    saveDraft("");
    autoGrowInput(input);
    input.placeholder = "输入消息";
    input.focus();
  } else if (local) {
    local.status = "failed";
    renderMessages();
  }
}

async function onMessagesClick(event) {
  if (state.selectMode) {
    const check = event.target.closest("[data-action='select-message']");
    if (!check) return;
    const id = Number(check.dataset.id);
    const index = state.selectedIds.indexOf(id);
    if (index >= 0) {
      state.selectedIds.splice(index, 1);
    } else {
      state.selectedIds.push(id);
    }
    renderMessages();
    renderSelectBar();
    return;
  }
  const image = event.target.closest(".attachment-image");
  if (image && image.src) {
    openImageViewer(image.src);
    return;
  }
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const messageId = button.dataset.id;
  if (button.dataset.action === "reply") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (message && !message.deleted) {
      setReply(message);
      const input = state.activeGroupId
        ? document.getElementById("group-message-input")
        : document.getElementById("message-input");
      if (input) input.focus();
    }
    return;
  }
  if (button.dataset.action === "forward") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (message && !message.deleted) openForwardModal(message);
    return;
  }
  if (button.dataset.action === "star") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (!message || message.deleted) return;
    const url = `/api/messages/${messageId}/star`;
    const response = await api(url, {
      method: message.starred ? "DELETE" : "PUT",
    });
    if (response.ok) {
      message.starred = !message.starred;
      renderMessages();
      toast(message.starred ? "已收藏" : "已取消收藏", "success");
    }
    return;
  }
  const sub = state.activeSub;
  const groupId = state.activeGroupId;
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
    const url = groupId
      ? `/api/groups/${groupId}/messages/${messageId}/reactions`
      : `/api/conversations/${encodeURIComponent(sub)}/messages/${messageId}/reactions`;
    await api(url, {
      method: mine ? "DELETE" : "PUT",
      body: mine ? undefined : JSON.stringify({ emoji }),
    });
    state.pickerMessageId = null;
    return;
  }
  if (button.dataset.action === "poll-vote") {
    const pollId = Number(button.dataset.poll);
    const index = Number(button.dataset.index);
    const message = state.messages.find(
      (item) => item.poll && item.poll.id === pollId
    );
    const poll = message && message.poll;
    if (!poll || poll.closed || !state.activeGroupId) return;
    let indexes;
    if (poll.multiple) {
      const current = poll.my_votes || [];
      indexes = current.includes(index)
        ? current.filter((item) => item !== index)
        : [...current, index];
    } else {
      indexes = [index];
    }
    const response = await api(
      `/api/groups/${state.activeGroupId}/polls/${pollId}/vote`,
      { method: "PUT", body: JSON.stringify({ option_indexes: indexes }) }
    );
    if (response.ok) {
      if (message) message.poll = await response.json();
      renderMessages();
    }
    return;
  }
  if (button.dataset.action === "poll-close") {
    const pollId = Number(button.dataset.poll);
    if (!state.activeGroupId) return;
    const response = await api(
      `/api/groups/${state.activeGroupId}/polls/${pollId}/close`,
      { method: "POST" }
    );
    if (response.ok) {
      const message = state.messages.find(
        (item) => item.poll && item.poll.id === pollId
      );
      if (message) message.poll = await response.json();
      renderMessages();
      toast("投票已结束", "success");
    }
    return;
  }
  if (button.dataset.action === "show-reads") {
    await openReadsModal(Number(messageId));
    return;
  }
  if (button.dataset.action === "hide-message") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (!message) return;
    confirmModal(
      "删除消息",
      "仅从你的会话中删除这条消息，对方仍然可见。",
      async () => {
        const url =
          state.activeGroupId !== null
            ? `/api/groups/${state.activeGroupId}/messages/${messageId}/me`
            : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages/${messageId}/me`;
        const response = await api(url, { method: "DELETE" });
        if (response.ok) {
          state.messages = state.messages.filter(
            (item) => String(item.id) !== messageId
          );
          renderMessages();
          toast("已从你的会话中删除", "success");
        }
      },
      "删除"
    );
    return;
  }
  if (button.dataset.action === "retry-send") {
    const local = state.messages.find((item) => item.id === button.dataset.id);
    if (!local || (!state.activeSub && state.activeGroupId === null)) return;
    local.status = "sending";
    renderMessages();
    const url =
      state.activeGroupId !== null
        ? `/api/groups/${state.activeGroupId}/messages`
        : `/api/conversations/${encodeURIComponent(state.activeSub)}/messages`;
    const response = await api(url, {
      method: "POST",
      body: JSON.stringify({ content: local.content }),
    });
    if (response.ok) {
      removeLocal(local);
    } else {
      local.status = "failed";
      renderMessages();
    }
    return;
  }
  if (button.dataset.action !== "edit" && button.dataset.action !== "withdraw") return;
  if (!sub && !groupId) return;
  if (button.dataset.action === "edit") {
    const message = state.messages.find((item) => String(item.id) === messageId);
    if (!message || message.deleted) return;
    state.editingId = message.id;
    const input = groupId
      ? document.getElementById("group-message-input")
      : document.getElementById("message-input");
    input.value = message.content;
    input.placeholder = "正在编辑，Enter 保存";
    input.focus();
    return;
  }
  const url = groupId
    ? `/api/groups/${groupId}/messages/${messageId}`
    : `/api/conversations/${encodeURIComponent(sub)}/messages/${messageId}`;
  confirmModal("撤回消息", "撤回后对方将无法看到此消息。", async () => {
    const response = await api(url, { method: "DELETE" });
    if (!response.ok && response.status === 409) {
      if (groupId) await loadGroupHistory();
      else await loadHistory();
    }
  }, "撤回");
}

function openForwardModal(messages) {
  const list = Array.isArray(messages) ? messages : [messages];
  state.forwardMessageIds = list.map((message) => message.id);
  const friends = state.friends
    .map(
      (friend) => `<li class="contact-item">
        <button class="forward-target contact-button" type="button"
          data-kind="dm" data-target="${escapeHtml(friend.sub)}">
          ${avatarHtml(friend)}
          <span class="contact-name">${escapeHtml(displayName(friend))}</span>
        </button>
      </li>`
    )
    .join("");
  const groups = state.groups
    .map(
      (group) => `<li class="contact-item">
        <button class="forward-target contact-button" type="button"
          data-kind="group" data-target="${group.id}">
          <div class="avatar avatar-placeholder group-avatar" aria-hidden="true">#</div>
          <span class="contact-name">群：${escapeHtml(group.name)}</span>
        </button>
      </li>`
    )
    .join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="forward-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">转发给</h3>
        <ul class="contact-list forward-list">${friends}${groups}</ul>
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-forward">取消</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("forward-modal");
  modal.addEventListener("click", async (event) => {
    const target = event.target.closest(".forward-target");
    if (target) {
      const url =
        target.dataset.kind === "group"
          ? `/api/groups/${target.dataset.target}/forward`
          : `/api/conversations/${encodeURIComponent(target.dataset.target)}/forward`;
      let done = 0;
      for (const id of state.forwardMessageIds) {
        const response = await api(url, {
          method: "POST",
          body: JSON.stringify({ message_id: id }),
        });
        if (response.ok) done += 1;
      }
      if (done > 0) {
        modal.remove();
        if (state.selectMode) toggleSelectMode();
        toast(done === 1 ? "已转发" : `已转发 ${done} 条`, "success");
      }
      return;
    }
    if (event.target === modal || event.target.closest("[data-action='close-forward']")) {
      modal.remove();
    }
  });
}

async function openReadsModal(messageId) {
  if (!state.activeGroupId) return;
  const response = await api(
    `/api/groups/${state.activeGroupId}/messages/${messageId}/reads`
  );
  if (!response.ok) return;
  const body = await response.json();
  const rows = body.readers
    .map(
      (reader) => `<li class="contact-item">
        ${avatarHtml(reader)}
        <span class="contact-name">${escapeHtml(displayName(reader))}</span>
      </li>`
    )
    .join("");
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="reads-modal" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">已读 ${body.read_count}/${body.total_members}</h3>
        <ul class="contact-list forward-list">${
          rows || '<li class="sidebar-empty">还没有人已读</li>'
        }</ul>
        <div class="modal-actions">
          <button class="btn btn-primary" type="button" data-action="close-reads">关闭</button>
        </div>
      </div>
    </div>`
  );
  const modal = document.getElementById("reads-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-reads']")) {
      modal.remove();
    }
  });
}

function applyGroupReadReceipt(bySub, lastReadId) {
  for (const message of state.messages) {
    if (message.sender_sub !== state.me.sub || message.id > lastReadId) continue;
    if (!state.groupReadBy[message.id]) state.groupReadBy[message.id] = new Set();
    if (!state.groupReadBy[message.id].has(bySub)) {
      state.groupReadBy[message.id].add(bySub);
      message.read_count = (message.read_count || 0) + 1;
    }
  }
  renderMessages();
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
  const input = state.activeGroupId
    ? document.getElementById("group-message-input")
    : document.getElementById("message-input");
  input.value = "";
  autoGrowInput(input);
  input.placeholder = "输入消息";
}

function onComposerInput() {
  sendTyping("start");
  const input = document.getElementById("message-input");
  autoGrowInput(input);
  updateCharCount(input, "char-count");
  saveDraftDebounced(input.value);
}

function onComposerBlur() {
  sendTyping("stop");
}

function autoGrowInput(input) {
  if (!input) return;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

function updateCharCount(input, counterId) {
  const counter = document.getElementById(counterId);
  if (!counter || !input) return;
  const remaining = 2000 - input.value.length;
  counter.hidden = remaining > 200;
  counter.textContent =
    remaining >= 0 ? `还可输入 ${remaining} 字` : `超出 ${-remaining} 字`;
  counter.classList.toggle("char-count-over", remaining < 0);
}

function draftKey() {
  if (state.activeGroupId !== null) {
    return `lichat-draft:group:${state.activeGroupId}`;
  }
  if (state.activeSub) {
    return `lichat-draft:dm:${state.activeSub}`;
  }
  return null;
}

function saveDraft(value) {
  const key = draftKey();
  if (!key) return;
  if (value) {
    localStorage.setItem(key, value);
  } else {
    localStorage.removeItem(key);
  }
}

function saveDraftDebounced(value) {
  if (draftTimer) window.clearTimeout(draftTimer);
  draftTimer = window.setTimeout(() => saveDraft(value), 300);
}

function loadDraft() {
  const key = draftKey();
  const input =
    state.activeGroupId !== null
      ? document.getElementById("group-message-input")
      : document.getElementById("message-input");
  if (!key || !input) return;
  const draft = localStorage.getItem(key) || "";
  if (draft) {
    input.value = draft;
    autoGrowInput(input);
  }
}

function handleServerMessage(data) {
  if (data.type === "message" && data.message) {
    const message = data.message;
    if (message.sender_sub !== state.me.sub) notifyMessage(message);
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
    if (data.group_id != null && data.group_id === state.activeGroupId) {
      applyGroupReadReceipt(data.by_sub, data.last_read_id);
    } else if (data.peer_sub === state.activeSub) {
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
  } else if (data.type === "poll_event" && data.poll) {
    const target = state.messages.find(
      (item) => item.poll && item.poll.id === data.poll.id
    );
    if (target) {
      target.poll = data.poll;
      renderMessages();
    }
  } else if (data.type === "call") {
    handleCallSignal(data);
  } else if (data.type === "group_event") {
    if (data.event === "dissolved") {
      state.groups = state.groups.filter((group) => group.id !== data.group_id);
      if (state.activeGroupId === data.group_id) closeGroupPanel();
      toast("群聊已解散", "info");
      renderSidebar();
    } else if (
      (data.event === "member_removed" || data.event === "member_left") &&
      data.group &&
      Array.isArray(data.group.members)
    ) {
      const stillMember = data.group.members.some(
        (member) => member.user.sub === state.me.sub
      );
      if (!stillMember) {
        state.groups = state.groups.filter((group) => group.id !== data.group_id);
        if (state.activeGroupId === data.group_id) closeGroupPanel();
        toast("你已不在该群聊中", "info");
        renderSidebar();
      } else {
        refreshGroups();
      }
    } else if (data.event === "role_changed" && data.group) {
      const myRow = data.group.members.find(
        (member) => member.user.sub === state.me.sub
      );
      if (myRow) toast(`你的角色已变更为 ${roleLabel(myRow.role)}`, "info");
      refreshGroups();
    } else {
      refreshGroups();
    }
  } else if (data.type === "friend_event") {
    refreshSidebar();
  } else if (data.type === "notification" && data.notification) {
    state.notifications.unshift(data.notification);
    state.notificationsUnread += 1;
    updateNotifyBadge();
    renderNotificationsModal();
    toast(notificationText(data.notification), "info");
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

function onChatHeaderClick(event) {
  const remarkButton = event.target.closest("[data-action='friend-remark']");
  if (remarkButton) {
    openRemarkModal(state.activePeer);
    return;
  }
  const deleteButton = event.target.closest("[data-action='friend-delete']");
  if (deleteButton && state.activeSub) {
    confirmModal(
      "删除好友",
      "删除后将解除好友关系，聊天记录会保留。",
      async () => {
        const response = await api(
          `/api/friends/${encodeURIComponent(state.activeSub)}`,
          { method: "DELETE" }
        );
        if (response.ok) {
          closeChat();
          await refreshSidebar();
          toast("已删除好友", "success");
        }
      },
      "删除"
    );
    return;
  }
  const selectButton = event.target.closest("[data-action='toggle-select']");
  if (selectButton) {
    toggleSelectMode();
    return;
  }
  const button = event.target.closest("[data-action^='call-']");
  if (!button || !state.activeSub) return;
  startCall(button.dataset.action === "call-video" ? "video" : "audio");
}

function openRemarkModal(peer) {
  if (!peer) return;
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="remark-modal" role="dialog" aria-modal="true">
      <form id="remark-form" class="modal-card">
        <h3 class="modal-title">设置备注名</h3>
        <p class="muted">仅你自己可见，展示时优先于对方昵称。</p>
        <label class="sr-only" for="remark-input">备注名</label>
        <input id="remark-input" class="input" maxlength="32"
          placeholder="备注名（留空清除）" value="${escapeHtml(peer.remark || "")}" />
        <div class="modal-actions">
          <button class="btn btn-ghost" type="button" data-action="close-remark">取消</button>
          <button class="btn btn-primary" type="submit">保存</button>
        </div>
      </form>
    </div>`
  );
  const modal = document.getElementById("remark-modal");
  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-action='close-remark']")) {
      modal.remove();
    }
  });
  document.getElementById("remark-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const remark = document.getElementById("remark-input").value.trim();
    const response = await api(`/api/friends/${encodeURIComponent(peer.sub)}/remark`, {
      method: "PATCH",
      body: JSON.stringify({ remark }),
    });
    if (response.ok) {
      const body = await response.json();
      peer.remark = body.remark || null;
      const nameElement = document.querySelector(".chat-peer-name");
      if (nameElement) nameElement.textContent = displayName(peer);
      await refreshSidebar();
      modal.remove();
      toast("备注已保存", "success");
    }
  });
  document.getElementById("remark-input").focus();
}

async function startCall(kind) {
  if (state.call || !state.activeSub) return;
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: kind === "video",
    });
  } catch {
    toast("无法访问麦克风/摄像头，请检查浏览器权限", "error");
    return;
  }
  const pc = new RTCPeerConnection();
  state.call = {
    pc,
    peerSub: state.activeSub,
    kind,
    status: "calling",
    incoming: false,
    localStream: stream,
    offer: null,
  };
  wireCallEvents();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  sendCallSignal("offer", pc.localDescription.toJSON(), kind);
  showCallOverlay("呼叫中…");
}

function wireCallEvents() {
  const call = state.call;
  if (!call) return;
  call.pc.onicecandidate = (event) => {
    if (event.candidate) sendCallSignal("ice", event.candidate.toJSON());
  };
  call.pc.ontrack = (event) => {
    const remote = document.getElementById("call-remote");
    if (remote && event.streams[0]) remote.srcObject = event.streams[0];
  };
}

function sendCallSignal(op, payload = {}, kind = null) {
  const call = state.call;
  const peer = call ? call.peerSub : state.activeSub;
  if (!peer || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  const frame = { type: "call", op, to: peer, payload };
  if (kind) frame.kind = kind;
  state.ws.send(JSON.stringify(frame));
}

function showCallOverlay(status) {
  let overlay = document.getElementById("call-overlay");
  if (!overlay) {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<div class="call-overlay" id="call-overlay" role="dialog" aria-modal="true">
        <div class="call-videos">
          <video id="call-local" class="call-video" autoplay muted playsinline></video>
          <video id="call-remote" class="call-video" autoplay playsinline></video>
        </div>
        <div id="call-status" class="call-status"></div>
        <div class="call-actions">
          <button id="call-hangup" class="btn btn-danger" type="button">挂断</button>
        </div>
      </div>`
    );
    overlay = document.getElementById("call-overlay");
    document.getElementById("call-hangup").addEventListener("click", hangUp);
  }
  const local = document.getElementById("call-local");
  if (local && state.call && state.call.localStream) {
    local.srcObject = state.call.localStream;
  }
  setCallStatus(status);
}

function setCallStatus(status) {
  const element = document.getElementById("call-status");
  if (element) element.textContent = status;
}

function hangUp() {
  sendCallSignal("end");
  endCallLocal();
}

function endCallLocal() {
  const call = state.call;
  if (call) {
    if (call.localStream) {
      call.localStream.getTracks().forEach((track) => track.stop());
    }
    if (call.pc) call.pc.close();
  }
  state.call = null;
  const overlay = document.getElementById("call-overlay");
  if (overlay) overlay.remove();
  const incoming = document.getElementById("call-incoming");
  if (incoming) incoming.remove();
}

function handleCallSignal(data) {
  if (data.op === "offer") {
    if (state.call) {
      state.ws.send(
        JSON.stringify({ type: "call", op: "reject", to: data.from, payload: {} })
      );
      return;
    }
    state.call = {
      pc: null,
      peerSub: data.from,
      kind: "unknown",
      status: "incoming",
      incoming: true,
      localStream: null,
      offer: data.payload || {},
    };
    showIncomingCall();
    return;
  }
  const call = state.call;
  if (!call) return;
  if (data.op === "answer") {
    call.pc.setRemoteDescription(data.payload).then(() => {
      call.status = "connected";
      setCallStatus("已接通");
    });
  } else if (data.op === "ice" && data.payload) {
    call.pc.addIceCandidate(data.payload).catch(() => {});
  } else if (data.op === "end" || data.op === "reject") {
    endCallLocal();
  } else if (data.op === "unavailable") {
    setCallStatus("对方不在线");
    endCallLocal();
  } else if (data.op === "busy") {
    setCallStatus("对方忙线中");
    endCallLocal();
  } else if (data.op === "invalid" || data.op === "error") {
    setCallStatus("呼叫失败");
    endCallLocal();
  }
}

function showIncomingCall() {
  const call = state.call;
  if (!call) return;
  const peer =
    state.friends.find((friend) => friend.sub === call.peerSub) || null;
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="modal-overlay" id="call-incoming" role="dialog" aria-modal="true">
      <div class="modal-card">
        <h3 class="modal-title">来电</h3>
        <p>${escapeHtml(peer ? displayName(peer) : call.peerSub)} 邀请你通话</p>
        <div class="modal-actions">
          <button id="call-reject" class="btn btn-ghost" type="button">拒绝</button>
          <button id="call-accept" class="btn btn-primary" type="button">接听</button>
        </div>
      </div>
    </div>`
  );
  document.getElementById("call-reject").addEventListener("click", () => {
    sendCallSignal("reject");
    endCallLocal();
  });
  document.getElementById("call-accept").addEventListener("click", acceptIncomingCall);
}

async function acceptIncomingCall() {
  const call = state.call;
  if (!call) return;
  const incoming = document.getElementById("call-incoming");
  if (incoming) incoming.remove();
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
  } catch {
    toast("无法访问麦克风/摄像头，请检查浏览器权限", "error");
    sendCallSignal("reject");
    endCallLocal();
    return;
  }
  const pc = new RTCPeerConnection();
  call.pc = pc;
  call.localStream = stream;
  call.status = "connecting";
  call.incoming = false;
  wireCallEvents();
  stream.getTracks().forEach((track) => pc.addTrack(track, stream));
  await pc.setRemoteDescription(call.offer);
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  sendCallSignal(
    "answer",
    pc.localDescription.toJSON(),
    call.kind === "unknown" ? "audio" : call.kind
  );
  showCallOverlay("接听中…");
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
  confirmModal("退出登录", "确定要退出当前账号吗？", () => {
    state.loggingOut = true;
    localStorage.removeItem("lichat-session-active");
    localStorage.setItem("lichat-logout", String(Date.now()));
    if (state.wsReconnectTimer) {
      window.clearTimeout(state.wsReconnectTimer);
      state.wsReconnectTimer = null;
    }
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
  }, "退出");
}

function scheduleReconnect() {
  if (state.loggingOut || state.wsReconnectTimer) return;
  const delay = Math.min(30000, 1000 * 2 ** state.wsRetry);
  state.wsRetry += 1;
  const dot = document.getElementById("ws-dot");
  const label = document.getElementById("ws-text");
  if (dot) dot.className = "status-dot status-connecting";
  if (label) label.textContent = `已断开，${Math.round(delay / 1000)} 秒后重连…`;
  state.wsReconnectTimer = window.setTimeout(() => {
    state.wsReconnectTimer = null;
    if (document.visibilityState === "visible") connectWebSocket();
  }, delay);
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

  socket.addEventListener("open", () => {
    state.wsRetry = 0;
    if (state.wsReconnecting) {
      state.wsReconnecting = false;
      toast("已重新连接", "success");
      refreshSidebar();
      reconcileMessages();
    }
    setStatus("connected", "已连接");
  });
  socket.addEventListener("error", () => setStatus("disconnected", "连接已断开"));
  socket.addEventListener("message", (event) => {
    try {
      handleServerMessage(JSON.parse(event.data));
    } catch {
      /* 忽略无法解析的帧 */
    }
  });
  socket.addEventListener("close", (event) => {
    if (state.call) endCallLocal();
    if (event.code === 4401) {
      state.wsReconnecting = false;
      localStorage.removeItem("lichat-session-active");
      localStorage.setItem("lichat-logout", String(Date.now()));
      if (state.loggingOut) {
        setStatus("disconnected", "已退出登录");
        return;
      }
      setStatus("invalid", "已退出登录，正在返回登录页…");
      window.location.href = "/";
      return;
    }
    if (state.loggingOut) return;
    setStatus("disconnected", "连接已断开");
    state.wsReconnecting = true;
    scheduleReconnect();
  });

  state.pingTimer = window.setInterval(() => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "ping" }));
    }
  }, 25000);
}

window.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  const socket = state.ws;
  if (!state.loggingOut && (!socket || socket.readyState === WebSocket.CLOSED)) {
    if (state.wsReconnectTimer) {
      window.clearTimeout(state.wsReconnectTimer);
      state.wsReconnectTimer = null;
    }
    connectWebSocket();
  }
});

window.addEventListener("storage", (event) => {
  if (event.key === "chat-theme") {
    window.LiChatTheme && window.LiChatTheme.initTheme();
    return;
  }
  if (event.key === "lichat-logout" && event.newValue) {
    window.location.href = "/";
    return;
  }
  if (event.key === "lichat-login" && event.newValue) {
    window.location.reload();
  }
});

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
  state.replyTo = null;
  state.groups = [];
  state.activeGroupId = null;
  state.activeGroup = null;
  state.nextBefore = null;
  loadMe();
});

ensureFreshFrontend();
initFocusTracking();
loadMe();
