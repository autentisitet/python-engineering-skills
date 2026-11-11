---
name: python-matplotlib-config
description: Creates and reviews Matplotlib/Seaborn global style, CJK font fallback, reusable .mplstyle files, and Figure/Axes calling style. Use when creating/editing a style sheet or configuring plotting appearance/API behavior; applies one theme mechanism before fonts and prefers Axes methods. Do not use for chart semantics, data analysis, Plotly, or image decoding.
metadata:
  short-description: Configure Matplotlib styles, CJK fonts, and Axes usage
---

# Python Matplotlib Configuration

## Activation

- **Keyword trigger:** the task substantively involves Matplotlib `rcParams`, `plt.style.use`, `sns.set_theme`, `.mplstyle`, Chinese/CJK fonts, `Figure`, `Axes`, or pyplot state.
- **Intent trigger:** the user asks to configure consistent Matplotlib appearance or review object-oriented versus state-machine plotting calls.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-matplotlib-config because this task involves Matplotlib configuration.`
- **Exit:** stop applying this skill after style, font, and Figure/Axes ownership decisions are complete.
- **Do not trigger:** ordinary chart design, statistical interpretation, data analysis, non-Matplotlib plotting, or a library name in unrelated text is insufficient.

---

## Configure Theme Before Fonts

1. Select one process-wide theme entry point: either `plt.style.use(...)` or `sns.set_theme(...)`.
2. Apply the chosen theme before setting CJK font fallback. Both mechanisms modify global Matplotlib `rcParams`; a later theme call can replace earlier font settings.
3. After the theme, configure an ordered installed-font fallback list and `axes.unicode_minus` only if minus glyphs require it.
4. Verify the actual target system has at least one requested CJK font. Do not assume a font name is portable across Fedora, Windows, containers, and CI.

Prefer a project `.mplstyle` when several entry points need the same stable appearance. Keep platform-dependent font detection or overrides after loading the style if the style must run on heterogeneous systems.

Read [references/configuration-guide.md](references/configuration-guide.md) for ordering and verification examples.

---

## Prefer Figure and Axes Methods

- Create objects explicitly with `fig, ax = plt.subplots(...)`.
- Prefer `ax.plot`, `ax.set_title`, `ax.set_xlabel`, `ax.legend`, and other Axes methods.
- Use pyplot primarily for Figure creation, style/context management, interactive display, and explicit cleanup.
- Save with `fig.savefig(...)`; close owned figures with `plt.close(fig)` in batch or service code.
- Reusable functions should accept an `Axes` or return the created Figure/Axes instead of mutating `plt.gca()` state.

---

## Scope Global Mutation

- Applications may configure one global style during startup when they own the process.
- Libraries should not change global themes or fonts at import time. Accept configuration or use `plt.style.context(...)` / `matplotlib.rc_context(...)` for scoped changes.
- Do not combine multiple theme systems merely to accumulate preferred options. Put deliberate shared values into one style sheet or one theme call.

---

## Required Output

Report only what the task needs: selected theme mechanism, ordering relative to font fallback, installed-font verification, whether an `.mplstyle` is appropriate, Figure/Axes ownership, and cleanup behavior.
