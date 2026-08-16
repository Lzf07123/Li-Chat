# Li&Chat 音视频呼叫与语音链路修复实施计划

规格：[../specs/2026-08-16-call-media-fixes-design.md](../specs/2026-08-16-call-media-fixes-design.md)

## Task 1：服务端信令修复

- Consumes：`app/ws/calls.py`、`tests/test_calls.py`
- Produces：offer 中继附带 `kind`；ICE 限频超限静默丢弃（不回 `invalid`）、默认间隔 0.01s；
  回归测试

步骤（TDD）：

- [ ] 红：`test_call_offer_relays_kind`、`test_call_throttled_ice_dropped_silently`
- [ ] 绿：最小实现 `app/ws/calls.py`
- [ ] 全量 `pytest -q` 全绿，独立提交 `fix: 呼叫信令透传 kind 且限频 ICE 静默丢弃`

## Task 2：可配置 ICE 服务器（STUN/TURN）

- Consumes：`app/config.py`、`app/api/users.py`、`tests/test_config.py`、`tests/test_me.py`
- Produces：`LICHAT_RTC_ICE_SERVERS` 解析/校验、`GET /api/me` 回传 `ice_servers`

步骤（TDD）：

- [ ] 红：配置解析与非法值拒绝；`/api/me` 含 `ice_servers`（含非空值）
- [ ] 绿：`Settings.rtc_ice_servers` + `MeOut.ice_servers`
- [ ] 全量验证，独立提交 `feat: 可配置 ICE 服务器（STUN/TURN）`

## Task 3：前端通话修复

- Consumes：`static/app.js`、`tests/test_calls.py`（前端契约用例）
- Produces：ICE 候选缓冲与 flush、来电 kind 区分与媒体约束对齐、iceServers 接线、
  远程视频 play 兜底

步骤（TDD）：

- [ ] 红：前端契约断言（pendingIce/flushPendingIce/iceServers/视频来电 等标记）
- [ ] 绿：最小实现 `static/app.js`
- [ ] 全量验证，独立提交 `fix: 通话前端 ICE 缓冲与音视频类型对齐`

## Task 4：文档收口

- Consumes：`docs/api.md`、`docs/architecture.md`、`docs/security.md`、`docs/deployment.md`、
  `docs/user-guide.md`、`CHANGELOG.md`、`.env.example`
- Produces：协议/字段/环境变量/安全防护与遗留风险同步

步骤：

- [ ] 更新上述文件
- [ ] 独立提交 `docs: 同步通话修复文档与 CHANGELOG`

## 验收

见规格第 5 节；门禁输出（pytest/ruff/mypy）与 `git log --oneline` 作为证据。
