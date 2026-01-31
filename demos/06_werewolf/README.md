## 这是一个 Fork

这个仓库是从 OpenAgents 官方仓库 fork 出来的：
https://github.com/openagents-org/openagents

# 🐺 OpenAgents Werewolf Demo (v2.0)- demos/06_werewolf

一个基于 OpenAgents 框架的 6 人局狼人杀游戏 Demo。包含 1 名人类玩家和 5 名由 LLM 驱动的 AI 玩家。

## 📅 最新改动 (2026-01-31)

### 1. AI 交互逻辑重构 (Critical Fix)
- **修复 AI 不响应问题**：`CollaboratorAgent` 默认忽略私信。我们通过自定义 `WerewolfDebugAgent` 重写了 `react` 方法，强制 AI 响应 Direct Message。
- **对标 QQ3 Demo**：
  - 启用 `react_to_all_messages: true`，让 AI 能够监听页面广播。
  - 增加 `reaction_delay: "random(1, 3)"`，模拟真实人类反应延迟。
  - 使用 `model_name: "auto"`，统一调用全局配置的大模型。

### 2. 调试增强 (Debug Agent)
- **新增 `debug_agent.py`**：
  - 一个专门的 Agent 类，继承自标准 Agent。
  - **功能**：在控制台详细打印 LLM 的完整 Prompt、工具调用和响应耗时。
  - **位置**：`src/openagents/mods/games/werewolf/debug_agent.py`。

### 3. 游戏核心逻辑修复
- **GameState 崩溃修复**：通过 Pydantic 数据类补充缺失字段 (`last_words_queue`, `next_phase_after_last_words`)，解决了游戏卡死问题。
- **遗言环节修复**：
  - 修复了 `GamePhase.LAST_WORDS` 枚举缺失导致的 Crash。
  - 修正了 `_process_input` 逻辑，允许**已死亡玩家**在遗言阶段发言（之前会被死人禁言规则拦截）。
- **超时机制调整**：Host 等待时间调整回 **15秒**，配合 AI 的快速响应。

---

## 🎮 游戏功能

### 角色配置
- **玩家人数**: 6人 (1 Human + 5 AI)
- **配置**:
  - 🐺 **狼人** (2人): 夜晚私聊杀人，白天伪装。
  - 🔮 **预言家** (1人): 每晚查验一人身份。
  - 💊 **女巫** (1人): 一瓶解药，一瓶毒药。
  - 👤 **村民** (2人): 无技能，靠逻辑投票。

### 核心机制
- **Host-Driven Flow**: 游戏流程完全由 Host Mod (`mod.py`) 驱动，而非 Agent 自主驱动。大大提升了稳定性。
- **混合阻塞机制**:
  - **AI 玩家**: 超时自动跳过 (Auto-Skip) 或随机行动，防止卡死。
  - **人类玩家**: 必须做出行动才能推进游戏 (Indefinite Blocking)，Host 会一直催促。
- **状态管理**: 完整的状态机管理，支持“第N夜”、“第N天”、“遗言”、“投票”等复杂阶段流转。

---

## 🚀 如何运行

### 前置条件
- Python 3.10+
- OpenAgents 框架已安装
- `.env` 文件配置了 LLM API Key

### 启动步骤 (Windows PowerShell)

1. **启动游戏网络 (Host)**
   ```powershell
   ./start_network.ps1
   ```
   > 此时会启动 OpenAgents Network 和 Werewolf Host Mod。

2. **启动 AI 玩家**
   ```powershell
   ./start_ai_players.ps1
   ```
   > 脚本会启动 5 个 AI 进程。请观察控制台输出，确认 `DEBUG AGENT MODULE LOADED`。

3. **进入游戏 (Web UI)**
   - 打开浏览器访问: [http://localhost:8700/studio](http://localhost:8700/studio)
   - 选择 `werewolf-game` 频道。
   - 发送 **"游戏开始"**。

---

## 🐛 故障排查

| 现象 | 可能原因 | 解决方案 |
|------|----------|----------|
| **AI 不说话/没反应** | 消息没触发 Event | 检查 `debug_agent.py` 是否加载。确认 `ai_player.yaml` 中 `react_to_direct_messages: true`。 |
| **Debug 终端无 LLM 日志** | Agent 类型错误 | 检查 yaml 文件中 `type` 是否为 `openagents.mods.games.werewolf.debug_agent.WerewolfDebugAgent`。 |
| **游戏卡在某个阶段** | Host 报错 | 查看 `start_network.ps1` 的控制台报错信息。 |
| **这是什么奇怪的回复?** | 模型问题 | 检查 `.env` 中的模型配置，建议使用指令遵循能力强的模型 (如 Gemini 2.0 Flash / GPT-4o)。 |

---

## 📂 关键文件结构

```
demos/06_werewolf/
├── start_network.ps1       # 启动脚本 (Host)
├── start_ai_players.ps1    # 启动脚本 (AI)
├── agents/                 # AI 玩家配置 (yaml)
│   ├── ai_player1.yaml     # 张三 (DebugAgent)
│   └── ...
└── src/openagents/mods/games/werewolf/
    ├── mod.py              # 核心游戏逻辑 (Host)
    ├── debug_agent.py      # 自定义 Debug Agent
    ├── game_state.py       # 数据结构
    └── ai_prompts.py       # AI 提示词模板
```
