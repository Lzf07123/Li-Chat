# Li&Chat

基于 OIDC SSO（Li&Pass）的小圈子即时通讯。当前里程碑：统一单点登录——授权码 + PKCE、本地会话、三路径登出、WebSocket 认证桥接。

## 功能

- 通过 Li&Pass 一键登录，本地不存密码，用户资料（昵称/头像/邮箱）自动同步
- HttpOnly 会话 Cookie，滑动 2 小时 / 绝对 7 天
- RP 发起登出与回程登出（门户登出即时踢下线并断开实时连接）
- 同源前端：登录、资料展示、在线状态、心跳保活、退出
- 好友：按昵称/邮箱搜索、申请与处理、列表与解除
- 好友推荐：随机推荐未建立关系的人，一键添加、刷新换一批
- 好友备注名与申请附言：备注名仅自己可见、展示优先；申请可带 ≤200 字附言
- 单聊：纯文本实时收发、历史分页拉取、未读计数与已读回执、消息编辑与撤回、表情回应
- 会话增强：消息引用回复、转发、@提及、收藏、会话置顶与免打扰
- 会话管理：会话归档、草稿自动保存、发送状态与失败重试、消息「仅自己删除」、多选批量转发、
  搜索命中定位高亮、免打扰灰色未读徽标
- 在线状态与正在输入：好友在线圆点、last_seen、输入中提示
- 群聊：建群、成员邀请/移除、群主/管理员角色、转让与退出、群消息与群已读
- 群管理：群公告（发布时间）、群头像、群消息编辑/撤回/表情、成员禁言、群解散、群已读明细
- 群互动：群投票（可多选、可结束）、群文件面板
- 附件与多媒体：图片/文件/语音消息（按住录音）、粘贴/拖拽/多选上传、上传进度与失败重试、
  图片查看器
- 全文搜索：聊天记录关键词检索（命中高亮片段）与联系人搜索
- 个人资料：昵称/简介编辑与头像上传（SSO 资料仅空值回填）、我的数据导出（JSON）
- 通知中心：好友申请/@提及/禁言/角色变更/群解散（铃铛 + 未读角标 + 可选桌面通知）
- 音视频呼叫：WebRTC 1:1 通话（服务端信令中继，媒体 P2P，可配置 STUN/TURN）
- 账号与安全：登录限流、写操作限流、登录设备管理、通话记录
- 体验基座：全局 Toast 错误反馈、WS 指数退避重连与增量补拉、日期分组与连续消息合并、
  骨架屏、键盘快捷键、表情面板、无障碍焦点管理、多标签页协同、明暗主题

## 快速开始

```bash
uv sync --dev
cp .env.example .env   # 填入 Li&Pass 注册的 client_id / client_secret
uv run uvicorn app.main:app --reload
```

浏览器打开 `http://localhost:8000/`。测试套件内置模拟 IdP，无外网依赖。

容器方式：

```bash
docker compose up -d --build   # 默认附带编排内 redis（jti 防重放/跨副本登出广播）
```

详见 [部署指南](docs/deployment.md)。

## 质量门禁

```bash
uv run pytest -q      # 283 个测试
uv run ruff check .
uv run mypy app
```

## 项目结构

```text
app/
├── main.py        # 应用装配、生命周期、/ws、/healthz、静态挂载
├── config.py      # LICHAT_* 环境变量
├── models.py      # users / auth_states / sessions / friendships / messages / dm_reads / reactions / groups / group_members / group_reads / polls / poll_votes / notifications / uploads / call_logs 等 19 张表
├── auth/          # 本地会话与鉴权依赖
├── oidc/          # 依赖方实现（发现、PKCE、令牌校验、用户同步）
├── sso/           # /oidc/* 路由、登出签名、jti 防重放
├── ws/            # WebSocket 连接管理
├── api/           # /api/me、用户搜索、好友与单聊路由、群/投票/通知/导出路由
├── friends/       # 好友业务：搜索、关系状态、申请生命周期
├── messages/      # 消息业务：发送、历史分页、校验、群文件/已读明细
├── polls/         # 群投票业务：创建、投票/改票、关闭、聚合
├── notifications/ # 站内通知：落账、列表、已读
static/            # 同源前端（index.html + app/brand/theme/ambient.js + style.css 令牌）
tests/             # 283 个测试 + 本地模拟 IdP
design-system/     # 品牌设计（chat/ 项目方案 + template/ Li-Design 子模块）
Dockerfile         # 容器镜像（python:3.12-slim + uv，非 root 运行）
docker-compose.yaml # 容器编排（单服务 + SQLite 命名卷）
docs/              # 架构、接口、部署、安全文档
```

## 文档索引

- [架构说明](docs/architecture.md)
- [接口文档](docs/api.md)
- [部署指南](docs/deployment.md)
- [用户指南](docs/user-guide.md)
- [安全设计清单](docs/security.md)
- [OIDC 对接文档](docs/oidc-integration.md)
- [品牌设计报告](design-system/chat/BRAND.md)
- [设计系统速览](design-system/chat/MASTER.md)
- [SSO 设计规格](docs/superpowers/specs/2026-08-15-li-chat-sso-design.md)
- [UI 重构设计规格](docs/superpowers/specs/2026-08-16-li-chat-ui-rebrand-design.md)
- [好友与单聊设计规格](docs/superpowers/specs/2026-08-16-friends-dm-design.md)
- [实施计划](docs/superpowers/plans/2026-08-15-li-chat-sso.md)
- [UI 重构实施计划](docs/superpowers/plans/2026-08-16-li-chat-ui-rebrand.md)
- [好友与单聊实施计划](docs/superpowers/plans/2026-08-16-friends-dm.md)
- [变更记录](CHANGELOG.md)

## 路线图

- [x] 里程碑一：Li&Pass 统一单点登录
- [x] 里程碑二：好友关系与一对一实时聊天
- [x] 里程碑三：群聊、未读/已读、离线推送（群聊与未读/已读已交付；离线推送依赖长连接服务，待定）
- [x] 里程碑四：音视频（WebRTC）与更多扩展（1:1 呼叫信令已交付；群呼叫/媒体服务待定）
- [x] 体验与业务扩展 v21–v70：五阶段各 10 版（体验优化/业务新功能/已有完善/逻辑闭环/收口），
  详见 CHANGELOG 与 docs/superpowers
