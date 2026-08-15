"use strict";

/* 品牌单点：名称 / slogan / Logo / 备案的唯一出处（等价于模板中的 brand.ts）。 */

const LOGO_MARK = `<svg class="logo" viewBox="0 0 48 48" fill="none" aria-hidden="true">
  <rect x="5" y="17" width="18" height="18" rx="5" stroke="currentColor" stroke-width="2.5"/>
  <path d="M23 23 29 15" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
  <rect x="26" y="8" width="17" height="17" rx="5" stroke="currentColor" stroke-width="2.5"/>
  <circle cx="34.5" cy="16.5" r="2.25" fill="currentColor" stroke="none"/>
</svg>`;

window.BRAND = Object.freeze({
  name: "Li&Chat",
  slug: "chat",
  slogan: "一次登录，直连你的小圈子",
  description: "Li&Chat——一次登录，直连你的小圈子",
  icp: "",
  police: "",
  logo: LOGO_MARK,
  footer: function () {
    const parts = [this.name, this.slogan];
    if (this.icp) parts.push(this.icp);
    if (this.police) parts.push(this.police);
    return parts.join(" · ");
  },
});
