"""Publish a fixed set of public source documents under the static site root."""
from pathlib import Path
from framework.artifacts import atomic_output

PUBLIC = ('ACADEMIC_POSITIONING.md','FUNCTIONAL_COMPLETENESS.md','HEALTH.md','SELF_AUDIT.json',
          'NUMERICAL-PROGRAMS.md','NUMERICAL-PROGRAMS-ACCEPTANCE.json',
          'RELEASES.md','CASE-SOFTMAX.md','QUALITY-2026-10-31.md','PAPER2AGENT.md','VERIFIERS.md',
          'ORCHESTRATION.md','CHAIN_AUDIT.md','COUPLING.md','PROJECT_INTEGRATION.md',
          'CLI-REUSE-DEVELOPMENT.md','RELEASE-PUBLICATION-0.4.12.json',
          'MODEL_VERDICTS.md','UPDATES.md','EVOLUTION.json','DEMO_COVERAGE.json',
          'PUBLICATION-QUALITY.md','PUBLICATION-QA.json','PUBLICATION-VISUAL-REVIEW.json',
          'MODEL-TASK-QUALITY.md','MODEL_TASK_READINESS.json','CAPABILITY-TRUTH-AUDIT-2026-11-01.md',
          'RSI-READINESS-2026-11-01.md','LOCAL-MODEL-CAPACITY-2026-11-01.md',
          'LOCAL-MODEL-CAPACITY-2026-11-01.json','RELEASE-CHECKS.md',
          'MONITOR-SEMANTICS.md','MONITOR-UI-ACCEPTANCE-2026-11-01.json','CONSUMER-OBSERVATION-ACCEPTANCE.json',
          'EXECUTABLE-DELIVERY.md','PACKAGE-ACCEPTANCE.json',
          'CRON-ISOLATION.md','CRON-SCHEDULER-ACCEPTANCE-2026-11-01.json',
          'INDEPENDENT-INTAKE-ACCEPTANCE.json','MONITOR-RUNTIME-MIGRATION-2026-11-01.json',
          'INDEPENDENT-LIFECYCLE-ACCEPTANCE.json','STARTUP-RUNTIME-ACCEPTANCE-2026-11-01.json',
          '_coupling.json','REPORT-PUBLICATION-ACCEPTANCE-2026-11-01.json',
          'SDK-EXECUTION.md','SDK-PROCESS-ACCEPTANCE.json',
          'QUARTO-DELIVERY.md','QUARTO-DELIVERY-ACCEPTANCE.json',
          'archive/sdk-process-acceptance-v0.4.6.json','archive/sdk-process-acceptance-v0.4.7.json',
          'archive/startup-runtime-acceptance-v0.4.7.json',
          'SCHEDULING-POLICY.md','SCHEDULING-ACCEPTANCE-2026-11-01.json',
          'CRON-RETIREMENT-2026-11-01.json','CORE-RECOVERY-ACCEPTANCE.json',
          'RECOVERY-ACCEPTANCE.md','RECOVERY-LIVE-ACCEPTANCE.json','RECOVERY-SHELL-2026-11-02.md',
          'TRACKING-INTEGRITY.md','TRACKING-ACCEPTANCE.json','LOCK-COMPATIBILITY.md',
          'archive/core-recovery-acceptance-c12acdd.json',
          'archive/sdk-process-acceptance-v0.4.8.json','archive/quarto-delivery-acceptance-v0.4.8.json',
          'archive/reproduction-acceptance-v0.4.8.json',
          'archive/self-audit-v0.4.9.json','archive/core-recovery-acceptance-v0.4.9.json',
          'archive/recovery-live-acceptance-v0.4.9.json','archive/sdk-process-acceptance-v0.4.9.json',
          'archive/quarto-delivery-acceptance-v0.4.9.json','archive/reproduction-acceptance-v0.4.9.json',
          'archive/self-audit-v0.4.10.json','archive/core-recovery-acceptance-v0.4.10.json',
          'archive/recovery-live-acceptance-v0.4.10.json','archive/sdk-process-acceptance-v0.4.10.json',
          'archive/quarto-delivery-acceptance-v0.4.10.json','archive/reproduction-acceptance-v0.4.10.json',
          'archive/tracking-acceptance-v0.4.10.json',
          'REPRODUCTION-INTEGRITY.md','REPRODUCTION-ACCEPTANCE.json')

PUBLIC_ASSETS = ('docs/screens/web/index-top.webp',
                 'reference/package_delivery_acceptance/package.zip',
                 'reference/sdk_process_acceptance/eidos-0.4.6-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.7-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.8-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.9-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.10-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.11-py3-none-any.whl',
                 'reference/sdk_process_acceptance/eidos-0.4.12-py3-none-any.whl',
                 'reference/recovery_shell_acceptance/check.py',
                 'reference/recovery_shell_acceptance/bootstrap.py',
                 'reference/numerical_programs_acceptance/check.py',
                 'reference/tracking_acceptance/check.py','reference/tracking_acceptance/README.md',
                 'reference/recovery_acceptance/check.py','reference/recovery_acceptance/service.py',
                 'reference/recovery_acceptance/README.md',
                 'reference/reproduction_acceptance/check.py',
                 'reference/sdk_process_acceptance/check.py',
                 'reference/quarto_delivery_acceptance/check.py')


def publish(root: Path):
    for name in PUBLIC:
        source=root/'docs'/name
        if source.is_file():
            with atomic_output(root/'site/docs'/name) as temporary:
                temporary.write_bytes(source.read_bytes())
    for name in ('README.md','Quarto_Centric_Local_Research_Pipeline_Technical_Framework.md'):
        source=root/name
        if source.is_file():
            body=source.read_bytes()
            if name=='README.md':
                # This copy lives inside site/, where source-root site/ links move up one level.
                body=body.replace(b'](site/',b'](')
            with atomic_output(root/'site'/name) as temporary:
                temporary.write_bytes(body)
    for name in PUBLIC_ASSETS:
        source=root/name
        if source.is_file():
            with atomic_output(root/'site'/name) as temporary:
                temporary.write_bytes(source.read_bytes())
