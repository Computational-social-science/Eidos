"""Publish a fixed set of public source documents under the static site root."""
from pathlib import Path
from framework.artifacts import atomic_output

PUBLIC = ('ACADEMIC_POSITIONING.md','FUNCTIONAL_COMPLETENESS.md','HEALTH.md','SELF_AUDIT.json',
          'RELEASES.md','CASE-SOFTMAX.md','QUALITY-2026-10-31.md','PAPER2AGENT.md','VERIFIERS.md',
          'ORCHESTRATION.md','CHAIN_AUDIT.md','COUPLING.md','PROJECT_INTEGRATION.md',
          'MODEL_VERDICTS.md','UPDATES.md','EVOLUTION.json','DEMO_COVERAGE.json',
          'PUBLICATION-QUALITY.md','PUBLICATION-QA.json','PUBLICATION-VISUAL-REVIEW.json',
          'MODEL_VERDICTS.md','MODEL-TASK-QUALITY.md','MODEL_TASK_READINESS.json','CAPABILITY-TRUTH-AUDIT-2026-11-01.md',
          'MONITOR-SEMANTICS.md','MONITOR-UI-ACCEPTANCE-2026-11-01.json')


def publish(root: Path):
    for name in PUBLIC:
        source=root/'docs'/name
        if source.is_file():
            with atomic_output(root/'site/docs'/name) as temporary:
                temporary.write_bytes(source.read_bytes())
    for name in ('README.md','Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'):
        source=root/name
        if source.is_file():
            with atomic_output(root/'site'/name) as temporary:
                temporary.write_bytes(source.read_bytes())
