# Li&Chat 音视频呼叫与语音链路修复设计规格

- 状态：草稿 ｜ 日期：2026-08-16 ｜ 品牌：Li&Chat

## 1. 目标与范围

用户反馈「视频与语音无法正确使用」。排查确认问题集中在 WebRTC 1:1 音视频呼叫链路
（语音消息的录制/上传/回放链路无代码缺陷，见第 6 节），修复目标：

- 通话能稳定建立媒体连接（不因信令缺陷自毁或被叫端丢弃全部 ICE 候选）；
- 视频/语音类型在来电与媒体采集上保持一致（语音来电不请求摄像头）；
- 跨 NAT/跨网呼叫可配置 STUN/TURN（当前无任何 ICE 服务器，仅同网直连可用）。

**范围内**：`app/ws/calls.py`、`app/config.py`、`app/api/users.py`、`static/app.js`、
`tests/`（呼叫回归 + 配置 + 前端契约）、`.env.example` 与相关文档。

**不在范围**：群呼叫、多方会议、服务端媒体中转、TURN 服务自建部署（仅提供配置入口）、
语音消息的服务器端转码（跨浏览器编码差异记为已知限制）。

## 2. 现状与根因（证据）

基线：`pytest -q` 283 项全绿，ruff/mypy 全绿。以下缺陷均由代码审查 + 真实 WS 会话
临时用例复现（`tests/test_call_diag_tmp.py`，诊断后已删）：

1. **`kind` 不透传**：`app/ws/calls.py` 中继帧只有 `op/from/payload`，发起方 offer 附带的
   `kind`（audio/video）被丢弃。被叫端 `static/app.js` 只能把来电当 `"unknown"`，
   「接听」一律 `getUserMedia({audio:true, video:true})`——语音来电也请求摄像头，
   且 answer 回填 kind 固定为 `"audio"`（通话记录依赖 offer 时落账，暂未错账，但类型
   语义已失真）。
2. **ICE 限频回 `invalid` 导致通话自毁**：`handle_call` 对 50ms 内重复 ICE 给发送方回
   `invalid`；前端 `handleCallSignal` 把任何 `invalid/error` 当作「呼叫失败」并
   `endCallLocal()`。浏览器 trickle ICE 常在极短间隔连发候选（host/srflx），等于正常
   呼叫会被自己挂断。已复现：连发两个 ICE，发送方收到 `invalid`。
3. **被叫端丢弃全部主叫 ICE 候选**：来电期间 `state.call.pc` 为 `null`，`handleCallSignal`
   直接 `call.pc.addIceCandidate(...)` 抛 TypeError 被吞掉；主叫的候选在响铃阶段全部
   到齐，因此被叫端永远没有主叫的任何候选 → ICE 连通性检查无对可用 → 即使同网也不通
   媒体，UI 却显示「已接通」。
4. **主叫端 ICE 与 setRemoteDescription 竞态**：answer 分支 `setRemoteDescription(...)`
   的 Promise 未 await，紧跟其后的 ICE 候选可能先于 remoteDescription 设置而
   `addIceCandidate` 失败（InvalidStateError 被吞），首批候选丢失。
5. **无 ICE 服务器配置**：两端 `new RTCPeerConnection()` 不带 `iceServers`，只有 host
   候选；跨 NAT/跨网络（真实小圈子场景）无法建连。当前无任何 STUN/TURN 配置入口。
6. **远程视频自动播放**：异步 `getUserMedia` 消耗用户手势后，远程 `<video autoplay>`
   带声自动播放可能被浏览器策略拦截，需要显式 `play()` 兜底。

## 3. 方案

### 3.1 服务端信令（`app/ws/calls.py`）

- 中继帧在 `op == "offer"` 时附带 `kind`（非法值已收敛为 audio/video）。
- ICE 限频保持滥用防护，但**超限静默丢弃、不再给发送方回 `invalid`**；`invalid` 仅保留给
  真正的状态机非法迁移。默认最小间隔由 0.05s 放宽到 0.01s，降低误伤正常 trickle 候选。

### 3.2 前端通话（`static/app.js`）

- `state.call` 增加 `pendingIce: []`；收到 ICE 一律入队，仅在
  `call.pc.remoteDescription` 就绪后 `flushPendingIce()` 统一应用（覆盖缺陷 3/4 的
  两个方向）。`endCallLocal` 随 `state.call = null` 自然清空队列。
- 来电 `kind` 直接取中继帧的 `data.kind`（缺失回退 `audio`，安全优先不请求摄像头）；
  来电文案区分「视频/语音」，接听媒体约束按 kind 采集，answer 回填真实 kind。
- 两端 `RTCPeerConnection` 使用 `/api/me` 下发的 `ice_servers`（见 3.3）。
- 远程轨道 `ontrack` 里对 remote video 显式 `play().catch(() => {})`，规避自动播放拦截。

### 3.3 ICE 服务器配置（`app/config.py` + `/api/me`）

- 新环境变量 `LICHAT_RTC_ICE_SERVERS`：JSON 数组，每项 `{urls: str|str[], username?,
  credential?}`；`urls` 只允许 `stun:/stuns:/turn:/turns:` 前缀；最多 8 个服务器；
  解析失败或非法值拒绝启动（与 Redis 配置失败同策略，fail-fast）。
- 解析结果随 `GET /api/me` 的 `ice_servers` 字段下发给登录用户（TURN 凭据仅登录后可见，
  不放无鉴权端点）。默认空列表 = 保持现状（仅同网/直连），部署方按需配置。

### 3.4 硬性约束

- 不降级认证/CSRF 契约：`/api/me` 仍走会话鉴权 + `no-store`。
- 信令仍不落库、SDP 不进日志；媒体仍 P2P 不经服务端。
- 默认配置不得引入第三方 STUN（避免未经用户同意的外部服务与 IP 泄露）；仅提供可配置入口。

## 4. 安全影响

- ICE 服务器列表含 TURN 凭据，仅经登录端点下发，属 TURN 正常用法；文档明确凭据可见性。
- 静默丢弃超限 ICE 不降低好友闸/状态机/16KB 载荷限制等既有防护。
- 无 STUN/TURN 时呼叫仍只暴露给通话对端的候选信息，行为与现状一致。

## 5. 验收标准

- 新增回归测试先红后绿：offer 中继含 `kind`；限频 ICE 静默丢弃（双方均无 `invalid`）；
  ICE 服务器配置解析/非法拒绝；`/api/me` 回传 `ice_servers`；前端契约含 ICE 缓冲与
  iceServers 接线标记。
- `pytest -q` 全绿（≥283 项），`ruff check .` 与 `mypy app` 全绿。
- 文档同步：api.md（WS 协议 + `/api/me` 字段）、architecture.md、security.md（防护表 +
  遗留风险）、deployment.md（环境变量表）、user-guide.md、CHANGELOG。

## 6. 语音消息链路结论（不修改）

录音/上传/发送/回放代码链无缺陷（`tests/test_voice.py` 覆盖 webm/mp4 与伪造类型拒绝）。
两点环境性限制需用户知晓：① `getUserMedia/MediaRecorder` 只存在于安全上下文（https 或
localhost），http 局域网 IP 访问时录音与呼叫都无法获取麦克风；② Chrome 录制为
`audio/webm`(opus)，iOS Safari 不能播放该封装，反之 Safari 的 mp4 可被 Chrome 播放——
跨端回放兼容性取决于浏览器能力，需服务端转码才能根治（不在本期范围）。
