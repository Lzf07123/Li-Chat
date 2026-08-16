"use strict";

const THEME_KEY = "chat-theme";
const DARK_BG = "#3a3f45";
const LIGHT_BG = "#f6fbf9";

function systemPrefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme) {
  const dark = theme === "dark" || (theme !== "light" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
  return dark ? "dark" : "light";
}

function syncThemeColor(dark) {
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.removeAttribute("media");
    meta.setAttribute("content", dark ? DARK_BG : LIGHT_BG);
  });
}

function initTheme() {
  let saved = null;
  try {
    saved = localStorage.getItem(THEME_KEY);
  } catch {
    saved = null;
  }
  const current = applyTheme(saved);
  const toggle = document.getElementById("theme-toggle");
  if (!toggle) return;
  toggle.setAttribute("aria-label", current === "dark" ? "切换到浅色模式" : "切换到深色模式");
  toggle.addEventListener("click", () => {
    const next = document.documentElement.classList.contains("dark") ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* 隐私模式下忽略 */
    }
    applyTheme(next);
    syncThemeColor(next === "dark");
    toggle.setAttribute("aria-label", next === "dark" ? "切换到浅色模式" : "切换到深色模式");
  });
}

window.LiChatTheme = { THEME_KEY, applyTheme, initTheme };
