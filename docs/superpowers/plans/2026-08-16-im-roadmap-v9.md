# Li&Chat IM 路线图 v9 实施计划：个人资料与头像

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/models.py`、`app/main.py`、`app/api/users.py`、`app/oidc/user_sync.py`、
  `app/friends/service.py`、`app/api/friends.py`、`static/app.js`、`static/style.css`、
  `tests/test_user_sync.py`、`docs/api.md`、`docs/architecture.md`、`docs/security.md`、
  `CHANGELOG.md`
- Produces：`users.bio` + 兼容迁移、`PATCH /api/me`、`POST /api/me/avatar`、SSO 同步仅
  空值回填、bio 仅好友可见、前端资料编辑弹层与头像上传、`tests/test_profile.py`

## 步骤（TDD）

- [x] 写失败测试：改昵称/简介与校验、头像（非图片 422/他人附件 403）、SSO 不覆盖本地值、
  bio 可见性
- [x] 模型与迁移；user_sync 仅空值回填（同步改 test_user_sync）
- [x] 路由与 friends bio 可见性；前端资料编辑与头像
- [x] 全量验证 pytest / ruff / mypy 全绿（166 通过）
- [x] 独立提交 `feat: 个人资料与头像（SSO 仅空值回填）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md

## 验收

见规格 v9 验收清单；门禁输出与 `git show --stat` 作为证据。
