---
name: python-sklearn-workflow
description: Designs leakage-safe scikit-learn splits, cross-validation, scoring, search, diagnostic curves, PCA scaling, model inspection, ColumnTransformer, and Pipelines. Use when building or reviewing an sklearn evaluation workflow. Do not use for ordinary prediction with an already-fitted estimator, plotting already-computed predictions, experiment tracking after evaluation design is fixed, deep-learning frameworks, estimator theory alone, or incidental sklearn imports.
metadata:
  short-description: Design leakage-safe scikit-learn evaluation workflows
---

# Python Scikit-Learn Workflow

## Activation

- **Keyword trigger:** the task substantively involves scikit-learn model selection, `KFold`, `StratifiedKFold`, `GroupKFold`, `TimeSeriesSplit`, `cross_validate`, `GridSearchCV`, `RandomizedSearchCV`, learning/validation curves, PCA, `sklearn.inspection`, `ColumnTransformer`, or `Pipeline`.
- **Intent trigger:** the user asks how to split, preprocess, tune, diagnose, or interpret a scikit-learn model without leakage.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-sklearn-workflow because this task involves scikit-learn evaluation or preprocessing.`
- **Exit:** stop applying this skill when the split, CV, preprocessing, search, and diagnostic contracts are settled.
- **Do not trigger:** a dependency update, experiment tracking when splitting/tuning are already fixed, ordinary `predict` call on an already-fitted estimator, report-only plotting from already-computed predictions, isolated estimator API question, deep-learning pipeline, or incidental import is insufficient. Plotting belongs here only when the task changes scoring, evaluation design, diagnostic methodology, or model inspection.

---

## Start With the Evaluation Unit

Before choosing a splitter, identify what must remain independent between training and evaluation:

- individual IID observations;
- class labels with rare outcomes;
- users, patients, devices, sessions, locations, or other groups;
- chronological future observations; or
- a combination of class balance and non-overlapping groups.

Choose the test set and CV strategy from that unit, not from a preferred default percentage. Read [references/model-selection-guide.md](references/model-selection-guide.md) for splitter and search choices.

---

## Keep Preprocessing Inside the Fold

- Split off any final test set before fitting scalers, imputers, encoders, feature selectors, PCA, or other learned transforms.
- Put learned preprocessing and the estimator in `Pipeline` so each CV fold fits transformations only on its training partition.
- Use `ColumnTransformer` when numeric, categorical, text, or other column subsets need different transformations.
- Search nested parameters through pipeline names such as `preprocess__numeric__scaler` or `model__C`.
- Do not manually preprocess the full dataset before `cross_val_score`, `cross_validate`, grid search, or randomized search.

Read [references/preprocessing-inspection.md](references/preprocessing-inspection.md) for PCA, inspection, and heterogeneous columns.

---

## Select Evaluation and Search Tools Deliberately

- Use `cross_val_score` for one metric and simple fold scores.
- Use `cross_validate` when multiple metrics, train scores, fit/score times, or returned estimators are genuinely needed.
- Use `GridSearchCV` for a small, discrete, justified parameter grid where exhaustive combinations fit the compute budget.
- Use `RandomizedSearchCV` for larger spaces, distributions, or a fixed candidate budget. Set `n_iter` and parameter distributions deliberately.
- Keep the same CV semantics and scoring contract across model comparisons. Pass groups/metadata correctly when the splitter requires them.
- Preserve an untouched test set or use an appropriate nested evaluation when model selection consumes all development folds.

---

## Add Curves and Inspection to Answer a Question

- Use `learning_curve` to ask whether more training data is likely to reduce a train/validation gap or whether both scores have plateaued.
- Use `validation_curve` to inspect one hyperparameter's train/validation behavior. It is not a replacement for multi-parameter search or final testing.
- Use `sklearn.inspection.permutation_importance` to measure dependence of a fitted model's score on features, preferably on held-out data after confirming the model has useful predictive performance.
- Use partial dependence or ICE only when their assumptions and the feature distribution make the result interpretable.
- Do not add inspection plots mechanically. Define the debugging, reliability, or interpretability question first.

---

## Required Output

State the independent evaluation unit; holdout proportion rationale; selected CV splitter and scoring; preprocessing/PCA placement; grid or randomized search budget; whether learning/validation curves answer a concrete question; inspection method and dataset; leakage controls; and the final untouched evaluation path.
