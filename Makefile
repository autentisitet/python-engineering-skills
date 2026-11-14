PYTHON ?= python3
TARGET ?=
DATASET ?= evals/train_queries.json
RUNS ?= 1
RETRY_RESULT ?= evals/results/activation-validation.json
RETRY_DATASET ?= evals/validation_queries.json
RETRY_OUTPUT ?= evals/results/validation-timeout-retry.json
CROSS_BASELINE ?= evals/results/activation-validation-current.json
CROSS_DATASET ?= evals/validation_queries.json
CROSS_MODEL ?=
CROSS_OUTPUT ?= evals/results/activation-validation-cross.json

.DEFAULT_GOAL := usage

.PHONY: usage validate install remove eval smoke queries-csv queries-json queries-checksum queries-check retry-dataset cross-check

usage:
	@printf '%s\n' \
	  'Project commands:' \
	  '  make validate' \
	  '  make install TARGET=/path/to/project' \
	  '  make remove TARGET=/path/to/project' \
	  '  make eval' \
	  '  make queries-csv' \
	  '  make queries-json' \
	  '  make queries-checksum' \
	  '  make queries-check' \
	  '  make retry-dataset' \
	  '  make cross-check CROSS_MODEL=deepseek-v4-pro' \
	  '  make smoke [DATASET=evals/train_queries.json RUNS=1]'

validate:
	@$(PYTHON) -m scripts.packages.lint_skill_packages --strict-warnings
	@$(PYTHON) -m scripts.evals.validate_evals
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/train_queries.csv .tmp/train-check.json --split train --split-seed 20261112 >/dev/null
	@diff -u evals/train_queries.json .tmp/train-check.json
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/validation_queries.csv .tmp/validation-check.json --split validation --split-seed 20261112 >/dev/null
	@diff -u evals/validation_queries.json .tmp/validation-check.json
	@rm -f .tmp/train-check.json .tmp/validation-check.json
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
	@bash -n scripts/links/install.sh scripts/links/uninstall.sh

install:
	@test -n "$(TARGET)" || { echo 'Usage: make install TARGET=/path/to/project' >&2; exit 2; }
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
	@$(PYTHON) -m scripts.evals.run_activation_evals $(DATASET) --runs $(RUNS) \
	  --sample-per-label 1 --allow-model-calls --reasoning-effort low \
	  --output evals/results/activation-smoke.json

queries-csv:
	@$(PYTHON) -m scripts.evals.convert_queries to-csv evals/train_queries.json evals/train_queries.csv
	@$(PYTHON) -m scripts.evals.convert_queries to-csv evals/validation_queries.json evals/validation_queries.csv

queries-json:
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/train_queries.csv evals/train_queries.json --split train --split-seed 20261112
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/validation_queries.csv evals/validation_queries.json --split validation --split-seed 20261112

queries-checksum:
	@sha256sum evals/train_queries.json evals/train_queries.csv evals/validation_queries.json evals/validation_queries.csv

queries-check:
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/train_queries.csv .tmp/train-check.json --split train --split-seed 20261112 >/dev/null
	@$(PYTHON) -m scripts.evals.convert_queries to-json evals/validation_queries.csv .tmp/validation-check.json --split validation --split-seed 20261112 >/dev/null
	@diff -u evals/train_queries.json .tmp/train-check.json
	@diff -u evals/validation_queries.json .tmp/validation-check.json
	@rm -f .tmp/train-check.json .tmp/validation-check.json

retry-dataset:
	@$(PYTHON) -m scripts.evals.extract_retry_cases \
	  --result $(RETRY_RESULT) --dataset $(RETRY_DATASET) --output $(RETRY_OUTPUT)

cross-check:
	@test -n "$(CROSS_MODEL)" || { echo 'Usage: make cross-check CROSS_MODEL=deepseek-v4-pro' >&2; exit 2; }
	@$(PYTHON) -m scripts.evals.cross_check_evals \
	  --baseline $(CROSS_BASELINE) --dataset $(CROSS_DATASET) \
	  --model $(CROSS_MODEL) --allow-model-calls --output $(CROSS_OUTPUT)
