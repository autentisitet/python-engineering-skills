# Scikit-Learn Preprocessing and Inspection

## Pipeline and ColumnTransformer

Use `Pipeline` whenever a learned transformation must be refit inside each train/CV partition. This includes imputation, scaling, encoding, feature selection, PCA, and many target-independent transforms that still learn from `X`.

Use `ColumnTransformer` to apply separate pipelines to column subsets, for example:

```python
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

numeric = Pipeline(
    [
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ]
)
categorical = Pipeline(
    [
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OneHotEncoder(handle_unknown="ignore")),
    ]
)
preprocess = ColumnTransformer(
    [
        ("numeric", numeric, numeric_columns),
        ("categorical", categorical, categorical_columns),
    ]
)
```

Combine the transformer and estimator in one outer Pipeline before CV/search. Preserve feature names when inspection or debugging requires mapping transformed features back to source columns.

---

## PCA and Scaling

Scikit-learn PCA centers features but does not scale each feature to unit variance. Standardize before PCA when features use different units/scales and those scales should not determine component variance. Keep original scale when magnitude is semantically meaningful or features already share a justified scale.

Place scaler and PCA inside the Pipeline so each fold learns means, variances, and components from training data only. Consider sparse input, outliers, memory, `n_components`, solver constraints, and whether `whiten=True` changes downstream semantics.

Do not assume PCA improves every model. Compare a no-PCA pipeline and inspect explained variance, performance, fit time, and interpretability.

---

## sklearn.inspection

Use inspection after defining a reliable fitted-model evaluation:

- `permutation_importance`: model-agnostic score degradation when a feature is shuffled. Prefer held-out data to study generalization dependence.
- `PartialDependenceDisplay`: average marginal predictions over feature values.
- ICE through partial dependence displays: per-sample response heterogeneity.
- `DecisionBoundaryDisplay`: low-dimensional decision-region diagnostics.

Important limits:

- permutation importance describes this fitted model and scorer, not intrinsic causal feature value;
- correlated features can make each other appear weak under individual permutation;
- low baseline performance makes feature importance uninformative;
- PDP/ICE can evaluate unrealistic feature combinations when features are dependent; and
- inspection on the training set can emphasize overfit relationships.

Define the question and evaluation dataset before adding inspection code.

Official references:

- <https://scikit-learn.org/stable/common_pitfalls.html>
- <https://scikit-learn.org/stable/modules/compose.html>
- <https://scikit-learn.org/stable/modules/decomposition.html>
- <https://scikit-learn.org/stable/inspection.html>
