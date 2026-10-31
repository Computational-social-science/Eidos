# 科研与对外案例：从隐藏的梯度错误到可复核交付

来源：[Barron、Gnanapragasam、Tschannen，A Fix for Softmax and Cross-Entropy，v3](https://arxiv.org/html/2610.31642v3)。

“损失有限、没有 NaN”并不等于梯度正确。该工作揭示 Softmax Collapse 与 Softmax Cancellation；Eidos 用这个案例验证自身是否能识别、复现并阻止被测机制的错误通过。

**可直接用于介绍的表述：**

> Eidos 将已有 Paper2Agent 论文工具接入独立高精度验收：以 float32/float64 的 96 个实测案例展示精度断崖和近相等 logits 的梯度误差，要求刻意损坏的对照被拒绝，并从同一份证据生成交互案例、科研报告和可执行复现包。检查结果进入数值审计与回归测试，形成可复用的科研能力。

**English:** Eidos turns a published numerical failure into a reproducible research acceptance case: independently checked gradients, adversarial controls, an upgraded existing Paper2Agent tool, and evidence shared by the interactive case, report and executable source bundle.

## 可核验的演示顺序

1. 在 `site/index.html#demo` 选择 Collapse、float32、logit gap 18：标准 target 梯度为 0，修复梯度约为 −3.046e−8。
2. 切到 Cancellation，检查完全相等和 1e−7 扰动：分清请求扰动与实际可表示输入，平稳点比较绝对误差；零参考处相对误差无定义。
3. 展开方法，核对原论文 Eqs. 5–9；从链接下载 JSON、CSV、HTML/PDF/Word 报告与 ZIP。
4. 解压 ZIP，按 README 在独立环境重建全部展示结果，检查两项负对照被拒绝。

不应宣称 Eidos 发现了这两个问题、已经复现整篇论文训练收益，或保证所有未来项目免疫数值错误。该案例证明的是有边界的验证与复用能力；新的科学结论仍须自己的设计、数据和实验。

交付入口：`site/reports/numerics/`；可复用实现：`framework/stable_numerics.py` 与 `framework/stable_numerics_torch.py`；原有 Agent：`reference/barron2026_agent/`。

## 修复方案与前后对照

Collapse 修复同时覆盖 `log1p` 前向与 target 梯度的负和计算；Cancellation 使用 teacher logits、中心化差值、`expm1`/`log1p` 和零和修正，保留远分支。网页提供可直接调用的经过测试的 Torch 实现入口。

补充训练对照包含三个种子、每种方案 2,000 个 Adam 步：标准版最终参数位移约 0.172161、0.150217、0.181606，修复版均为 0。教师 held-out 准确率很低，因此只能展示平稳点修复，不能宣传泛化提升。完整轨迹、前瞻本地协议、模型和保留的失败运行都随包交付。

出版图件包含四面板数值对照和两面板训练对照，按 Nature 官方图件技术要求制作并提供 SVG/PDF；不宣称期刊认可或接收。

网页图现在使用原站深色背景和响应式 SVG：Figure 1 的模式、精度、案例与滑块同时更新梯度、误差扫描、游标和读数；Figure 2 可组合种子、指标、尺度、步数和修复方案。网页不再嵌入静态白底出版图。白底 183 mm SVG/PDF 作为完整实测范围的出版母版单独下载，不能混淆为当前网页选择的导出。

后续 Transformer 重建与探索性延长见 [完整记录](SOFTMAX-TRAINING-FOLLOWUP.md)。三名延长实验教师均达到预设的 95% held-out 阈值；蒸馏标准方案发生位移、修复方案保持零位移。该结果保留三种子差异、原 10,000 epoch 阴性结果与重建选择，尚不能宣传整篇论文复现或普遍收益。
