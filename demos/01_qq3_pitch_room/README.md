# Demo 1: “锵锵三人行” 创业特别版
# (Qiang Qiang Trio - Startup Special)

这是一个模拟经典谈话节目“锵锵三人行”的多智能体（Multi-Agent）演示。在这里，AI 扮演三位性格鲜明的角色，与你聊聊创业点子。

## 核心玩法

不同于普通的群聊，这个 Demo 模拟了真实的节目录制现场：

1.  **你（用户）是唯一的“场外观众”或“连线嘉宾”**。
2.  **窦文涛（douwentao）是主持人**，他会直接回应你的话，并负责控场。
3.  **杨澜（yanglan）和孟非（mengfei）是嘉宾**，他们通常不直接回你，而是等着文涛点名，或者在文涛抛出话题后接茬。

## 角色介绍 (Agents)

| Agent ID | 角色 | 风格设定 |
|----------|------|---------|
| `douwentao` | **主持人 / 组局者** | **唯一直接回应用户的 Agent**。负责把你的想法“翻译”成节目话题，点名让杨澜和孟非发表看法，用幽默和松弛感掌控节奏。 |
| `yanglan` | **知性嘉宾** | 优雅、敏锐。关注产品背后的社会价值、人文关怀以及女性视角。只回应窦文涛的话题。 |
| `mengfei` | **犀利嘉宾** | “人间清醒”。负责泼冷水，关注商业落地的现实问题，直来直去。只回应窦文涛的话题。 |

## 快速开始 (Quick Start)

### 1. 启动网络 (Start the Network)

```bash
cd demos/01_startup_pitch_room
openagents network start network.yaml
```

### 2. 启动角色 (Launch the Agents)

请在不同的终端窗口中分别运行：

```bash
# 启动文涛
openagents agent start agents/douwentao.yaml

# 启动杨澜
openagents agent start agents/yanglan.yaml

# 启动孟非
openagents agent start agents/mengfei.yaml
```

### 3. 连接并开始聊天

你可以使用 OpenAgents Studio 或 CLI 连接到 `localhost:8700`。

进入 `pitch-room` 频道，直接说出你的想法：

> **User**: “文涛老师，我想做一个给宠物听的音乐 App，能缓解猫狗焦虑，您觉得有戏吗？”

> **douwentao**: “哎，这个有意思啊！给猫听的莫扎特？咱们今儿就聊聊这个。杨澜，你养过猫吗？你觉得猫听得懂吗？”

> **yanglan**: “我觉得这是个很温暖的想法。现在的都市人把宠物当孩子养，这种情感投射是真实存在的……”

> **mengfei**: “我得泼点冷水啊。猫听不听得懂我不知道，但最后买单的是人。这玩意儿怎么收费？是不是智商税？”

## 示例话题

- “我想做一个专门帮人吵架的 AI 代理。”
- “搞一个共享单车，但是是电动的，还能自动回库。”
- “我想开发一款让人做梦能学英语的枕头。”

## 配置信息

- **Network Port:** 8700
- **Channels:** `pitch-room`
- **Mod:** `openagents.mods.workspace.messaging`

