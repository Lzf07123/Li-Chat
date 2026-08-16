# Li&Chat IM 路线图 v7 实施计划：附件与图片消息

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/config.py`、`app/models.py`、`app/main.py`、`app/messages/service.py`、
  `app/api/messages.py`、`app/api/groups.py`、`tests/conftest.py`、`static/app.js`、
  `static/style.css`、`docs/api.md`、`docs/architecture.md`、`docs/security.md`、
  `docs/deployment.md`、`CHANGELOG.md`
- Produces：`uploads` 表、上传端点（大小/mime 嗅探校验、随机文件名）、鉴权回源端点、
  消息 `content_type/attachment_*` 扩展（单聊 + 群）、前端附件发送与图片渲染、
  `tests/test_uploads.py`

## 步骤（TDD）

- [x] 写失败测试：图片/文件上传回源、超限 413、伪造/非法 mime 415、匿名 401、非上传者 403、
  附件消息与归属校验
- [x] 配置（`LICHAT_UPLOAD_MAX_MB`/`LICHAT_UPLOAD_DIR`）、`Upload` 模型、上传/回源 service
- [x] 消息模型扩展 + `_ensure_message_columns`；发送校验附件归属
- [x] 前端：附件选择上传、图片/文件消息渲染
- [x] 全量验证 pytest / ruff / mypy 全绿（158 通过）
- [x] 独立提交 `feat: 附件上传与图片消息`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md /
  docs/deployment.md

## 验收

见规格 v7 验收清单；门禁输出与 `git show --stat` 作为证据。
