# Eidos：可复核科研流水线技术框架

**实现基线：4.3.32；同步日期：2026-10-31（Asia/Shanghai）。** 当前状态为 pre-release、有界实证验证；本轮修改尚未提交或推送。测试、覆盖率与链路状态以 docs/SELF_AUDIT.json、docs/HEALTH.md 为准。

旧 v4.1 设计原文已完整归档至 [历史设计](docs/archive/technical-framework-v4.1-2026-10-20.md)。原有“production-ready”“certified results”及代理图示不能作为当前能力证明。

## 1. 实际架构与目标

目标：使研究问题、源码、数据、实验、独立验收和交付之间具有可追踪的执行关系。

```text
projects/*/project.yaml → framework.project → 消费者 gate / test / render
                                └─ numerics: required → 数值 preflight
chain registry → scheduler → sampler → derived verdict → recovery / verify
                                      └─ dashboard / evidence ledger
论文与本地协议 → 实现与独立参考 → 实验/负对照 → 有效性门 → Quarto/图件/数据/代码包
```

编排由确定性链路、注册器、调度器和显式人工关口实现。当前代码 does not use LangGraph / LangChain；Hydra is absent，ChromaDB is removed。具体入口见 [实际编排](docs/ORCHESTRATION.md)，不再把旧设计意图描述成已运行的代理系统。

## 2. 组件与责任

| 层 | 当前入口 | 边界 |
|---|---|---|
| 项目注册 | framework/project.py | 保持外部项目原位，运行其命令、核对输出、保留研究状态；未知/缺失项目不静默通过 |
| 链路调度 | tools/audit_chains.py、tools/refresh_chains.py | 按依赖和间隔执行；缺少可选消费者为 SKIP |
| 状态与恢复 | tools/watch_pipeline.py、tools/status_view.py、tools/serve_site.py、tools/monitor_supervisor.py | 样本新鲜度与序号共同决定健康；OS 生命周期锁、watchdog、事务式热更新；启动尝试与恢复验证分开记录 |
| 科学有效性 | framework/validity/ | 主张必须解析到登记证据；框架门通过不能证明主张普遍为真 |
| 数值验证 | framework/verifiers/numerics.py | 独立 Decimal 定义、实际后端适配、相对误差和负对照；静态筛查是启发式 |
| 数值实现 | framework/stable_numerics.py、framework/stable_numerics_torch.py | 有限 float32/float64；Torch 自定义损失只支持一阶反向 |
| 论文工具 | reference/barron2026_agent/、reference/reproduction/barron2026/mcp/ | 复用已有 Paper2Agent，四个工具及真实调用轨迹；工具可调用不等于复现训练结果 |
| 出版交付 | tools/build_site.py、tools/numerics_case.py、Quarto | 网站、数据、三格式报告和代码包共用证据 |
| 科研图件 | tools/numerics_figure.py、tools/training_figure.py | Python 生成可编辑矢量，浏览器只选择已记录数据 |

模型仅用于路由和判断草稿。未达到验证门槛的模型判断不得成为科学验收。假设、关键设计和最终投稿继续遵守项目人工关口政策。

## 3. 科学验收与自进化

论文机制 → 独立参考 → 可失败的检查 → 负对照 → 可复用实现 → 实际消费者 → CI/回归 → 有范围的交付。

- 区分论文数值复现、实现资格、训练效果复现和科学新发现。
- 不用有限 loss、概率和为 1 或绝对误差下限替代梯度正确性。
- 独立参考按实际可表示输入计算；不能先舍入高精度参考再宣称零误差。
- 保留失败、阴性结果和所有预先指定的种子；预期科学效果不出现不等于执行失败，实验缺失或前提被破坏则必须拒绝。
- 新后端须验收自己的执行路径，不能借用 NumPy 的 PASS。

## 4. Softmax Collapse / Cancellation：修复前后与方案

来源：[A Fix for Softmax and Cross-Entropy, v3](https://arxiv.org/html/2610.31642v3)，发现与方法归 Barron、Gnanapragasam、Tschannen。

| 机制 | 修复前 | 修复方案 | 验收 |
|---|---|---|---|
| Collapse | 高置信度下 q[target]−1 舍入为零；最大值平移只能阻止指数溢出 | 排除一个 argmax 后用 log1p；target 梯度取其他梯度的负和；同时修复前向与反向 | 41 个 gap × 2 个 dtype，逐项检查 loss、梯度及 dtype |
| Cancellation | 近似分布的浮点概率相减失准，相等 logits 也可能产生残差 | teacher logits、中心化差值、expm1/log1p、远分支和零和修正 | 7 个请求扰动 × 2 个 dtype，记录实际扰动，单独检查精确相等 |

共 96 个展示案例，另有 12 项资格检查和 2 个必须被拒绝的负对照。整体 PASS 还须全部展示点通过，错误 loss 不得借用正确梯度的 PASS。float32 gap 18 时，标准 target 梯度为 0，修复约为 −3.046×10⁻⁸。

网页主体必须包含修复前后测量、算法解释、实现入口和下载，不只呈现异常现象。

```python
from framework.stable_numerics_torch import logit_distillation
loss = logit_distillation(student_logits, teacher_logits).mean()
loss.backward()
# 硬标签：hard_cross_entropy(logits, targets).mean()
```

## 5. 实际优化对照：平稳点机制实验

消费者位于 reference/softmax_training/。protocol.json 是执行前保存的本地前瞻协议，不是外部平台注册。

数据为 (a+b) mod 53，共 2,809 个整数对，50% 训练划分；种子 0、1、2。教师为两个线性层及 ReLU 的 MLP，隐藏宽度 128。两种学生精确复制教师权重，并严格验证初始表示 logits 相等；各执行 2,000 步全批次 Adam，T=4，lr=0.002，betas=(0.9,0.98)，eps=1e−8，无 weight decay。

主要终点为参数 L2 位移。标准版约为 0.172161、0.150217、0.181606；修复版全部精确为 0。保存全部种子轨迹、训练/测试指标和模型；CPU 验收器直接读取浮点存储、不执行 pickle 代码，独立重算最终权重位移。

**限制：教师训练准确率为 100%，held-out 仅约 0–0.0712%。此结果支持平稳点/优化漂移的有界机制结论，不支持泛化收益，也未复现原论文高测试准确率。** 三个种子只作描述性比较，不作显著性宣称。

首轮失败已保留：教师先算完整批次再切片，学生直接计算训练批次；CUDA GEMM 造成约 1.05×10⁻⁵ 的初始 logits 差异，破坏前提。docs/failed-batch-shape.zip 包含原始代码、证据和模型。修复为匹配批次的教师缓存及严格相等断言后，才完成修正重跑。

## 6. 本轮逻辑缺口与科学修复

| 缺口 | 已接通的执行/拒绝路径 |
|---|---|
| numerics: required 被执行器忽略 | 注册器枚举校验；gate 前执行 preflight；危险代码即使自身退出 0 也被拒绝 |
| 数值政策拼写错误静默降级 | 非 required/optional/not_applicable 配置拒绝 |
| 抽查 PASS 扩大为完整展示 PASS | 逐点验证；gap 22 的错误梯度和错误 loss 都有失败回归 |
| 极小梯度被绝对阈值掩盖/偷偷降精度 | 相对误差、相对零和残差、输入输出 dtype 保持 |
| 高精度参考提前转 float64 | Decimal 内计算误差后才转换显示值 |
| 缺协议/种子/模型或伪造位移仍可通过 | 完整协议/运行时/源文件/数据划分/模型清单与哈希，独立权重重算 |
| 相同权重被当作相同 logits | 同形状计算路径上 torch.equal，不满足则拒绝实验 |
| 自审忽略 pytest 失败 | 核查真实退出码，失败不覆盖最后有效记录 |
| 热更新失败回退启动旧代码 | 保留最后接受模块，连续成功/失败更新回归 |
| watchdog/PID 文件故障 | 故障路径测试、OS 生命周期锁、受控进程恢复验证 |

通用 preflight 只证明源码筛查和内置数值资格，不认证消费者梯度。实际 Torch/JAX/融合后端仍须进入消费者自己的 gate。

## 7. Nature 图件技术规范

依据 [Nature 官方图件指南](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) 与 [最终提交要求](https://www.nature.com/nature/for-authors/final-submission)：主图宽 183 mm，内核图高 132 mm、训练图高 70 mm，低于 170 mm。图内字号 6–7 pt，本机使用 Arial；PDF 嵌入 TrueType/Type42，SVG 保留可编辑文字，主图不栅格化。

白底出版画布使用蓝/朱红/黑配合实/虚/点线，黑色高对比文字；面板依次 a–d。真实零值在对数轴外标记，不制造正数地板。训练 KL 的 symlog 线性区明确标注。确定性网格无统计误差条；训练展示全部种子。PNG 仅用于 Word 和预览。

规格记录为 site/reports/numerics/figure-policy.json。网页与出版母版分别生成：网页使用原站深色背景、12 px SVG 图中文字与响应式坐标，出版母版保留白底及实际物理尺寸，供独立下载。网页不再嵌入白底静态图，也不把网页截图当出版母版。

Figure 1 联动 failure mode × dtype × 实测输入：a 为当前案例的有符号梯度，b 为整段实测误差与选中游标；Collapse 显示相对 L2 误差，Cancellation 显示绝对 L2 误差。滑块、选择器、表格与读数同步。对数轴中的精确零值有独立轨道；Δ=0 不伪造对数横坐标。Figure 2 支持 seed × endpoint × scale × Adam step 与 standard/fixed 显隐；只读取归档检查点，保留完整轨迹与游标。全部组合均来自实测，没有在浏览器重新计算 softmax 或伪造未运行的实验参数。375–1440 px 宽度下验证无页面横向溢出。

出版图内精确零使用面板内计数注释，避免轴下标记与刻度重叠；Cancellation 的近教师面板直接显示相对梯度误差。技术规格符合公开要求不代表 Nature 编辑部认可研究结论。

## 8. 单源交付、环境与运行

生成入口为 tools/build_site.py；禁止手改 site/index.html。tools/numerics_case.py --render 生成 HTML/PDF/DOCX，以及共用证据的 JSON/CSV、矢量图、训练轨迹、协议、失败档案和带校验和的源码包。包内保留原有 Agent/MCP 与训练模型；CPU 可复核已保存权重，重新训练须具备记录的 CUDA 环境。

源码当前在 E:/2026-AI4S/Eidos，勿假定为会话的 D 盘目录。项目环境在 C:/Users/Administrator/.venvs/eidos-py312（Python 3.12.4），源码盘为 exFAT USB。声明 Python >=3.11；使用 uv.lock 的 locked sync，不做无目的升级。

Git 对源代码采用 LF；对绑定原始 SHA256 的训练证据、检查点和截图所绑定的生成页面保留原始字节，防止 Windows/Linux 换行转换破坏验收。提交前从 Git index 导出独立副本，重新运行模型和分析证据验收；只在原工作区通过不足以证明克隆后可复核。

首轮远端 CI 暴露两项跨平台验收问题：Linux/Windows 的 NumPy `log1p` 结果相差 1 ULP，原 MCP 烟雾测试却要求实数逐位相同；浏览器任务用 Windows 生成的页面做 Linux 重建一致性比较。现保留 vendor 验证器原文，由 `tools/verify_barron_mcp.py` 为非零 float64 输出采用 1e−14 相对容差、绝对容差 0，精确零与离散字段保持精确断言，报告写明策略。独立梯度资格及负对照标准不变。Linux 同版 NumPy 已复核七个案例；CI 浏览器先在 runner 生成页面，再完整执行布局、对比度、运行与源一致性检查，本地提交钩子仍核验交付页面与截图。

CI 监控页也遵循生产启动顺序：先执行 `tools/watch_pipeline.py` 两次真实采样（间隔 2 秒），再构建 dashboard，使历史图有实际时间区间。新克隆不带忽略的运行状态，不能把未采样的空服务/历史图当完整监控。缺失外部服务如实显示不可观测或失败，页面结构验收不把这些状态改成健康。

本次训练使用 py -3.14：Python 3.14.3、Torch 2.13.0+cu126、NumPy 2.4.1、CUDA 12.6、RTX 4070，关闭 TF32并启用确定性算法。主项目环境不强制安装 Torch，可选模块 SKIP 与 GPU 环境的单独 PASS 分别记录；.venv-repro 保留给原有论文 JAX 消费者。

```text
python -m pytest tests/ -q
python tools/record_self_audit.py
python tools/audit_numerics.py --projects
python -m framework.project check barron2026_agent
python -m framework.project check softmax_training
python tools/build_site.py
python tools/numerics_case.py --render
python tools/audit_site.py --no-build
python tools/check_render.py --json
python tools/health.py --json
```

命令使用 AGENTS.md 指定的项目解释器。重新训练用已验证的 GPU 解释器：py -3.14 reference/softmax_training/train.py。常规 gate 读取并核验一次训练的证据，不在调度轮询中反复训练。

监控为 http://127.0.0.1:8765/，案例为 /index.html#demo。健康须有新鲜样本和递增 seq；沿用现有 Startup 入口，不重复部署启动器。24 小时观察写入 .scratch/quality/soak-24h.json，运行中为 RUNNING，不能写为 PASS；受控进程恢复不等于整机登录重启验证。

Consumers 改为桌面三列、中屏两列、手机单列的原生卡片，不再把七个消费者压缩到同一 SVG 横栏。`prose_lie` 是应当被 Gate S 拒绝的负对照（文本 19 与证据 1 冲突）：新鲜且实际判为 FAIL 时显示 Expected rejection，不能把它描述为科研通过。负对照按实际核验时间计时，保留旧证据时间；正项目按证据生成时间计时。监控取最旧消费者，未知时间不伪装新鲜；年龄原值参与阈值判断。轮询与手动核验都会更新消费者卡片。

首页注册表使用同一新鲜度规则：实际 gate 检查必须与退出码一致，才记录本次核验；缺失时间仍为 STALE。静态过期文案不含逐小时变化的年龄，防止证据和状态均未改变时产生无意义的页面漂移。

2026-10-31 的 24 小时观察已记录两次失败，日志显示开发期间旧进程加载的新 dashboard 找不到旧缓存 project 模块中的 `consumer_freshness`。监督进程重启后恢复；失败记录保留，此轮严格连续观察不能宣称全通过。

## 9. 未验证范围与下一步

完整论文参数表、AMP/bfloat16、高阶求导及其他后端仍未验证；有限指数范围和输入量化不可恢复。覆盖率以框架源码范围测量，薄弱路径不能被测试代码覆盖率掩盖。

三种子 Transformer 跟进实验与完整结果见 [SOFTMAX-TRAINING-FOLLOWUP](docs/SOFTMAX-TRAINING-FOLLOWUP.md)。10,000 epoch 重建未获得达标教师；显式登记的探索性 50,000 epoch 延长获得三名超过预设 95% held-out 阈值的教师，并完成精确初始教师蒸馏对照。延长实验与父实验六条轨迹在 10,000 epoch 的模型哈希完全相同；后续沿用优化器，但原始优化器矩未单独保存供独立验证。原实验和不利结果全部保留，不能声称整篇论文 MATCH 或普遍泛化优越性。

验收器核对源/协议/运行时/划分/完整模型清单、原始张量、独立最终准确率、margin、CE、蒸馏位移及父实验重放。此前“删掉产物清单仍可通过”的漏洞有真实报告变异测试覆盖。单独分析脚本 `tools/grokking_analysis.py` 补测最终检查点 target 梯度为零的比例，绑定模型、实验与分析代码哈希；不冒充未记录的梯度时间轨迹。这些跟进结果独立归档，主页 Figure 2 仍明确展示原 MLP 平稳点案例。

下一阶段登记完整 dtype × epsilon 参数矩阵和跨种子设计，核对原论文未明确的实现选择，再判断泛化结果的可迁移性；保留所有阶段的成功、阴性与失败证据。新科学主张仍须文献对照、可证伪假设和独立数据支持。当前全量本地验收为 527 passed、3 个可选 Torch 模块 skipped；CUDA 环境另有 12 passed，框架源码覆盖率 67%，11 条链为 10 PASS/1 SKIP。

相关记录：[质量复核](docs/QUALITY-2026-10-31.md)、[案例说明](docs/CASE-SOFTMAX.md)、[健康](docs/HEALTH.md)、[编排](docs/ORCHESTRATION.md)。
