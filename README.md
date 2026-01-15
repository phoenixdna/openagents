
## 这是一个 Fork

这个仓库是从 OpenAgents 官方仓库 fork 出来的：
https://github.com/openagents-org/openagents

## 我主要改了什么（Demo 01）

我主要调整了 [demos/01_startup_pitch_room](file:///d:/MyProject/openagents/demos/01_startup_pitch_room) 这个演示，把原来的“创业团队群聊”改成了“锵锵三人行 - 创业特别版”的对谈形式：

- 你（用户）只需要在频道里抛出创业想法
- `douwentao` 作为主持人控场并直接回应用户
- `yanglan` 和 `mengfei` 作为嘉宾，主要回应主持人的点名与话题

快速开始（与 Demo 目录 README 基本一致）：

```bash
cd demos/01_startup_pitch_room
openagents network start network.yaml
```

在不同终端分别启动三个角色：

```bash
openagents agent start agents/douwentao.yaml
openagents agent start agents/yanglan.yaml
openagents agent start agents/mengfei.yaml
```
