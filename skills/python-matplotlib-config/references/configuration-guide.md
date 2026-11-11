# Matplotlib Configuration Guide

## Startup Ordering

Use one of these global theme paths, then apply fonts:

```python
import matplotlib.pyplot as plt

plt.style.use("./config/project.mplstyle")
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Noto Sans CJK SC",
            "Microsoft YaHei",
            "SimHei",
            "DejaVu Sans",
        ],
        "axes.unicode_minus": False,
    }
)
```

Or, when Seaborn owns the application theme:

```python
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Noto Sans CJK SC", "DejaVu Sans"],
        "axes.unicode_minus": False,
    }
)
```

Do not call another global theme function after the font update. If existing startup code does so, consolidate the configuration or reapply the deliberate font settings after the final theme call.

---

## Style Sheet Decision

Use a versioned `.mplstyle` for stable colors, sizes, line widths, grids, and layout defaults shared across scripts. A style sheet can also contain font family lists, but those names still depend on installed system fonts. Keep dynamic platform detection in Python when the deployment environments differ.

Later styles override conflicting values from earlier styles. If composing styles, keep the order explicit and test the final `rcParams`.

---

## Verification

- Query installed fonts or use `matplotlib.font_manager.findfont(..., fallback_to_default=False)` for required families.
- Render Chinese text, ASCII text, digits, and a negative value in the target headless/backend environment.
- Assert the final relevant `rcParams` after all startup configuration has run.
- For reusable plotting functions, test the returned artists and that the supplied Axes was modified.

Official references:

- <https://matplotlib.org/stable/users/explain/customizing.html>
- <https://matplotlib.org/stable/users/explain/fonts.html>
- <https://seaborn.pydata.org/generated/seaborn.set_theme.html>
