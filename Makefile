PYTHON ?= python3
TARGET ?=
DATASET ?= evals/train_queries.json
RUNS ?= 1

.DEFAULT_GOAL := usage

.PHONY: usage validate use remove eval smoke

usage:
	@printf '%s\n' \
	  'Project commands:' \
	  '  make validate' \
	  '  make use TARGET=/path/to/project' \
	  '  make remove TARGET=/path/to/project' \
	  '  make eval' \
	  '  make smoke [DATASET=evals/train_queries.json RUNS=1]'

validate:
	@$(PYTHON) -m scripts.packages.lint_skill_packages --strict-warnings
	@$(PYTHON) -m scripts.evals.validate_evals
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	@bash -n scripts/links/install.sh scripts/links/uninstall.sh

use:
	@test -n "$(TARGET)" || { echo 'Usage: make use TARGET=/path/to/project' >&2; exit 2; }
	@./scripts/links/install.sh "$(TARGET)"

remove:
	@test -n "$(TARGET)" || { echo 'Usage: make remove TARGET=/path/to/project' >&2; exit 2; }
	@./scripts/links/uninstall.sh "$(TARGET)"

eval: validate
	@if command -v codex >/dev/null 2>&1; then \
	  $(PYTHON) -m scripts.evals.check_skill_discovery --output evals/results/discovery.json; \
	else \
	  printf '%s\n' 'skip skill discovery (codex CLI not found)'; \
	fi
	@printf '%s\n' \
	  '' \
	  'Free checks complete. Optional Codex-backed step:' \
	  '  make smoke         behavior smoke, 1 positive + 1 negative per skill' \
	  ''

smoke:
	@$(PYTHON) -m scripts.evals.run_activation_evals $(DATASET) --runs $(RUNS) --jobs 1 \
	  --sample-per-label 1 --allow-model-calls --output evals/results/activation-smoke.json
