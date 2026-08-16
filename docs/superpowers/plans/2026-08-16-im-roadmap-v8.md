# Li&Chat IM 路线图 v8 实施计划：全文搜索

规格：[../specs/2026-08-16-im-roadmap-v1-v10-design.md](../specs/2026-08-16-im-roadmap-v1-v10-design.md)

## Task

- Consumes：`app/messages/service.py`、`app/friends/service.py`、`app/main.py`、
  `static/app.js`、`static/style.css`、`docs/api.md`、`docs/architecture.md`、
  `docs/security.md`、`CHANGELOG.md`
- Produces：`app/search/service.py`、`app/api/search.py`、`GET /api/search?kind=messages|
  contacts`（游标分页 + snippet）、前端用户/消息双模式搜索、`tests/test_search.py`

## 步骤（TDD）

- [x] 写失败测试：命中/分页终止/snippet、权限边界（非群成员搜不到）、已撤回排除、contacts、
  参数校验与鉴权
- [x] service：消息检索（自己可见范围 + 游标）与 contacts 复用
- [x] 路由与前端搜索模式切换
- [x] 全量验证 pytest / ruff / mypy 全绿（163 通过）
- [x] 独立提交 `feat: 全文搜索（消息 + 联系人）`
- [x] 同步 CHANGELOG / docs/api.md / docs/architecture.md / docs/security.md

## 验收

见规格 v8 验收清单；门禁输出与 `git show --stat` 作为证据。
