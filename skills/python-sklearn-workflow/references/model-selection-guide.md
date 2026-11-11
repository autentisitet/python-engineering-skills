# Scikit-Learn Model Selection Guide

## Splitter Selection

| Data dependency | Prefer | Main check |
| --- | --- | --- |
| IID regression or sufficiently balanced classification | `KFold` | Shuffle only when order is not meaningful; set an integer seed when shuffling |
| Binary/multiclass labels with fold-level class scarcity | `StratifiedKFold` | Preserves approximate class proportions; it can understate variability |
| Repeated observations from the same entity/session | `GroupKFold` | No group may cross train/validation; distinct groups must cover `n_splits` |
| Ordered observations evaluated on future data | `TimeSeriesSplit` | Preserve order; consider `gap`, `test_size`, and unequal temporal spacing |
| Class balance plus non-overlapping groups | `StratifiedGroupKFold` | Balance is approximate and must not override group isolation |

Do not use random K-fold validation for future prediction, and do not use stratification as a substitute for group or temporal independence. Visualize or inspect several generated splits when groups, rare classes, or time boundaries are complex.

---

## Holdout Proportion

There is no universally correct 80/20 or 70/30 split. Choose enough final-test observations to estimate the required metric with useful uncertainty while retaining enough development data to fit and tune the model. Check:

- absolute number of minority-class examples, groups, and time periods in each partition;
- whether the test distribution represents production;
- whether related records can leak across the boundary;
- whether hyperparameter search needs a separate validation process; and
- whether a small dataset needs nested/repeated CV instead of a large fixed holdout.

Do not repeatedly inspect the final test score while tuning; that turns the test set into development data.

---

## Cross-Validation Results

Use `cross_val_score` when only one scorer and fold scores are needed. Use `cross_validate` for multiple scorers, train scores, timings, or returned estimators. Report fold distribution or uncertainty, not only a mean.

Ensure the metric matches the product cost and target distribution. For imbalanced classification, accuracy alone is usually insufficient; select metrics and thresholds separately.

---

## Search Strategy

- **`GridSearchCV`:** small discrete space, interactions matter, and every combination is affordable.
- **`RandomizedSearchCV`:** large/high-dimensional space, continuous distributions, or fixed compute budget. Useful when only a subset of parameters materially affects performance.
- Use distributions appropriate to scale, such as log-spaced or log-uniform values for multiplicative regularization parameters.
- Include preprocessing and PCA choices inside the searched Pipeline when they are model decisions.
- Record candidate count, folds, scoring, parallelism, refit rule, and total fit count before starting expensive searches.

Search CV results are optimistic for the selected candidate. Use the untouched test set or nested CV for final generalization assessment.

---

## Diagnostic Curves

- `learning_curve`: vary training-set size and compare train/validation scores to diagnose data sufficiency, bias, and variance.
- `validation_curve`: vary one parameter and compare train/validation scores to understand sensitivity, underfitting, or overfitting.

Use the same leakage-safe pipeline, splitter, scoring, and group/time semantics as the main evaluation. Curves explain behavior; they do not automatically select a deployable model.

Official references:

- <https://scikit-learn.org/stable/modules/cross_validation.html>
- <https://scikit-learn.org/stable/modules/grid_search.html>
- <https://scikit-learn.org/stable/modules/learning_curve.html>
