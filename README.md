# WorldSim - 多智能体世界推演引擎

> **Warning: This is a toy project.** 一个为了好玩和学习而做的实验性项目，不适用于任何严肃的场景分析或决策参考。

WorldSim 是一个基于 LLM 的多智能体世界推演系统。用户设定一个世界背景（如"AI 替代 85% 白领工作"），系统自动生成数十个社会实体（政府机构、企业、工会、个人等），并在 tick-based 时间轴上模拟它们之间的博弈、反应和演变。

思路参考了 [SillyTavern](https://github.com/SillyTavern/SillyTavern) 的角色卡系统（persona / appearance / speech_style）和 [MiroFish](https://github.com/mycyg/MiroFish) 的多智能体博弈推演机制。

## Screenshots

**推演主界面** — 左侧时间线，中间实时局势播演，右侧实体压力/影响力面板，底部可折叠知识图谱：

![simulation](https://github.com/mycyg/worldsimulation/raw/main/screenshot-sim.png)

**场景设置** — 可配置初始指标、时间参数、结局条件、大事件触发规则：

![setup](https://github.com/mycyg/worldsimulation/raw/main/screenshot-sim2.png)

## 核心特性

- **Tick-based 事件驱动模拟** — 每个 tick = 1 个月，- **通用实体命名** — 实体使用真实社会角色描述，而非虚构人名
- **自主决策 + 因果链** — 高影响力实体先行，其余实体看到结果后反应
- **混合大事件触发** — 用户自定义规则 + LLM 自主判断
- **可配置参数** — 初始指标、结局阈值、大事件触发规则均可自定义
- **实时 WebSocket 推送** — 页面实时更新，无需手动刷新
- **知识图谱集成** — 基于 Kuzu 图数据库的实体关系可视化

## 技术栈

| 层 | 技术 |
|------|------|
| Frontend | Vue 3 + Vue Router + Vite |
| Backend | Flask + Flask-SocketIO + SQLAlchemy |
| LLM | 火山引擎 Ark API（兼容 OpenAI 接口格式） |
| Database | SQLite（关系数据）+ Kuzu（图数据库） |

## 项目结构

```
WorldSim/
├── backend/
│   ├── app.py                         # Flask 应用入口 + SocketIO
│   ├── config.py                      # 环境变量 + 配置管理
│   ├── requirements.txt               # Python 依赖
│   ├── models/
│   │   └── database.py                # SQLAlchemy 数据模型
│   ├── routes/
│   │   ├── scenario.py                # 场景 CRUD + 文件上传
│   │   ├── entity.py                  # 实体管理 + LLM 批量生成
│   │   ├── simulation.py              # 推演控制 + SocketIO
│   │   └── report.py                  # 结局报告
│   ├── services/
│   │   ├── simulation_engine.py       # 核心 tick-based 推演引擎
│   │   ├── entity_generator.py        # LLM 多阵营实体生成器
│   │   ├── ending_system.py           # 可配置结局判定
│   │   ├── llm_client.py             # OpenAI 兼容 LLM 客户端
│   │   ├── report_generator.py        # 推演报告生成器
│   │   ├── graphiti_service.py        # Kuzu 知识图谱服务
│   │   ├── file_parser.py             # PDF/TXT/MD 文件解析
│   │   └── zep_service.py             # Zep 长期记忆服务（可选）
│   └── test_smoke.py                  # 冒烟测试
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js                    # Vue 入口
│       ├── App.vue                    # 根组件
│       ├── api.js                     # API 客户端
│       ├── router/index.js            # 路由配置
│       ├── views/
│       │   ├── Home.vue               # 首页
│       │   ├── Setup.vue              # 场景设置
│       │   ├── Entities.vue           # 实体管理
│       │   ├── Simulation.vue         # 推演主界面
│       │   └── Report.vue             # 结局报告
│       ├── components/
│       │   ├── MetricsBar.vue         # 四大指标条
│       │   ├── Timeline.vue           # 时间线面板
│       │   ├── SimControls.vue        # 推演控制面板
│       │   ├── GraphPanel.vue         # 知识图谱面板
│       │   ├── FactionList.vue        # 阵营列表
│       │   ├── EntityEditor.vue       # 实体编辑抽屉
│       │   ├── FileUpload.vue         # 文件上传
│       │   ├── ToastContainer.vue     # 通知容器
│       │   └── Toast.js               # 通知工具
│       └── styles/
│           └── main.css               # 单色主题
├── data/                            # 运行时生成（SQLite + 上传文件）
└── .env                             # 环境变量（需手动创建）
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Node.js 18+

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 3. 配置环境变量

复制 `.env.example` 并填入你的 LLM API Key：

```bash
cp .env.example .env
```

```ini
# LLM 配置（火山引擎 Ark API 或其他兼容 OpenAI 的服务）
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=your-model-endpoint-id

# Embedding 模型（用于知识图谱，可选）
EMBEDDING_MODEL=your-embedding-endpoint-id

# Flask
FLASK_PORT=5001
FLASK_DEBUG=true
MAX_FILE_SIZE_MB=50
```

> 也支持任何兼容 OpenAI API 的服务，只需修改 `LLM_BASE_URL` 即可。

### 4. 启动服务

```bash
# 启动后端（默认端口 5001）
cd backend
python app.py

# 启动前端（默认端口 5173）
cd frontend
npm run dev
```

浏览器访问 http://localhost:5173

### 5. 运行冒烟测试

```bash
cd backend
python test_smoke.py
```

## 使用流程

```
首页 → 新建推演 → 场景设置 → 生成实体 → 启动推演 → 查看报告
```

1. **新建推演** — 在首页点击"新建推演"创建空场景
2. **场景设置** — 填写世界背景、推演问题，配置参数
3. **生成实体** — LLM 根据背景自动生成多阵营实体
4. **启动推演** — 每个 tick 实体自主决策，实时观察局势演变
5. **查看报告** — 推演结束后生成完整分析报告

## 推演机制详解

### Tick 循环

每个 tick 代表 1 个月，系统按以下步骤运行：

1. 计算当前日期（如 2026年3月）
2. 选择本 tick 活跃实体（按影响力 + 轮换机制选出 5 个）
3. 两阶段自主决策：
   - 阶段 1: Top 3 高影响力实体先行行动（日期 1-15 日）
   - 阶段 2: 其余实体看到阶段 1 结果后做出反应（日期 10-28 日）
4. 极端事件检查 — 低影响力 + 高压力实体有概率触发极端事件
5. 裁判评估 — LLM 评估所有行动的合理性，更新局势和指标
6. 更新宏观指标 + 实体状态
7. 周期性总结 — 每 N 个 tick 生成阶段总结
8. 结局检查 — 检查是否满足结局条件

### 实体决策

每个实体的决策包含完整的行为逻辑：

| 字段 | 说明 |
|------|------|
| 渴望 (desire) | 该实体当前最想要什么 |
| 恐惧 (fear) | 该实体当前最害怕什么 |
| 思考 (thought) | 内心独白，决策前的考量 |
| 行动 (action) | 具体做了什么 |
| 目标 (target) | 行动的目标对象 |
| 行动类型 | `proactive` / `reactive` / `wait` |

### 指标体系

| 指标 | 范围 | 说明 |
|------|------|------|
| 黑暗度 (darkness) | 0-100 | 社会黑暗面程度，越高越糟 |
| 压力值 (pressure) | 0-100 | 社会整体压力水平 |
| 稳定度 (stability) | 0-100 | 社会稳定性 |
| 希望值 (hope) | 0-100 | 社会希望指数 |

### 结局判定

| 结局 | 条件 |
|------|------|
| Good End | 希望 >= 阈值 AND 稳定 >= 阈值 |
| Bad End | 黑暗 >= 阈值 OR 压力 >= 阈值 |
| Bittersweet | 希望和黑暗同时较高 |
| Neutral | 到达总时长，兜底结局 |

所有阈值均可在 Setup 页面自定义。

### 大事件系统

1. **规则触发** — 用户配置的自然语言条件，系统每个 tick 检查
2. **LLM 自主判断** — 每 3 个 tick，LLM 根据局势判断是否触发重大事件

极端事件机制：低影响力（<45）+ 高压力（>=75）的实体有概率触发极端事件，概率 = (pressure - 70) / 50。触发后该实体影响力提升 15-30 点。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scenarios` | 列出所有场景 |
| POST | `/api/scenarios` | 创建场景 |
| GET | `/api/scenarios/:id` | 获取场景详情 |
| PUT | `/api/scenarios/:id` | 更新场景 |
| DELETE | `/api/scenarios/:id` | 删除场景 |
| GET | `/api/scenarios/:id/entities` | 获取实体列表 |
| POST | `/api/scenarios/:id/generate` | LLM 批量生成实体 |
| POST | `/api/scenarios/:id/entities` | 手动添加实体 |
| PUT | `/api/entities/:id` | 编辑实体 |
| DELETE | `/api/entities/:id` | 删除实体 |
| POST | `/api/simulations/:id/start` | 启动推演 |
| POST | `/api/simulations/:id/pause` | 暂停推演 |
| POST | `/api/simulations/:id/resume` | 恢复推演 |
| POST | `/api/simulations/:id/stop` | 停止推演 |
| POST | `/api/simulations/:id/reset` | 重置推演 |
| POST | `/api/simulations/:id/inject` | 注入外部事件 |
| GET | `/api/simulations/:id/state` | 获取推演状态 |
| GET | `/api/simulations/:id/rounds` | 获取 tick 数据 |
| GET | `/api/simulations/:id/timeline` | 获取时间线 |
| POST | `/api/reports/:id/generate` | 生成报告 |
| GET | `/api/reports/:id` | 获取报告 |
| POST | `/api/scenarios/:id/parse-rules` | 从文件提炼规则 |

## WebSocket 事件

| 事件 | 方向 | 说明 |
|------|------|------|
| `join_scenario` | Client → Server | 加入推演房间 |
| `sim:progress` | Server → Client | 推演进度 |
| `sim:round` | Server → Client | 每 tick 完整数据 |
| `sim:metrics` | Server → Client | 四大指标更新 |
| `sim:phase` | Server → Client | 阶段标记 |
| `sim:summary` | Server → Client | 周期性总结 |
| `sim:entity_spawned` | Server → Client | 新实体涌现 |
| `sim:ending` | Server → Client | 结局通知 |
| `sim:error` | Server → Client | 错误通知 |

## 致谢

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 角色卡系统启发
- [MiroFish](https://github.com/mycyg/MiroFish) — 多智能体博弈推演思路启发
- [Claude](https://www.anthropic.com/claude) / [火山引擎 Ark](https://www.volcengine.com/product/ark) — LLM 能力提供
- [Kuzu](https://kuzudb.com/) — 嵌入式图数据库

## License

MIT
