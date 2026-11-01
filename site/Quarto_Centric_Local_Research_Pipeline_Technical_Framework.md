# Eidos：可复核科研流水线技术框架

**实现基线：0.4.8（初期开发编号迁移；旧 4.x 标签完整保留）；同步日期：2026-11-01（Asia/Shanghai）。** 当前状态为 pre-release、有界实证验证。测试、覆盖率与链路状态以 docs/SELF_AUDIT.json、docs/HEALTH.md 为准；功能完备性见 [验收清单](docs/FUNCTIONAL_COMPLETENESS.md)。

运行部署边界：核查发现现存监控及两条旧链路循环仍使用全局 Python 3.14；本地启动配置已选择项目 Python 3.12，但受控停止/重启被自动审批以 blocked by policy 拒绝，未执行、未改道终止。新增调度循环源码已补 OS 生命周期锁、单次 tick 互斥、隐藏子进程树超时清理及原子心跳；这些规则不会追溯应用到旧进程。运行迁移仍为 PENDING，不能以网页可访问或源码测试通过替代实际部署验收。详见 docs/MONITOR-RUNTIME-MIGRATION-2026-11-01.json。

0.4.4 安全接入与输入绑定修复：发布演练及其缺失输出负控改用独占临时目录，不再覆盖或删除固定同名项目；清理前核对目录身份，替换目录予以保留并报错。失败的接入和覆盖率生成不能沿用旧通过，超时清理覆盖完整子孙进程。消费者快照现绑定 Python 验证入口与显式 validity_inputs（辅助代码、配置、数据）；模块入口缺声明、未知解释器选项或未授权外部文件不能绑定。gate 的必需输出不再误用于实验前的 test 阶段。监控缺包探测不擅自启用 user-site；不可用/非有限测量显式标为 UNOBSERVABLE，并保留诊断、输出有效 JSON；运行标记只读取一次以避免消失竞态。独立 HPAF 接入已用 1,033 条现有记录验证正常报告、坏 JSON 缺输出拒绝、错误计数拒绝及源码/语料变化撤销旧状态；首次过强声明的 S4 拒绝如实保留，未补造预注册。此为接入与绑定证据，不代表完整科研生命周期、科研新颖性或出版验收；见 docs/INDEPENDENT-INTAKE-ACCEPTANCE.json。

**0.4.2 新增交付合同（发布状态另由标签与版本履历证明）：** 通用交付包改为显式文件清单、锁定依赖、复现与验证两步命令、必需输出及种子/数据/配置版本；生成包不再等同于执行通过。新增运行器拒绝旧输出、输入或清单变更以及 Windows 路径别名冲突。独立安装与执行验收、Docker/Binder 状态分别记录于 `docs/PACKAGE-ACCEPTANCE.json`；合同见 [可执行交付](docs/EXECUTABLE-DELIVERY.md)。容器镜像拉取失败不能记为容器验收通过；本轮不扩展既有数值科学结论。

2026-11-01 补充验收：新增独占执行声明与原子执行记录，真实双进程回归只允许一次实验调用；全量测试为 642 passed、4 个可选模块 skipped。新建 Windows 环境和禁用网络的 Linux 容器均通过 12 个数值正例与 2 个故障对照。容器构建使用 AWS ECR 上的官方 Python 镜像及固定摘要覆盖；原 Docker Hub 连接失败仍保留，远端 Binder 和新机器验收未完成。上述为 0.4.2 交付验证；历史 v0.4.1 的自审记录保留在既有标签，不改写为本次结果。

0.4.3 调度环境修复：真实 Hermes 调度器注入的工作区使其 `tools` 包遮蔽 Eidos 工具目录，导致先前手工检查通过、定时任务却连续失败。入口现先读取纯标准库配置，再以项目解释器 `-I -X utf8` 启动，并从转发环境移除 `PYTHONPATH`、`PYTHONHOME`，覆盖普通 Python 子孙进程。保留 stdout/stderr 和退出码，Windows 禁止创建控制台窗口。真实 watchdog 调度已由连续错误恢复为成功；解释器、隔离标志及 `console_window=0` 均来自实际运行记录。证据见 `docs/CRON-SCHEDULER-ACCEPTANCE-2026-11-01.json`；每日 contracts 的定时触发、重新登录和干净 24 小时观察仍独立待验，不以手工调用替代。

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

**实际模型边界：ScienceRSI-8B（Qwen3 架构、Q4_K_M）才是 S4/S7 测评对象**，结构化设计判断为 13/15，留出支持判断为 17/20，均未获准承担科学裁决；不能将这些成绩归给 Llama/Qwen2.5/Gemma。StartLux-Decision-4B 只承担有界类型化路由/分诊，不能代替实验执行或科学门。2026-11-01 本机快照中 llama3.1:8b 与 qwen2.5:14b 缺失，gemma2:9b 已安装但未做 EIDOS 任务资格验收。

StageAwareScheduler 明确候选不是已验收模型组：科学生成默认返回未就绪，只有显式 allow_unqualified_draft 才允许准备草稿；候选按替代关系选择一个，不再全部加载；未知阶段拒绝。experiment_execution 与 evaluation_gates 不加载 LLM。首页新增模型能力与科学权限分区，共源读取原测评记录，并显示快照时间。见 [任务质量与权限](docs/MODEL-TASK-QUALITY.md)。

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

依据 [Nature 官方图件指南](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) 与 [最终提交要求](https://www.nature.com/nature/for-authors/final-submission)：主图宽 183 mm，内核图高 132 mm、平稳点训练图高 70 mm、精度矩阵图高 130 mm，低于 170 mm。图内字号 6–7 pt，本机使用 Arial；PDF 嵌入 TrueType/Type42，SVG 保留可编辑文字，主图不栅格化。

白底出版画布使用蓝/朱红/黑配合实/虚/点线，黑色高对比文字；面板依次 a–d。真实零值在对数轴外标记，不制造正数地板。训练 KL 的 symlog 线性区明确标注。确定性网格无统计误差条；训练展示全部种子。PNG 仅用于 Word 和预览。

规格记录为 site/reports/numerics/figure-policy.json。网页与出版母版分别生成：网页使用原站深色背景、12 px SVG 图中文字与响应式坐标，出版母版保留白底及实际物理尺寸，供独立下载。网页不再嵌入白底静态图，也不把网页截图当出版母版。

Figure 1 联动 failure mode × dtype × 实测输入：a 为当前案例的有符号梯度，b 为整段实测误差与选中游标；Collapse 显示相对 L2 误差，Cancellation 显示绝对 L2 误差。滑块、选择器、表格与读数同步。对数轴中的精确零值有独立轨道；Δ=0 不伪造对数横坐标。Figure 2 支持 seed × endpoint × scale × Adam step 与 standard/fixed 显隐；只读取归档检查点，保留完整轨迹与游标。全部组合均来自实测，没有在浏览器重新计算 softmax 或伪造未运行的实验参数。375–1440 px 宽度下验证无页面横向溢出。

出版图内精确零使用面板内计数注释，避免轴下标记与刻度重叠；Cancellation 的近教师面板直接显示相对梯度误差。技术规格符合公开要求不代表 Nature 编辑部认可研究结论。

## 8. 单源交付、环境与运行

报告生成器统一采用 tools/publication.py：HTML 保持可读的研究报告，PDF/Word 使用 A4、12 pt Times New Roman、双倍行距和连续行号。图表具有明确标题、完整图例、实验单位、统计边界、Methods、Data availability、Code availability 与来源。Word 保留页码、重复表头和行完整性；PDF 处理短表所需空间和重复编号。原始数据、失败及不利结果不为版式而改写。

tools/audit_publication.py 按物理 viewport/viewBox 检查字号、尺寸、矢量文字、PDF 嵌入字体及 Word 样式，输出 docs/PUBLICATION-QA.json。tools/check_publication_record.py 核对交付物与生成器指纹；改变后旧记录失效。完整 PDF/Word 逐页图像检查独立记录，不能由模板导入或 PASS 标签替代。规范与边界见 [出版质量要求](docs/PUBLICATION-QUALITY.md)。作者、单位、贡献、基金及利益冲突须科研团队确认，submission_ready 保持 false。

报告导出与渲染持有目录锁；同线程可重入、跨进程互斥，版本回滚共享同一所有权，ZIP 原子替换。此机制不宣称整个多文件目录对读者原子可见。仍串行执行会写入报告的验收。

当前 0.4.1 属于开发期编号迁移，旧 v4.x 标签保留，不是通常 SemVer 单调升级。版本工具仅同步本地 editable 版本，历史实验锁按哈希原样归档；任何第三方依赖、来源、标记、哈希或字段类型改变均不能借版本迁移放行。源码、README、网站和发布记录须一致；具体顺序见 [发布流程](docs/RELEASES.md)。

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

截至 2026-10-31 22:03（Asia/Shanghai），24 小时观察仍为 RUNNING，约 5.7 小时、342 次观测、18 次不满足严格判据。失败包含此前旧进程缓存/快照悬空问题、本轮发布时的输入绑定切换及一次有意的在线失效探测；记录未重置。当前监控已恢复 OK，但不能宣称严格连续观察通过。输入绑定与自动复核已修复注册变更后沿用旧结论的问题；接入后仍可手动执行 `tools/build_pipeline.py --probe`。见 [运行观察快照](docs/SOAK-OBSERVATION-2026-10-31.json) 和 [在线变异验收](docs/CONSUMER-SNAPSHOT-ACCEPTANCE-2026-10-31.json)。

新增输入绑定：Gate S 核验前后对注册配置、框架源码、主张、报告及声明证据计算哈希；核验过程中变化则不绑定旧结论。输入变化后，监控撤销缓存状态并显示 UNOBSERVABLE，受影响卡片显示 STALE；其他已确认失败仍保留告警。后台单任务自动复核，超时清理所属进程树，五分钟冷却后可重试；采样继续。JSON 原子替换防止读到半写入文件。预期失败消费者按真实复核时间参与每小时刷新选择，避免旧负对照证据垄断队列。该机制不是重跑训练或验证未声明的数据依赖。

整体审查新增 [功能完备性清单](docs/FUNCTIONAL_COMPLETENESS.md)。通用 Docker/Binder 打包尚不完整：旧模板引用未复制的 requirements.txt，且缺少 pyproject.toml、uv.lock 和源码；已验证的案例 ZIP 不能替它证明“一键执行”。下一优先事项为修复通用打包、全新独立项目全流程验收及干净环境安装，不能因单个科学案例通过而宣称框架功能完备。

## 9. 未验证范围与下一步

完整论文参数表、AMP/bfloat16、高阶求导及其他后端仍未验证；有限指数范围和输入量化不可恢复。覆盖率以框架源码范围测量，薄弱路径不能被测试代码覆盖率掩盖。

三种子 Transformer 跟进实验与完整结果见 [SOFTMAX-TRAINING-FOLLOWUP](docs/SOFTMAX-TRAINING-FOLLOWUP.md)。10,000 epoch 重建未获得达标教师；显式登记的探索性 50,000 epoch 延长获得三名超过预设 95% held-out 阈值的教师，并完成精确初始教师蒸馏对照。延长实验与父实验六条轨迹在 10,000 epoch 的模型哈希完全相同；后续沿用优化器，但原始优化器矩未单独保存供独立验证。原实验和不利结果全部保留，不能声称整篇论文 MATCH 或普遍泛化优越性。

验收器核对源/协议/运行时/划分/完整模型清单、原始张量、独立最终准确率、margin、CE、蒸馏位移及父实验重放。此前“删掉产物清单仍可通过”的漏洞有真实报告变异测试覆盖。单独分析脚本 `tools/grokking_analysis.py` 补测最终检查点 target 梯度为零的比例，绑定模型、实验与分析代码哈希；不冒充未记录的梯度时间轨迹。这些跟进结果独立归档，主页 Figure 2 仍明确展示原 MLP 平稳点案例。

本轮已完成受支持精度矩阵：损失入口 float32/float64 × epsilon={1e-8,1e-12,1e-16} × 三种子 × 标准/修复，共 36 条 10,000 epoch 轨迹、1,836 个记录点、72 个最终模型文件。模型前向及参数始终为 FP32；不能把损失入口精度与整个模型精度混淆。bf16 尚未资格化，不计入已完成范围。协议在执行前本地登记，来源、锁文件、初始模型与划分均绑定哈希；六条 FP32/epsilon=1e-8 基线与父实验最终模型逐位相同。

最终权重经 NumPy 独立前向复核；36 个最终梯度端点从原训练顺序的 480 样本批次在记录的 CUDA 环境重新加载验证，检查 loss/model 两接口、有限值及严格无绝对地板的损失比较。中间零梯度计数是生产程序记录，不能称为独立重放的整条梯度轨迹。变异测试拒绝删组合、删产物、错误父哈希和伪造零 CE/损失。新消费者 `softmax_matrix` 要求实验验收和最终梯度重检同时通过后，才能进入 Gate S。

结果：修复版在 18 组配对中 5 组 held-out 更高、12 组更低、1 组相同；最高最终 held-out 为 79.210%，未复现论文表格的高泛化。修复版 918 个记录点的模型入口 target 零梯度计数均为 0，标准版最多 243/480。因此本地证据支持已测数值机制的修复，不能支持固定预算下普遍泛化提升。所有结果均保留，不挑选有利种子。完整 [矩阵报告](site/reports/softmax-matrix/report.html)、[配对 CSV](site/reports/softmax-matrix/paired.csv)、协议、原始记录、出版矢量图和独立复现包共源交付。

下一阶段优先核对原论文/引用实现的输入表示、初始化等未对齐细节，并登记能区分架构差异与数值机制的消融；不能先把实现差异归因于修复方法。此后再单独资格化 bf16、扩充种子和任务。新科学主张仍须文献对照、可证伪假设和独立数据支持。

相关记录：[质量复核](docs/QUALITY-2026-10-31.md)、[案例说明](docs/CASE-SOFTMAX.md)、[健康](docs/HEALTH.md)、[编排](docs/ORCHESTRATION.md)。

<!-- self-audit:start -->
本轮验收：875 passed、1 个用例 skipped、4 个可选模块收集 skipped，框架源码覆盖率 71%，11 条链为 10 PASS/1 SKIP/0 FAIL/ERROR。
<!-- self-audit:end -->

既有 CUDA 16 项已独立通过；本轮未修改数值后端。

## 10. 实时运行总览：视觉与状态语义复核（2026-11-01）

`8765/` 保持原有深色科研仪表盘风格，首屏以链路、消费者、服务边界三组摘要组织信息；依赖矩阵与恢复图在区域内滚动，避免将字体缩小到不可读。消费者使用 MATCH / CONTROL OK / STALE 区分预期一致、负对照成功拒绝及缓存结论失效，原始 Gate S 判定仍同时展示。科研介绍与报告入口保持 `/index.html`。

实时轮询同步链路状态点、依赖单元格、模块列头、服务列头与状态点、时间及摘要，修复“左侧状态变化但矩阵仍保留旧颜色”的缺口。只有明确 OK 的服务显示绿色；缺失观测、异常状态、样本过期、序号倒退或 45 秒不递增、HTTP/解析/超时错误不能继续显示绿色 LIVE。数据保留时明确标注缓存。RUNNING 单独计数，不冒充完成。

恢复流程保留自身快照时间；旧尝试或其他服务的终结记录不能验证新尝试，24 小时 healed 仅计入明确 recovered 且未声明失败的事件。历史能力账本显示记录日期与版本，不再以硬编码“四项仪器、零缺陷”暗示当前源码已验收。历史故障与当前活动故障、源文件年龄与服务健康分别说明。完整语义与验证范围见 [监控状态说明](docs/MONITOR-SEMANTICS.md)。本次界面相关回归检查与浏览器验收不替代 `docs/SELF_AUDIT.json` 的全项目审计或严格 24 小时稳定性验收。


## 2026-11-01：独立指标修复闭环与 Windows 启动入口修复

HPAF 原 README 第 48 行承诺 normalized Levenshtein distance，实际报告引擎的
分子是 SequenceMatcher 编辑脚本成本，不保证为最短编辑距离。对两份现有文件
共 1,033 对字符串逐项复核，旧指标有 2 项不一致，最大高估 112 次编辑。
新适配器将可视化对齐和定量指标分开：分子使用单位代价动态规划最短距离，
保留 max(len(source), 1) 分母。计量单位是未经归一化的 Unicode 码点；该比率
具有方向性并可能超过 1，不能解释为字素距离、攻击成功率或总体效应。

独立校验使用固定 RapidFuzz 3.14.6 的 C++ 后端，并以 225 组短字符串的穷举
编辑图交叉核验；公共生产路径还包括 10 组良性边界样例。旧算法、全零指标、
错误归一化、缺失行、布尔型距离、源码/数据变化、缺失输出均有拒绝控制。
原始 HPAF 代码与语料保持原样。源码、协议、锁、数据在执行前后绑定；输出仅
允许新建，禁止误覆盖输入或历史证据。Gate S 记录探索性结论，不伪造预注册。

已分别在新建的同机 Windows 环境中安装锁定依赖并执行：私有包复核 1,033 对，
公共包复核 235 对；重复执行和修改输入被拒绝。仅公开新造良性样例包与聚合
结果，不公开私有语料。详见 docs/INDEPENDENT-LIFECYCLE-ACCEPTANCE.json、
reference/hpaf_metric/CASE.md 及 site/reports/hpaf-metric/report.html。
该范围不等于新机器、Linux/Binder、外部独立采用、科研新颖性或 EIDOS 功能完备。

Windows 的两个 CMD 入口原先 CALL monitor.env，在本机返回 0 却没有加载 SET
配置，导致静默沿用全局 Python。现通过 tools/launch_runtime.py 使用字面配置
解析器，清除继承的 Python 导入路径，以隐藏、隔离、UTF-8 模式选择项目解释器；
参数与失败退出码均保留。真实 --check 诊断选择 Python 3.12.4，窗口句柄为 0；
9 项真实 CMD 回归及 38 项组合测试通过。remove --check/--help 不会触发卸载。
原有服务进程尚未迁移，自动审批拒绝重启的记录和既有 soak 失败历史保留，
不把诊断通过描述为服务迁移、登录重启或干净 24 小时验收。


### 同轮发布前发现并修复的交付副作用

真实提交钩子的 724 项回归曾出现 1 项失败：纯页面 render() 隐式导出科研报告，
在直接 wb 覆盖训练 evidence.json 时触发 Windows Errno 22。该次提交被拒绝，
没有跳过检查；具体 OS 错误根因未证实。现把纯渲染和 --check 与发布分离，
正式构建显式导出一次，并共享同一份内存案例给页面；证据、QMD、CSV 及训练
记录副本使用临时文件后原子替换，仍持原目录锁，不宣称整目录事务原子性。
CSV/QMD 直接交付字节与 ZIP 内一致，修正 Windows 文本换行引起的漂移。
新增两个回归先失败、修复后相关 17 项通过；最终完整自审为 726 passed、
4 个可选模块收集跳过、框架覆盖率 69%、11 条链 10 PASS/1 SKIP。
详见 docs/REPORT-PUBLICATION-ACCEPTANCE-2026-11-01.json。


## 2026-11-01：项目命令的可安装 SDK 生命周期

framework.project.run_command 的 gate/test/render 统一使用 SDK 内置的进程边界，
实现和 Windows/Linux helper 随 wheel 交付，不依赖源码 tools 目录。Windows
以 Job 管理继承后代；Linux 以独立 guardian、进程组及 owner pipe 连接嵌套
SDK 生命周期。普通根进程退出与输出管道 EOF 分离；正常完成也由 guardian
自行关组，不把清理交回可能被外层终止的 caller。控制通道与科研 stdout 分开，
保留目标真实退出码；超时、containment、权限错误不能冒充科研 OPEN/PASS。

旧代码的 10 项生命周期拒绝测试失败；进一步通过真实 Linux 候选 wheel 发现
并复现嵌套脱离、正常退出交接两个漏洞，再用 owner EOF 和 guardian 自行关组
修复。最终安装包验收分别在新 Windows 环境、断网 Linux 容器中执行；后者
复用已有 CPU 依赖环境，不等于全新 Linux 依赖安装或新机器验收。Scope 与
摘要见 docs/SDK-EXECUTION.md、docs/SDK-PROCESS-ACCEPTANCE.json。

该边界针对受信任的短任务，非恶意代码沙箱或硬实时/内存限制。QuartoBridge、
reproduction、tracking、updates、形式/引用检查与 inference 的直接 subprocess
入口尚需逐项迁移和实测，不能把项目 runner 通过推断为整个 SDK 全部通过。
已有 monitor/loop 迁移、登录重启与干净 24 小时观察仍待完成，历史失败不重置。

## 2026-11-01：直接 SDK 文稿与图形交付闭环（0.4.7）

QuartoBridge 原先只看进程退出码，受控 CLI 可在不生成任何文件时令 PDF、DOCX、HTML 三项均返回成功；它返回 outputs 目录，实际文件却落入 manuscript。新增缺陷控制先记录 10 项失败，再修复真正的产物交付边界。

当前渲染分别使用全新的暂存目录，核对所需格式、直接本地 HTML 资源、PDF 的 Poppler 解析结果及 DOCX 主文档关系/内容类型，再持有输出锁发布。每个文件原子替换；收据最后写入。发布前再次检查声明输入和已复制文件摘要；缺格式、损坏文件、输入变化、同名收据资源、路径冲突或发布异常均拒绝，回滚本次输出并保留用户输入编辑。读取方仍须验证收据，不能将逐文件替换理解为任意读者的文件系统快照。

图形入口改为有界的受信 Python/Matplotlib 单图执行，支持 SVG/PNG/PDF、零参数脚本与正常整数零退出，拒绝无图/多图/非整数退出对象。figure_inputs 可声明数据与辅助代码，执行后及发布前均复核摘要。文稿构建器正确处理自定义目录、安全 YAML 元数据、矩形表格、表头分隔行、单元格转义和引用块。

PDF 校验使用明确的外部 Poppler 契约；缺工具拒绝。原数值研究锁、权重和证据保持原有冻结状态。安装包验证区分受控 CLI/真实 Matplotlib 与可选的真实 Quarto/TeX，明确要求三种物理主文件并独立重算输入输出摘要。详见 [交付契约](docs/QUARTO-DELIVERY.md)。这不是科学内容、NATURE 投稿接受、新机器或运行中服务迁移的证明。其他直接 SDK 子进程调用仍须逐项验收。

下一批已复现问题：直接 reproduction.compare 在无限预期/无限容差及大整数先转浮点时可错误返回 MATCH，详见 FUNCTIONAL_COMPLETENESS 的开放缺陷段。0.4.7 不将该未限定比较器作为通用科研判据。


## 2026-11-01：调度去重与复现证据完整性（0.4.8）

本批按用户要求执行调度精简。现有两项 Eidos Hermes CRON 保留任务 ID、时间计划和历史；继续使用无 LLM 的脚本模式，并已固定项目 Python、工作目录，关闭错过时段的补跑。watchdog 的执行完成与系统健康分开记账，持续故障仍保留负健康证据；同一原因重复轮询静默，原因变化与恢复通知。无效序号、损坏检查点、矛盾 JSON 和同类检查乱序覆盖均增加负控制。详见 [调度政策](docs/SCHEDULING-POLICY.md)。

链路排查还修复了手动刷新与后台复核使用不同锁、单项刷新导致全部重复复核、按证据年龄自动执行任意科研 gate 的问题。缓存最多复用 24 小时且必须匹配当前输入摘要，不重写 checked_at；手动选中项强制重验，--force 才全量重验。源代码修复不等于已加载进旧常驻进程。既有两个旧链路循环及监控仍待迁移；此前停止/重启被自动审批拒绝（blocked by policy），没有强停、绕过或清空失败历史。

直接 reproduction 比较器按所表示的整数/二进制浮点值精确比较，并拒绝无限数、非法类型及歧义 JSON。S12 要求原始规格文件、完整集合清单和当前输入绑定，不能只提取成功子项冒充整篇论文 MATCH。收据跟随声明代码/数据/规格失效，旧手写 MATCH 需重放；夹具审计和变异测试改用临时副本实际执行 stub。512 项固定 seed 的独立 Decimal 判定提供不同算法的对照。这些本地一致性检查不是签名执行证明或独立见证的预注册，也没有完成论文训练复现。详见 [复现完整性边界](docs/REPRODUCTION-INTEGRITY.md)。

本批按 0.4.8 交付：新 Windows 独立环境与断网 Linux 容器各通过 18 组复现控制、512 项 Decimal 判定，另重跑生命周期与交付验收；0.4.7 的三条错误 MATCH 在保留的旧安装环境实际重现。历史 wheel、标签与收据完整保留。正式发布状态以 GitHub Releases 的标签、精确提交 CI 和资产指纹为准。测试与覆盖率由 SELF_AUDIT 记录，未通过的运行和运行时迁移限制保留。
