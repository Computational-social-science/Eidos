# Eidos — common tasks
# Everything here is a thin wrapper over the documented commands, so a reader
# can always run the underlying command directly.

PY ?= python
PROJECT ?=
KIND ?=

.PHONY: help test bootstrap render package projects check-project exec-project audit clean

help:
	@echo "make test                      run the framework test suite"
	@echo "make audit                     exercise every chain end to end"
	@echo "make bootstrap PROJECT=name    create projects/name from the skeleton"
	@echo "make render PROJECT=name       render an in-tree project's manuscript"
	@echo "make package PROJECT=name      build an in-tree project's Docker/Binder package"
	@echo "make projects                  list registered (external) projects"
	@echo "make check-project PROJECT=name run a registered project's gate command"
	@echo "make exec-project PROJECT=name KIND=gate|test|render"
	@echo "make clean                     remove caches (not project data)"
	@echo ""
	@echo "PY selects the interpreter (default: python). On this host 'python' can be"
	@echo "a 3.15 install without the project dependencies; pass the interpreter that"
	@echo "has them:  make test PY=C:/Python314/python.exe"

test:
	$(PY) -m pytest tests/ -q

audit:
	$(PY) tools/audit_chains.py $(if $(CHECKER),--project-checker $(CHECKER),)

# Calibration of the decision operator; SKIPs (exit 3) when the service is down.
probe:
	$(PY) tools/decision_probe.py --n 100 --json artifacts/decision_calibration_100.json

# Import graph: cycles, hard vs soft edges, process/network boundaries. Exit 1 on cycles.
coupling:
	$(PY) tools/audit_coupling.py --symbols --json artifacts/coupling.json

# The six external contracts (quarto, dvc, mlflow, decision, bootloops, runtimes).
contracts:
	$(PY) tools/contract_snapshot.py

contracts-check:
	$(PY) tools/contract_snapshot.py --check

projects:
	$(PY) -m framework.project list

check-project:
	@test -n "$(PROJECT)" || (echo "PROJECT is required: make check-project PROJECT=name" && exit 1)
	$(PY) -m framework.project check $(PROJECT)

exec-project:
	@test -n "$(PROJECT)" || (echo "PROJECT is required: make exec-project PROJECT=name KIND=gate" && exit 1)
	@test -n "$(KIND)" || (echo "KIND is required: gate, test or render" && exit 1)
	$(PY) -m framework.project exec $(PROJECT) $(KIND)

bootstrap:
	@test -n "$(PROJECT)" || (echo "PROJECT is required: make bootstrap PROJECT=name" && exit 1)
	bash bootstrap_project.sh $(PROJECT)

render:
	@test -n "$(PROJECT)" || (echo "PROJECT is required: make render PROJECT=name" && exit 1)
	@test ! -f projects/$(PROJECT)/project.yaml || (echo "$(PROJECT) is an external project; use: make exec-project PROJECT=$(PROJECT) KIND=render" && exit 1)
	cd projects/$(PROJECT)/manuscript && quarto render index.qmd

package:
	@test -n "$(PROJECT)" || (echo "PROJECT is required: make package PROJECT=name" && exit 1)
	@test ! -f projects/$(PROJECT)/project.yaml || (echo "$(PROJECT) is an external project; it builds its own package" && exit 1)
	$(PY) projects/$(PROJECT)/scripts/build_package.py --docker --binder

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
