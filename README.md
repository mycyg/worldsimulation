# WorldSim - 多智能体世界推演引擎

> **Warning: This is a toy project.** 一个为了好玩和学习而做的实验性项目，不适用于任何严肃的场景分析或决策参考。

WorldSim 是一个基于 LLM 的多智能体世界推演系统。用户设定一个世界背景（如"AI 替代 85% 白领工作"），系统自动生成数十个社会实体（政府机构、企业、工会、个人等），并在 tick-based 时间轴上模拟它们之间的博弈、反应和演变。

思路参考了 [SillyTavern](https://github.com/SillyTavern/SillyTavern) 的角色卡系统（persona / appearance / speech_style）和 [MiroFish](https://github.com/mycyg/MiroFish) 的多智能体博弈推演机制。

## 核心特性

- **Tick-based 事件驱动模拟** — 每个 tick = 1 个月，实体在精确时间戳上自主行动
- **通用实体命名** — 实体使用真实的社会角色描述（如"国家应急就业管理部门"、"38岁失业财务总监"），而非虚构人名
- **自主决策 + 因果链** — 高影响力实体先行行动，其余实体看到结果后做出反应；低影响力高压实体可触发极端事件
- **混合大事件触发** — 用户自定义规则条件 + LLM 自主判断，双层触发机制
- **可配置参数** — 初始指标（黑暗度/压力/稳定/希望）、结局阈值、大事件触发规则均可自定义
- **实时 WebSocket 推送** — 推演过程中页面实时更新，无需手动刷新
- **知识图谱集成** — 基于 Kuzu 图数据库的实体关系可视化

## 技术栈

| 层 | 技术 |
|---|------|
| Frontend | Vue 3 + Vue Router + Vite |
| Backend | Flask + Flask-SocketIO + SQLAlchemy |
| LLM | 火山引擎 Ark API（兼容 OpenAI 接口） |
| Database | SQLite（关系数据） + Kuzu（图数据库） |
| Memory | Zep（可选，长期记忆管理） |

## 项目结构

```
WorldSim/
├── backend/
│   ├── app.py                  # Flask 应用入口
│   ├── config.py               # 配置管理
│   ├── models/
│   │   └── database.py         # SQLAlchemy 数据模型
│   ├── routes/
│   │   ├── scenario.py         # 场景 CRUD + 文件上传
│   │   ├── entity.py           # 实体管理 + 批量生成
│   │   ├── simulation.py       # 推演控制 + SocketIO 事件
│   │   └── report.py           # 结局报告
│   ├── services/
│   │   ├── simulation_engine.py    # 核心推演引擎（tick 循环）
│   │   ├── entity_generator.py     # LLM 实体生成器
│   │   ├── ending_system.py        # 可配置结局判定
│   │   ├── llm_client.py           # LLM API 客户端
│   │   ├── graphiti_service.py     # 知识图谱服务
│   │   └── zep_service.py          # Zep 记忆服务
│   └── test_smoke.py           # 冒烟测试
├── frontend/
│   ├── src/
│   │   ├── api.js              # API 客户端
│   │   ├── views/
│   │   │   ├── Home.vue        # 首页
│   │   │   ├── Setup.vue       # 场景设置（含高级配置）
│   │   │   ├── Entities.vue    # 实体管理
│   │   │   ├── Simulation.vue  # 推演主界面
│   │   │   └── Report.vue      # 结局报告
│   │   ├── components/
│   │   │   ├── MetricsBar.vue  # 指标条
│   │   │   ├── Timeline.vue    # 时间线
│   │   │   ├── SimControls.vue # 推演控制面板
│   │   │   └── GraphPanel.vue  # 知识图谱面板
│   │   └── styles/
│   │       └── main.css        # 单色主题样式
│   └── vite.config.js
├── data/                       # SQLite DB + 上传文件（运行时生成）
└── .env                        # 环境变量配置
```

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install
```

### 2. 配置环境变量

复制 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
# LLM Configuration (火山引擎 Ark API)
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=your-model-endpoint-id

# Embedding
EMBEDDING_MODEL=your-embedding-endpoint-id

# Zep (可选)
ZEP_API_KEY=your-zep-api-key-here
```

> 也支持任何兼容 OpenAI API 的服务，修改 `LLM_BASE_URL` 即可。

### 3. 启动服务

```bash
# 启动后端（默认端口 5001）
cd backend
python app.py

# 启动前端开发服务器（默认端口 5173）
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173`

### 4. 运行冒烟测试

```bash
cd backend
python test_smoke.py
```

## 使用流程

1. **新建推演** — 填写世界背景、推演问题，配置参数
2. **生成实体** — LLM 根据背景自动生成多阵营实体（含角色卡、压力值、影响力）
3. **启动推演** — 每个 tick 实体自主决策，实时观察局势演变
4. **查看报告** — 推演结束后生成完整分析报告

## 配置项说明

### 时间与推演设置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 时间单位 | 月 | 月或季度 |
| 总时长 | 60 ticks | 推演总步数 |
| 总结间隔 | 6 ticks | 每隔 N 个 tick 生成阶段总结 |

### 初始指标

| 指标 | 默认值 | 含义 |
|------|--------|------|
| 黑暗度 | 0 | 社会黑暗面程度，越高越糟 |
| 压力值 | 0 | 社会整体压力 |
| 稳定度 | 50 | 社会稳定性 |
| 希望值 | 50 | 社会希望指数 |

### 结局条件

| 结局类型 | 触发条件 |
|----------|----------|
| Good End | 希望 >= 阈值 AND 稳定 >= 阈值 |
| Bad End | 黑暗 >= 阈值 OR 压力 >= 阈值 |
| Bittersweet | 希望和黑暗同时较高 |
| Neutral | 到达总时长时的兜底结局 |

### 大事件触发

支持自定义自然语言条件（如"失业率超过15%时触发大规模社会抗议"），以及 LLM 每 3 个 tick 自主判断是否触发重大事件。

## 推演机制

### Tick 循环

```
每个 Tick（= 1 个月）:
  1. 计算当前日期（2026年3月）
  2. 选择活跃实体（Top 影响力 + 轮换）
  3. 两阶段自主决策：
     - 阶段1: 高影响力实体先行行动
     - 阶段2: 其余实体看到结果后反应
  4. 极端事件检查（低影响力 + 高压力实体）
  5. 裁判评估所有行动，更新局势
  6. 更新宏观指标 + 实体状态
  7. 周期性总结（每 N 个 tick）
  8. 检查结局条件
```

### 实体决策

每个实体的决策包含：
- **渴望** — 该实体最想要什么
- **恐惧** — 该实体最害怕什么
- **行动** — 具体做了什么
- **行动类型** — 主动发起 / 被动反应 / 按兵不动

## License

MIT
