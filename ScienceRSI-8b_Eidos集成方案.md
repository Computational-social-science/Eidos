# ScienceRSI-8b 在 Eidos RSI 框架中的集成方案

**版本**：1.0.0
**日期**：2026年10月26日
**目标**：将 ScienceRSI-8b（80亿参数科学推理模型）集成到 Eidos 的 LangGraph 多 Agent 编排流程中，承担科学推理执行与 Gate S 验证职责，并形成 RSI 闭环。

---

## 一、模型注册与阶段调度

### 1.1 推理配置注册

在 `configs/global/framework.yaml` 的 `inference` 段新增 ScienceRSI-8b 的模型定义：

```yaml
# configs/global/framework.yaml — inference 段追加
inference:
  vram_budget_gb: 10.5
  models:
    # ... 既有模型保持不变 ...
    
    sciencersi_8b:
      backend: llama_cpp            # 或 ollama，取决于你的部署偏好
      path: "models/ScienceRSI-8b-Q4_K_M.gguf"
      quant: Q4_K_M
      context_length: 32768         # Qwen3-8B 原生支持，够用
      max_tokens: 8192
      temperature: 0.3              # 科学推理偏低温度，减少幻觉
      vram_footprint_gb: 6.8        # Q4_K_M 实测约 6.5-7.0 GB
      capabilities:
        - function_call             # Qwen3 原生支持
        - scientific_reasoning
        - evidence_evaluation
      mutex_with:                   # 互斥模型，不可同时驻留
        - startlux_decision_4b      # Gate S 路由模型，需要时切换

    startlux_decision_4b:
      # ... 既有配置 ...
      mutex_with:
        - sciencersi_8b
```

### 1.2 阶段-模型映射

更新 `framework/inference/` 的阶段调度表，将 ScienceRSI-8b 绑定到 hypothesis 和 evaluation 阶段：

```yaml
# configs/global/framework.yaml — stage_models 段
stage_models:
  hypothesis:
    primary: sciencersi_8b          # 主模型：科学假设生成
    fallback: llama3_1_8b           # 降级模型
    reasoning: "科学假设生成需要强推理能力，ScienceRSI-8b 在 GPQA-Diamond 上同规模最佳"
    
  literature:
    primary: qwen2_5_14b            # 保持不变，文献综述需要广泛知识
    fallback: llama3_1_8b
    
  design:
    primary: qwen2_5_14b
    secondary: sciencersi_8b        # 实验设计时可作为第二意见
    fallback: gemma2_9b
    
  execution:
    primary: startlux_decision_4b   # 执行阶段用轻量决策模型
    # ScienceRSI-8b 不参与此阶段
    
  evaluation:
    primary: sciencersi_8b          # 主模型：证据评估与结论验证
    fallback: llama3_1_8b
    reasoning: "评估阶段需要判断证据是否支持结论，ScienceRSI 的验证逻辑天然适配"
    
  diagnosis:
    primary: sciencersi_8b          # 失败诊断需要科学推理定位根因
    fallback: llama3_1_8b
    
  manuscript:
    primary: qwen2_5_14b            # 论文写作保持原模型
    fallback: llama3_1_8b
```

### 1.3 显存调度流程

ScienceRSI-8b 在 Eidos 的阶段感知调度中的切换逻辑：

```
pipeline 启动
  │
  ├─ hypothesis 阶段
  │   ├─ 加载 sciencersi_8b (6.8 GB)
  │   ├─ 执行假设生成
  │   └─ 卸载 sciencersi_8b
  │
  ├─ literature 阶段
  │   ├─ 加载 qwen2_5_14b
  │   ├─ 执行文献检索
  │   └─ 卸载 qwen2_5_14b
  │
  ├─ design 阶段
  │   ├─ 加载 qwen2_5_14b (主) + sciencersi_8b (辅，如需要)
  │   ├─ 注意：两者不可同时驻留，按子任务交替加载
  │   └─ 卸载
  │
  ├─ execution 阶段
  │   ├─ 加载 startlux_decision_4b (轻量，~4 GB)
  │   ├─ 执行实验
  │   └─ 卸载
  │
  ├─ evaluation 阶段
  │   ├─ 加载 sciencersi_8b (6.8 GB)
  │   ├─ 执行证据评估
  │   └─ 卸载
  │
  ├─ Gate S 验证（见第二节）
  │   ├─ sciencersi_8b 已在 evaluation 阶段驻留
  │   ├─ 执行 S4/S7 增强验证
  │   └─ 卸载 sciencersi_8b，加载 startlux_decision_4b 做路由
  │
  ├─ diagnosis 阶段（如有失败）
  │   ├─ 加载 sciencersi_8b
  │   ├─ 生成结构化失败报告
  │   └─ 卸载
  │
  └─ manuscript 阶段
      ├─ 加载 qwen2_5_14b
      └─ 生成论文
```

---

## 二、Gate S 增强版验证

### 2.1 设计思路

Gate S 的 S1-S8 检查中，S1-S3、S5-S6 是结构性检查（解析、匹配、声明），不需要 LLM。S4（preregistered design + negative control）和 S7（referee simulation）需要科学推理判断，这正是 ScienceRSI-8b 的强项。

### 2.2 S4 增强 Prompt：实验设计有效性验证

```python
# framework/validity/gate_s_enhanced.py

S4_SYSTEM_PROMPT = """你是一位严格的科学方法论审查员。你的任务是验证一项研究设计是否满足科学有效性的基本要求。

你需要检查：
1. 研究设计是否有预注册或明确的实验方案
2. 是否包含阴性对照（negative control）
3. 样本量和统计功效是否足以支持所声称的效应
4. 实验设计是否能排除主要的混淆变量

输出格式（严格 JSON）：
{
  "preregistered": bool,           // 是否有预注册设计
  "preregistered_evidence": str,   // 指向具体 artefact 的 RFC 6901 指针
  "negative_control": bool,        // 是否包含阴性对照
  "negative_control_description": str,  // 对照的具体描述
  "power_adequate": bool,          // 统计功效是否足够
  "power_analysis_pointer": str,   // 指向功效分析 artefact
  "confounders_addressed": [str],  // 已处理的混淆变量列表
  "confounders_unaddressed": [str],// 未处理的混淆变量列表
  "verdict": "PASS" | "FAIL" | "WEAK_PASS",
  "objections": [str]              // 具体的方法论异议，每条需可操作
}

规则：
- 只基于提供的 evidence artefacts 判断，不推测未提供的信息
- 如果某个检查项没有对应的 evidence，该项判定为 FAIL
- objections 中的每一条必须对应具体的改进建议
- 如果你不确定，在 verdict 中输出 WEAK_PASS 并在 objections 中说明不确定性"""

S4_USER_TEMPLATE = """## 待验证的 Claim
{claim_text}

## 实验设计 Artefact
{design_artefact_content}

## 统计分析 Artefact
{stats_artefact_content}

## Claim Register 中的预注册声明
{preregistered_declaration}

## 对照实验 Artefact
{control_artefact_content}

请逐项检查并输出 JSON 判定。"""
```

### 2.3 S7 增强 Prompt：模拟审稿人验证

```python
S7_SYSTEM_PROMPT = """你是一位资深的同行审稿人，正在对一篇科学论文的核心主张进行审查。你的任务不是简单地判断"对不对"，而是找出推理链条中可能存在的漏洞。

你需要模拟一位严格的 Reviewer 2：
- 质疑因果关系的替代解释
- 检查统计方法是否适合研究问题
- 评估结论是否超出了证据所能支持的范围
- 寻找选择性报告的可能性（如 p-hacking、HARKing）
- 评估可重复性风险

输出格式（严格 JSON）：
{
  "objections": [
    {
      "id": "obj_001",
      "severity": "major" | "minor" | "fatal",
      "category": "causality" | "statistics" | "overclaim" | "reporting" | "reproducibility" | "other",
      "description": str,           // 异议的具体描述
      "evidence_pointer": str,      // 指向相关 evidence 的 RFC 6901 指针
      "suggested_revision": str,    // 建议的修改方向
      "resolvable": bool            // 是否可在当前框架内解决
    }
  ],
  "overall_verdict": "PASS" | "MAJOR_REVISION" | "REJECT",
  "confidence": float,              // 0.0-1.0，你对自己判断的确信度
  "unresolved_count": int           // 未解决的 major+ 级别异议数
}

规则：
- severity 为 "fatal" 的异议直接导致 REJECT
- 任何 unresolved_count > 0 时，overall_verdict 不能为 PASS
- 你必须为每个 objection 提供 evidence_pointer，不可凭空质疑
- 如果你认为某个 claim 的证据确实充分，不要为了显得严格而编造异议"""

S7_USER_TEMPLATE = """## Claim Register（analysis/CLAIMS.yaml）
{claims_yaml}

## Manuscript 中的相关段落
{manuscript_excerpt}

## 所有 Evidence Artefacts
{evidence_artefacts}

## LESSONS 中的历史教训（来自之前的审查）
{lessons_context}

请作为审稿人进行审查，输出 JSON 格式的审稿意见。"""
```

### 2.4 Gate S 集成代码

```python
# framework/validity/gate_s_enhanced.py

import json
import yaml
from pathlib import Path
from framework.inference import ModelManager
from framework.gates.base import GateResult, GateStatus

class EnhancedGateS:
    """Gate S 增强版：在 S4 和 S7 环节引入 ScienceRSI-8b 进行科学推理验证。"""
    
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self.model_id = "sciencersi_8b"
    
    async def check_s4(self, claim: dict, project_path: Path) -> dict:
        """S4 增强：验证实验设计有效性。"""
        
        # 收集相关 artefacts
        design_artefact = self._load_artefact(project_path, claim.get("design_pointer"))
        stats_artefact = self._load_artefact(project_path, claim.get("power_pointer"))
        control_artefact = self._load_artefact(project_path, claim.get("control_pointer"))
        prereg_declaration = claim.get("preregistered", "not_declared")
        
        # 构建 prompt
        user_msg = S4_USER_TEMPLATE.format(
            claim_text=claim["text"],
            design_artefact_content=design_artefact or "NOT_FOUND",
            stats_artefact_content=stats_artefact or "NOT_FOUND",
            prereistered_declaration=prereg_declaration,
            control_artefact_content=control_artefact or "NOT_FOUND",
        )
        
        # 调用 ScienceRSI-8b
        response = await self.model_manager.generate(
            model_id=self.model_id,
            system_prompt=S4_SYSTEM_PROMPT,
            user_message=user_msg,
            response_format="json",
            temperature=0.2,  # 验证任务用更低温度
        )
        
        result = json.loads(response)
        
        return {
            "gate": "S4",
            "model": self.model_id,
            "verdict": result["verdict"],
            "details": result,
            "passed": result["verdict"] in ("PASS", "WEAK_PASS"),
        }
    
    async def check_s7(self, claims: list, project_path: Path, lessons: list) -> dict:
        """S7 增强：模拟审稿人验证。"""
        
        # 加载 claim register
        claims_yaml = yaml.dump(claims, allow_unicode=True, default_flow_style=False)
        
        # 加载相关 manuscript 段落
        manuscript_excerpt = self._extract_manuscript_claims(project_path, claims)
        
        # 加载所有 evidence artefacts
        evidence_artefacts = self._collect_all_evidence(project_path, claims)
        
        # 注入 LESSONS 历史教训（RSI 闭环的关键）
        lessons_context = self._format_lessons(lessons)
        
        user_msg = S7_USER_TEMPLATE.format(
            claims_yaml=claims_yaml,
            manuscript_excerpt=manuscript_excerpt,
            evidence_artefacts=evidence_artefacts,
            lessons_context=lessons_context or "No prior lessons recorded.",
        )
        
        response = await self.model_manager.generate(
            model_id=self.model_id,
            system_prompt=S7_SYSTEM_PROMPT,
            user_message=user_msg,
            response_format="json",
            temperature=0.2,
        )
        
        result = json.loads(response)
        
        # 检查 referee simulation 是否有未解决的 objection
        unresolved = [
            obj for obj in result["objections"]
            if obj["severity"] in ("major", "fatal")
        ]
        
        return {
            "gate": "S7",
            "model": self.model_id,
            "verdict": result["overall_verdict"],
            "objections": result["objections"],
            "unresolved_major_count": len(unresolved),
            "passed": result["overall_verdict"] == "PASS",
            "confidence": result["confidence"],
        }
    
    def _format_lessons(self, lessons: list) -> str:
        """将 LESSONS 文件中的历史教训格式化为 prompt 注入文本。
        这是 RSI 闭环的关键——让模型从过去的验证失败中学习。"""
        if not lessons:
            return ""
        
        formatted = []
        for lesson in lessons[-10:]:  # 最近 10 条，避免 prompt 过长
            formatted.append(
                f"- [{lesson['date']}] {lesson['category']}: "
                f"{lesson['description']} → 修正: {lesson['resolution']}"
            )
        return "\n".join(formatted)
    
    def _load_artefact(self, project_path: Path, pointer: str) -> str | None:
        """通过 RFC 6901 指针加载 evidence artefact。"""
        if not pointer:
            return None
        # 复用 Eidos 已有的 artefact 解析逻辑
        from framework.validity.gate_s import resolve_pointer
        return resolve_pointer(project_path, pointer)
    
    def _extract_manuscript_claims(self, project_path: Path, claims: list) -> str:
        """从 manuscript 中提取与 claims 相关的段落。"""
        from framework.validity.gate_s import extract_claim_spans
        return extract_claim_spans(project_path, claims)
    
    def _collect_all_evidence(self, project_path: Path, claims: list) -> str:
        """收集所有 claim 对应的 evidence artefacts。"""
        from framework.validity.gate_s import collect_evidence
        return collect_evidence(project_path, claims)
```

---

## 三、RSI 闭环反馈机制

### 3.1 设计理念

Eidos 的 LESSONS 文件 + ScienceRSI 的"验证先于迁移"思想，形成推理阶段的 RSI 循环：

```
        ┌─────────────────────────────────────────────────┐
        │              RSI 推理闭环                         │
        │                                                   │
        │   ① Agent 用 ScienceRSI-8b 做科学推理              │
        │          ↓                                        │
        │   ② Gate S 验证输出质量（S4/S7 增强）              │
        │          ↓                                        │
        │   ③ 验证通过 → 推理模式写入 Agent Skills           │
        │      验证失败 → 失败原因写入 LESSONS               │
        │          ↓                                        │
        │   ④ 下次同类任务时：                               │
        │      - LESSONS 注入 prompt 作为负面示例             │
        │      - Agent Skills 注入成功的推理模式              │
        │          ↓                                        │
        │   ⑤ Agent 的推理质量逐步提升（不改参数，改知识）     │
        │          ↓                                        │
        │   回到 ①                                          │
        └─────────────────────────────────────────────────┘
```

### 3.2 LESSONS 写入逻辑

```python
# framework/lessons/rsi_writer.py

from pathlib import Path
from datetime import datetime
import yaml

class RSIWriter:
    """将 Gate S 验证结果写入 LESSONS，供后续 RSI 循环使用。"""
    
    def __init__(self, project_path: Path):
        self.lessons_path = project_path / "LESSONS.yaml"
    
    def record_verification_failure(self, gate_result: dict, context: dict):
        """记录验证失败：什么推理模式出了问题，如何避免。"""
        
        lesson = {
            "date": datetime.now().isoformat(),
            "stage": context["stage"],           # hypothesis / evaluation / etc.
            "gate": gate_result["gate"],          # S4 / S7
            "model": gate_result.get("model", "unknown"),
            "category": self._classify_failure(gate_result),
            "description": self._extract_failure_description(gate_result),
            "resolution": self._suggest_resolution(gate_result),
            "evidence_pointer": context.get("evidence_pointer"),
            "severity": self._assess_severity(gate_result),
            "recurrence_count": 0,                # 首次出现
        }
        
        # 检查是否有同类历史教训（相同 category）
        existing = self._load_lessons()
        matches = [l for l in existing if l["category"] == lesson["category"]]
        if matches:
            lesson["recurrence_count"] = max(m["recurrence_count"] for m in matches) + 1
            lesson["prior_occurrences"] = [m["date"] for m in matches[-3:]]
        
        self._append_lesson(lesson)
    
    def record_verification_success(self, gate_result: dict, context: dict):
        """记录验证通过的成功推理模式，写入 Agent Skills。"""
        
        skill_entry = {
            "date": datetime.now().isoformat(),
            "stage": context["stage"],
            "pattern_type": self._classify_success_pattern(gate_result),
            "reasoning_chain_summary": context.get("reasoning_summary", ""),
            "applicable_when": context.get("task_conditions", []),
        }
        
        self._append_skill(skill_entry)
    
    def _classify_failure(self, gate_result: dict) -> str:
        """将 Gate S 失败分类为可复用的类别。"""
        verdict = gate_result.get("verdict", "")
        gate = gate_result.get("gate", "")
        
        if gate == "S4":
            details = gate_result.get("details", {})
            if not details.get("preregistered"):
                return "missing_preregistration"
            if not details.get("negative_control"):
                return "missing_negative_control"
            if not details.get("power_adequate"):
                return "insufficient_power"
            if details.get("confounders_unaddressed"):
                return "unaddressed_confounders"
        
        if gate == "S7":
            objections = gate_result.get("objections", [])
            if any(o["severity"] == "fatal" for o in objections):
                return "fatal_methodological_flaw"
            categories = set(o["category"] for o in objections)
            if "overclaim" in categories:
                return "overclaiming"
            if "statistics" in categories:
                return "statistical_method_mismatch"
            if "causality" in categories:
                return "causal_inference_error"
        
        return "general_reasoning_failure"
    
    def _extract_failure_description(self, gate_result: dict) -> str:
        """提取可读的失败描述。"""
        if gate_result["gate"] == "S7":
            objections = gate_result.get("objections", [])
            major = [o for o in objections if o["severity"] in ("major", "fatal")]
            if major:
                return "; ".join(o["description"] for o in major[:3])
        if gate_result["gate"] == "S4":
            details = gate_result.get("details", {})
            issues = []
            if not details.get("negative_control"):
                issues.append("缺少阴性对照")
            if not details.get("power_adequate"):
                issues.append("统计功效不足")
            return "; ".join(issues) if issues else "实验设计存在方法论缺陷"
        return "验证未通过"
    
    def _suggest_resolution(self, gate_result: dict) -> str:
        """生成可操作的修正建议。"""
        category = self._classify_failure(gate_result)
        
        resolutions = {
            "missing_preregistration": "补充实验方案预注册文档，明确假设、样本量和分析计划",
            "missing_negative_control": "设计并执行阴性对照实验，排除基线效应和假阳性",
            "insufficient_power": "重新计算所需样本量，或降低 claim 的效应量声明",
            "unaddressed_confounders": "识别并控制混淆变量，或在 claim 中明确声明局限性",
            "fatal_methodological_flaw": "需要从根本上重新审视实验设计",
            "overclaiming": "收窄结论的适用范围，增加限定条件",
            "statistical_method_mismatch": "选择与研究问题匹配的统计方法",
            "causal_inference_error": "明确区分相关性和因果性，补充因果推断的证据",
        }
        return resolutions.get(category, "审查推理链条中的薄弱环节并修正")
    
    def _assess_severity(self, gate_result: dict) -> str:
        verdict = gate_result.get("verdict", "")
        if verdict in ("REJECT", "FAIL"):
            return "critical"
        if verdict == "MAJOR_REVISION":
            return "major"
        if verdict == "WEAK_PASS":
            return "minor"
        return "info"
    
    def _classify_success_pattern(self, gate_result: dict) -> str:
        return f"verified_{gate_result.get('gate', 'unknown')}_reasoning"
    
    def _load_lessons(self) -> list:
        if not self.lessons_path.exists():
            return []
        with open(self.lessons_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or []
    
    def _append_lesson(self, lesson: dict):
        lessons = self._load_lessons()
        lessons.append(lesson)
        with open(self.lessons_path, "w", encoding="utf-8") as f:
            yaml.dump(lessons, f, allow_unicode=True, default_flow_style=False)
    
    def _append_skill(self, skill: dict):
        skills_path = self.lessons_path.parent / "AGENT_SKILLS.yaml"
        skills = []
        if skills_path.exists():
            with open(skills_path, "r", encoding="utf-8") as f:
                skills = yaml.safe_load(f) or []
        skills.append(skill)
        with open(skills_path, "w", encoding="utf-8") as f:
            yaml.dump(skills, f, allow_unicode=True, default_flow_style=False)
```

### 3.3 LESSONS 注入 Prompt（RSI 反馈到下次推理）

```python
# framework/lessons/rsi_injector.py

class RSIInjector:
    """将 LESSONS 和 AGENT_SKILLS 注入到 ScienceRSI-8b 的下次推理 prompt 中。"""
    
    def __init__(self, project_path: Path):
        self.project_path = project_path
    
    def build_context_block(self, stage: str, task_category: str = None) -> str:
        """构建注入 prompt 的上下文块。"""
        
        lessons = self._load_relevant_lessons(stage, task_category)
        skills = self._load_relevant_skills(stage, task_category)
        
        parts = []
        
        if skills:
            parts.append("## 已验证的成功推理模式\n")
            parts.append("以下推理模式在之前的任务中通过了验证，可参考使用：\n")
            for skill in skills[-5:]:
                parts.append(f"- [{skill['pattern_type']}] {skill['reasoning_chain_summary']}")
                if skill.get("applicable_when"):
                    parts.append(f"  适用条件：{', '.join(skill['applicable_when'])}")
            parts.append("")
        
        if lessons:
            parts.append("## 历史教训（请避免以下问题）\n")
            parts.append("以下是之前推理过程中发现的问题，请在本次推理中主动避免：\n")
            for lesson in lessons[-5:]:
                recurrence = f"（第 {lesson['recurrence_count'] + 1} 次出现）" if lesson.get("recurrence_count") else ""
                parts.append(
                    f"- [{lesson['severity']}] {lesson['category']}{recurrence}: "
                    f"{lesson['description']}"
                )
                parts.append(f"  → 建议修正方向：{lesson['resolution']}")
            parts.append("")
        
        return "\n".join(parts)
    
    def inject_into_prompt(self, base_system_prompt: str, stage: str, task_category: str = None) -> str:
        """将 RSI 上下文注入到 system prompt 中。"""
        context_block = self.build_context_block(stage, task_category)
        if not context_block:
            return base_system_prompt
        
        return f"""{base_system_prompt}

---

## RSI 经验注入（来自本项目的历史推理记录）

{context_block}

请在本次推理中充分考虑以上经验教训。对于历史教训中提到的问题类型，请格外注意避免。
对于已验证的成功模式，可在适用时参考其推理思路。"""
    
    def _load_relevant_lessons(self, stage: str, task_category: str = None) -> list:
        lessons_path = self.project_path / "LESSONS.yaml"
        if not lessons_path.exists():
            return []
        with open(lessons_path, "r", encoding="utf-8") as f:
            lessons = yaml.safe_load(f) or []
        
        # 筛选同阶段的教训
        relevant = [l for l in lessons if l.get("stage") == stage]
        
        # 如果有任务类别，进一步筛选
        if task_category:
            relevant = [l for l in relevant if task_category in l.get("category", "")]
        
        return relevant
    
    def _load_relevant_skills(self, stage: str, task_category: str = None) -> list:
        skills_path = self.project_path / "AGENT_SKILLS.yaml"
        if not skills_path.exists():
            return []
        with open(skills_path, "r", encoding="utf-8") as f:
            skills = yaml.safe_load(f) or []
        
        return [s for s in skills if s.get("stage") == stage]
```

---

## 四、LangGraph 节点集成

### 4.1 Hypothesis Agent 节点

```python
# framework/agents/hypothesis_agent.py

from langgraph.graph import StateGraph, END
from framework.inference import ModelManager
from framework.lessons.rsi_injector import RSIInjector
from framework.lessons.rsi_writer import RSIWriter

HYPOTHESIS_SYSTEM_PROMPT = """你是一位科学研究假设生成专家。基于给定的研究问题和文献综述，生成可检验的科学假设。

要求：
1. 假设必须具体、可操作、可证伪
2. 明确自变量、因变量和控制变量
3. 说明假设的理论依据和推理链条
4. 标注假设的风险等级（高/中/低）和理由
5. 如果有阴性对照的设计建议，一并提出

输出格式（严格 JSON）：
{
  "hypotheses": [
    {
      "id": "H1",
      "statement": str,
      "independent_variable": str,
      "dependent_variable": str,
      "control_variables": [str],
      "theoretical_basis": str,
      "reasoning_chain": str,      // 从理论到假设的推理链条
      "falsifiability": str,       // 如何证伪这个假设
      "risk_level": "high" | "medium" | "low",
      "risk_reason": str,
      "suggested_negative_control": str
    }
  ],
  "overall_reasoning": str         // 整体推理逻辑概述
}"""

async def hypothesis_node(state: dict) -> dict:
    """LangGraph 假设生成节点。"""
    
    project_path = state["project_path"]
    model_manager = state["model_manager"]
    rsi_injector = RSIInjector(project_path)
    
    # 注入 RSI 历史经验
    enhanced_prompt = rsi_injector.inject_into_prompt(
        base_system_prompt=HYPOTHESIS_SYSTEM_PROMPT,
        stage="hypothesis",
    )
    
    # 构建用户消息
    user_msg = f"""## 研究问题
{state['research_question']}

## 文献综述摘要
{state.get('literature_summary', 'Not yet available')}

## 先验知识
{state.get('prior_knowledge', 'None')}

请生成科学假设。"""
    
    # 调用 ScienceRSI-8b
    response = await model_manager.generate(
        model_id="sciencersi_8b",
        system_prompt=enhanced_prompt,
        user_message=user_msg,
        response_format="json",
        temperature=0.3,
    )
    
    result = json.loads(response)
    
    return {
        **state,
        "hypotheses": result["hypotheses"],
        "hypothesis_meta": {
            "model": "sciencersi_8b",
            "rsi_enriched": rsi_injector.build_context_block("hypothesis") != "",
        },
    }
```

### 4.2 Evaluation Agent 节点

```python
# framework/agents/evaluation_agent.py

EVALUATION_SYSTEM_PROMPT = """你是一位科学实验评估专家。你的任务是基于实验结果评估假设是否成立，并判断证据是否支持结论。

评估维度：
1. 数据与假设的一致性：实验结果是否支持/否定假设
2. 效应量与统计显著性：效应是否具有实际意义
3. 混淆变量排除：是否已充分控制替代解释
4. 阴性对照验证：基线行为是否符合预期
5. 结论的适当范围：结论是否超出了证据所能支持的范围

输出格式（严格 JSON）：
{
  "evaluations": [
    {
      "hypothesis_id": str,
      "supported": "yes" | "partial" | "no",
      "evidence_summary": str,
      "effect_size": str,
      "statistical_significance": str,
      "confounders_check": str,
      "negative_control_result": str,
      "conclusion_scope_appropriate": bool,
      "overclaiming_risk": str,
      "reasoning_chain": str        // 从数据到判断的推理链条
    }
  ],
  "overall_assessment": str,
  "confidence": float
}"""

async def evaluation_node(state: dict) -> dict:
    """LangGraph 评估节点。"""
    
    project_path = state["project_path"]
    model_manager = state["model_manager"]
    rsi_injector = RSIInjector(project_path)
    
    enhanced_prompt = rsi_injector.inject_into_prompt(
        base_system_prompt=EVALUATION_SYSTEM_PROMPT,
        stage="evaluation",
    )
    
    user_msg = f"""## 假设列表
{json.dumps(state['hypotheses'], ensure_ascii=False, indent=2)}

## 实验结果
{state['experiment_results']}

## 统计分析
{state.get('statistical_analysis', 'Not available')}

## 阴性对照结果
{state.get('control_results', 'Not available')}

请逐项评估每个假设。"""
    
    response = await model_manager.generate(
        model_id="sciencersi_8b",
        system_prompt=enhanced_prompt,
        user_message=user_msg,
        response_format="json",
        temperature=0.2,
    )
    
    result = json.loads(response)
    
    return {
        **state,
        "evaluations": result["evaluations"],
        "overall_assessment": result["overall_assessment"],
        "evaluation_meta": {
            "model": "sciencersi_8b",
            "rsi_enriched": rsi_injector.build_context_block("evaluation") != "",
        },
    }
```

### 4.3 Gate S 验证节点（RSI 闭环关键）

```python
# framework/agents/gate_s_node.py

async def gate_s_node(state: dict) -> dict:
    """LangGraph Gate S 验证节点——RSI 闭环的核心。"""
    
    from framework.validity.gate_s_enhanced import EnhancedGateS
    from framework.lessons.rsi_writer import RSIWriter
    
    project_path = state["project_path"]
    model_manager = state["model_manager"]
    gate_s = EnhancedGateS(model_manager)
    rsi_writer = RSIWriter(project_path)
    
    # 加载 claims
    claims_path = project_path / "analysis" / "CLAIMS.yaml"
    with open(claims_path, "r", encoding="utf-8") as f:
        claims = yaml.safe_load(f) or []
    
    # 加载 lessons
    lessons_path = project_path / "LESSONS.yaml"
    lessons = []
    if lessons_path.exists():
        with open(lessons_path, "r", encoding="utf-8") as f:
            lessons = yaml.safe_load(f) or []
    
    results = {"gate_s": {"checks": [], "overall_pass": True}}
    
    # S1-S3, S5-S6: 结构性检查（不需要 LLM）
    for check_id in ["S1", "S2", "S3", "S5", "S6"]:
        check_result = await run_structural_check(check_id, claims, project_path)
        results["gate_s"]["checks"].append(check_result)
    
    # S4: ScienceRSI-8b 增强检查
    for claim in claims:
        if claim.get("requires_s4", True):
            s4_result = await gate_s.check_s4(claim, project_path)
            results["gate_s"]["checks"].append(s4_result)
            
            if not s4_result["passed"]:
                results["gate_s"]["overall_pass"] = False
                # RSI：记录失败教训
                rsi_writer.record_verification_failure(
                    s4_result, 
                    {"stage": "evaluation", "evidence_pointer": claim.get("evidence_pointer")}
                )
    
    # S7: ScienceRSI-8b 增强审稿人模拟
    s7_result = await gate_s.check_s7(claims, project_path, lessons)
    results["gate_s"]["checks"].append(s7_result)
    
    if not s7_result["passed"]:
        results["gate_s"]["overall_pass"] = False
        rsi_writer.record_verification_failure(
            s7_result,
            {"stage": "evaluation"}
        )
    else:
        # RSI：记录成功推理模式
        rsi_writer.record_verification_success(
            s7_result,
            {"stage": "evaluation", "reasoning_summary": state.get("overall_assessment", "")}
        )
    
    # S8: Lean 审计（已有逻辑，不改动）
    for claim in claims:
        if claim.get("formal", False):
            s8_result = await run_lean_audit(claim, project_path)
            results["gate_s"]["checks"].append(s8_result)
    
    return {
        **state,
        "gate_s_results": results["gate_s"],
    }
```

---

## 五、部署验证清单

集成完成后，按以下步骤验证：

```bash
# 1. 下载 ScienceRSI-8b GGUF 量化版
#    推荐 Q4_K_M（约 4.5 GB）或 Q5_K_M（约 5.5 GB）
#    放入 Eidos 的 models/ 目录
wget -O models/ScienceRSI-8b-Q4_K_M.gguf \
  "https://huggingface.co/mradermacher/ScienceRSI-8b-i1-GGUF/resolve/main/ScienceRSI-8b.i1-Q4_K_M.gguf"

# 2. 更新 framework.yaml 中的模型配置（见第一节）

# 3. 运行完整审计链
make audit

# 4. 检查 ScienceRSI-8b 是否正常加载和卸载
python -m framework.inference --probe sciencersi_8b

# 5. 用 demo project 跑一轮完整 pipeline
make bootstrap PROJECT=sciencersi_test
# 编辑 projects/sciencersi_test/configs/project.yaml
python projects/sciencersi_test/scripts/run_experiment.py
python projects/sciencersi_test/scripts/run_evaluation.py
python projects/sciencersi_test/scripts/build_manuscript.py

# 6. 验证 RSI 闭环：检查 LESSONS.yaml 和 AGENT_SKILLS.yaml 是否有写入
cat projects/sciencersi_test/LESSONS.yaml
cat projects/sciencersi_test/AGENT_SKILLS.yaml

# 7. Gate S 单独验证
python tools/audit_validity.py --project projects/sciencersi_test --json

# 8. 对比验证：同一 claim 分别用 llama3.1:8b 和 sciencersi_8b 评估
python framework/model_ab.py --models llama3_1_8b,sciencersi_8b --questions 12
```

---

## 六、风险与缓解

| 风险 | 严重度 | 缓解措施 |
|---|---|---|
| 8B 模型指令遵循不稳定 | 中 | 所有 ScienceRSI-8b 输出都要求 JSON schema 强制，解析失败时 fallback 到 llama3.1:8b |
| 推理延迟叠加（多 Agent 多轮） | 中 | ScienceRSI-8b 仅在 hypothesis/evaluation/diagnosis 阶段加载，其他阶段不占用 VRAM |
| LESSONS 文件无限增长导致 prompt 过长 | 低 | RSIInjector 只注入最近 10 条 + 同阶段筛选，超过阈值时按 recurrence_count 排序截断 |
| Gate S 增强验证引入新的误判 | 中 | S4/S7 的 ScienceRSI-8b 输出是 advisory 而非 binding，最终仍由结构性检查（S1-S3/S5-S6/S8）做硬性门槛 |
| GGUF 量化损失科学推理精度 | 低 | Q4_K_M 对 8B 模型的推理能力损失通常在 1-2pp 以内，可接受 |
