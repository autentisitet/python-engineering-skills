#!/usr/bin/env python3
"""Validate portable Agent Skills packages and optional Codex metadata."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_DIR = ROOT / "skills"
NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")
AGENT_SKILLS_KEYS = {
    "allowed-tools", "compatibility", "description", "license", "metadata", "name",
}
OPENAI_KEYS = {"dependencies", "interface", "policy"}
INTERFACE_KEYS = {
    "brand_color", "default_prompt", "display_name", "icon_large", "icon_small",
    "short_description",
}


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    path: str
    message: str

    def render(self) -> str:
        """Render this diagnostic as one stable text line.

        中文：把诊断对象渲染为稳定的单行文本，供 CLI 和测试使用。
        """
        return f"{self.severity}: {self.code}: {self.path}: {self.message}"


def issue(severity: str, code: str, path: Path, message: str) -> Diagnostic:
    """Create a diagnostic with a normalized path string.

    中文：创建包含级别、代码、路径和消息的标准诊断对象。
    """
    return Diagnostic(severity, code, str(path), message)


def load_mapping(text: str, path: Path) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Parse a YAML mapping without exposing malformed source content.

    中文：安全解析 YAML 映射；发生错误时返回脱敏诊断而不回显原始内容。

    Security / 安全：使用 ``yaml.safe_load``，并故意不把原始 YAML 异常文本写入诊断，避免 token 等
    敏感标量被日志回显。
    """
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}, [issue("error", "yaml.invalid", path, "invalid YAML; quote ambiguous scalars or repair the frontmatter")]
    if not isinstance(value, dict):
        return {}, [issue("error", "yaml.mapping", path, "YAML document must be a mapping")]
    if not all(isinstance(key, str) for key in value):
        return {}, [issue("error", "yaml.keys", path, "YAML keys must be strings")]
    return value, []


def parse_skill(path: Path) -> tuple[dict[str, Any], list[Diagnostic]]:
    """Read and parse the YAML frontmatter of one SKILL.md.

    中文：读取单个 ``SKILL.md`` 并解析其 YAML frontmatter。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return {}, [issue("error", "skill.read", path, f"cannot read UTF-8 text: {error}")]
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, [issue("error", "frontmatter.malformed", path, "missing or malformed YAML frontmatter")]
    return load_mapping(match.group(1), path)


def validate_portable_layer(skill_dir: Path) -> list[Diagnostic]:
    """Validate portable Agent Skills frontmatter fields.

    中文：校验跨客户端可移植的 Agent Skills frontmatter 字段与类型。
    """
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        return [issue("error", "skill.missing", skill_dir, "missing SKILL.md")]
    data, diagnostics = parse_skill(path)
    if diagnostics:
        return diagnostics

    unknown = sorted(set(data) - AGENT_SKILLS_KEYS)
    if unknown:
        diagnostics.append(issue(
            "warning", "frontmatter.extension", path,
            "unknown portable fields are preserved: " + ", ".join(unknown),
        ))

    name = data.get("name")
    if not isinstance(name, str) or not name:
        diagnostics.append(issue("error", "name.missing", path, "name must be a non-empty string"))
    else:
        if len(name) > 64:
            diagnostics.append(issue("warning", "name.length", path, "name exceeds 64 characters"))
        if not NAME_PATTERN.fullmatch(name):
            diagnostics.append(issue(
                "error", "name.format", path,
                "name must use lowercase letters, digits, and single hyphens",
            ))
        if name != skill_dir.name:
            diagnostics.append(issue(
                "warning", "name.directory-mismatch", path,
                f"name does not match parent directory {skill_dir.name!r}",
            ))

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        diagnostics.append(issue("error", "description.missing", path, "description must be a non-empty string"))
    elif len(description) > 1024:
        diagnostics.append(issue("error", "description.length", path, "description must be at most 1024 characters"))

    compatibility = data.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str) or not compatibility or len(compatibility) > 500
    ):
        diagnostics.append(issue(
            "error", "compatibility.format", path,
            "compatibility must be a non-empty string of at most 500 characters",
        ))

    for key in ("license", "allowed-tools"):
        value = data.get(key)
        if value is not None and (not isinstance(value, str) or not value):
            diagnostics.append(issue("error", f"{key}.format", path, f"{key} must be a non-empty string"))

    metadata = data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            diagnostics.append(issue("error", "metadata.mapping", path, "metadata must be a mapping"))
        elif not all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()):
            diagnostics.append(issue("error", "metadata.strings", path, "metadata keys and values must be strings"))
    return diagnostics


def is_contained(root: Path, candidate: Path) -> bool:
    """Return whether a resolved candidate remains inside the package root.

    中文：解析符号链接后判断候选路径是否仍位于技能包根目录内。

    OS considerations / OS 考虑：通过 ``resolve`` 后的路径关系判断而非字符串前缀，兼容不同分隔符并
    防止 ``../`` 与符号链接穿越。
    """
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=True))
    except (OSError, ValueError, RuntimeError):
        return False
    return True


def validate_package_paths(skill_dir: Path) -> list[Diagnostic]:
    """Validate package entry count and symlink containment.

    中文：检查技能包文件数量、根目录链接和逃逸符号链接。

    Security / 安全：``os.walk`` 禁止跟随目录链接，并设置条目上限，避免循环链接与超大包导致无限
    遍历或资源消耗。
    """
    diagnostics: list[Diagnostic] = []
    if skill_dir.is_symlink():
        return [issue("error", "path.root-symlink", skill_dir, "validate the source directory, not a linked package root")]
    paths = 0
    for directory, dirs, files in os.walk(skill_dir, followlinks=False):
        paths += len(dirs) + len(files)
        if paths > 2000:
            return [issue("error", "path.limit", skill_dir, "package exceeds 2000 entries; reduce package size")]
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink() and not is_contained(skill_dir, path):
                diagnostics.append(issue("error", "path.external-symlink", path, "symlink resolves outside the skill package"))
    return diagnostics


def validate_local_links(skill_dir: Path) -> list[Diagnostic]:
    """Validate local Markdown links in the skill entrypoint.

    中文：检查技能入口中的本地 Markdown 链接是否存在且未逃逸包边界。

    Security / 安全：先去除锚点再解析目标路径，并复用包边界检查，防止 Markdown 链接读取包外文件。
    """
    path = skill_dir / "SKILL.md"
    if not path.is_file():
        return []
    diagnostics: list[Diagnostic] = []
    for raw_target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        relative = target.split("#", 1)[0]
        if not relative:
            continue
        candidate = skill_dir / relative
        if not is_contained(skill_dir, candidate):
            diagnostics.append(issue("error", "link.escape", path, f"local link escapes package: {raw_target!r}"))
        elif not candidate.resolve(strict=False).exists():
            diagnostics.append(issue("error", "link.broken", path, f"broken local link {raw_target!r}"))
    return diagnostics


def validate_authoring_structure(skill_dir: Path) -> list[Diagnostic]:
    """Check authoring guidance separately from portable validity.

    中文：检查入口长度、reference 可发现性和渐进披露结构，不混入可移植规范结论。
    """
    entrypoint = skill_dir / "SKILL.md"
    if not entrypoint.is_file():
        return []
    text = entrypoint.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    body = text[match.end():] if match else text
    diagnostics: list[Diagnostic] = []
    if len(body.splitlines()) > 500:
        diagnostics.append(issue(
            "warning", "authoring.entrypoint-length", entrypoint,
            "SKILL.md body exceeds 500 lines; move conditional detail to references",
        ))

    linked_references: set[str] = set()
    for raw_target in LINK_PATTERN.findall(body):
        target = raw_target.strip().split(maxsplit=1)[0].strip("<>").split("#", 1)[0]
        if target.startswith("references/"):
            linked_references.add(Path(target).as_posix())

    references_dir = skill_dir / "references"
    if not references_dir.is_dir():
        return diagnostics
    for path in sorted(item for item in references_dir.rglob("*.md") if item.is_file()):
        relative = path.relative_to(skill_dir).as_posix()
        if relative.count("/") > 1:
            diagnostics.append(issue(
                "warning", "authoring.reference-depth", path,
                "keep references one level below the skill entrypoint",
            ))
        if relative not in linked_references:
            diagnostics.append(issue(
                "warning", "authoring.reference-unlinked", path,
                "reference is not linked directly from SKILL.md",
            ))
        lines = path.read_text(encoding="utf-8").splitlines()
        headings = {line.strip().casefold() for line in lines[:40]}
        if len(lines) > 100 and not headings.intersection({"## contents", "## table of contents"}):
            diagnostics.append(issue(
                "warning", "authoring.reference-contents", path,
                "reference exceeds 100 lines; add a short contents section near the top",
            ))
    return diagnostics


def validate_openai_yaml(skill_dir: Path) -> list[Diagnostic]:
    """Validate optional Codex metadata in ``agents/openai.yaml``.

    中文：校验可选的 Codex UI、policy、dependency 和图标元数据。
    """
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        return []
    data, diagnostics = load_mapping(path.read_text(encoding="utf-8"), path)
    if diagnostics:
        return diagnostics

    unknown = sorted(set(data) - OPENAI_KEYS)
    if unknown:
        diagnostics.append(issue(
            "warning", "openai.extension", path,
            "unknown Codex fields are preserved: " + ", ".join(unknown),
        ))

    interface = data.get("interface", {})
    if not isinstance(interface, dict):
        diagnostics.append(issue("error", "openai.interface", path, "interface must be a mapping"))
        return diagnostics
    unknown_interface = sorted(set(interface) - INTERFACE_KEYS)
    if unknown_interface:
        diagnostics.append(issue(
            "warning", "openai.interface-extension", path,
            "unknown interface fields are preserved: " + ", ".join(unknown_interface),
        ))
    for key, value in interface.items():
        if key in INTERFACE_KEYS and (not isinstance(value, str) or not value):
            diagnostics.append(issue(
                "error", "openai.interface-value", path,
                f"interface.{key} must be a non-empty string",
            ))

    short_description = interface.get("short_description")
    if isinstance(short_description, str) and not 25 <= len(short_description) <= 64:
        diagnostics.append(issue(
            "error", "openai.short-description", path,
            "interface.short_description must be 25-64 characters",
        ))
    default_prompt = interface.get("default_prompt")
    if isinstance(default_prompt, str) and f"${skill_dir.name}" not in default_prompt:
        diagnostics.append(issue(
            "error", "openai.default-prompt", path,
            f"interface.default_prompt must reference ${skill_dir.name}",
        ))
    brand_color = interface.get("brand_color")
    if isinstance(brand_color, str) and not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
        diagnostics.append(issue(
            "error", "openai.brand-color", path,
            "interface.brand_color must be a six-digit hex color",
        ))
    for key in ("icon_small", "icon_large"):
        value = interface.get(key)
        if not isinstance(value, str):
            continue
        candidate = skill_dir / value
        if not is_contained(skill_dir, candidate):
            diagnostics.append(issue("error", "openai.icon-escape", path, f"interface.{key} escapes the package"))
        elif not candidate.resolve(strict=False).is_file():
            diagnostics.append(issue(
                "error", "openai.icon-missing", path,
                f"interface.{key} points to missing file {value!r}",
            ))

    policy = data.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            diagnostics.append(issue("error", "openai.policy", path, "policy must be a mapping"))
        elif "allow_implicit_invocation" in policy and not isinstance(policy["allow_implicit_invocation"], bool):
            diagnostics.append(issue(
                "error", "openai.policy-value", path,
                "policy.allow_implicit_invocation must be a boolean",
            ))
    if "dependencies" in data and not isinstance(data["dependencies"], dict):
        diagnostics.append(issue("error", "openai.dependencies", path, "dependencies must be a mapping"))
    return diagnostics


def validate_scripts(skill_dir: Path) -> list[Diagnostic]:
    """Validate executable skill scripts and interpreter declarations.

    中文：检查技能脚本的可执行权限和 shebang 解释器声明。
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    diagnostics: list[Diagnostic] = []
    for path in sorted(item for item in scripts_dir.rglob("*") if item.is_file()):
        if path.suffix in {".py", ".sh"} and os.name != "nt" and not os.access(path, os.X_OK):
            diagnostics.append(issue("error", "script.executable", path, "script must have the executable bit set"))
        if path.suffix in {".py", ".sh"}:
            first_line = path.read_text(encoding="utf-8").splitlines()[:1]
            if not first_line or not first_line[0].startswith("#!"):
                diagnostics.append(issue(
                    "warning", "script.shebang", path,
                    "executable script should declare an interpreter",
                ))
    return diagnostics


def validate_skill_diagnostics(skill_dir: Path) -> list[Diagnostic]:
    """Run all package validators for one skill directory.

    中文：对单个技能目录运行路径、portable、authoring、Codex 和脚本检查。

    Design / 设计：路径安全检查优先执行；发现根目录或 symlink 风险时立即返回，避免后续验证读取不可信
    外部内容。
    """
    diagnostics = validate_package_paths(skill_dir)
    if diagnostics:
        return diagnostics
    diagnostics.extend(validate_portable_layer(skill_dir))
    try:
        diagnostics.extend(validate_local_links(skill_dir))
        diagnostics.extend(validate_authoring_structure(skill_dir))
        diagnostics.extend(validate_openai_yaml(skill_dir))
        diagnostics.extend(validate_scripts(skill_dir))
    except (OSError, UnicodeError, RuntimeError):
        diagnostics.append(issue("error", "package.read", skill_dir, "cannot read package; check UTF-8 encoding and permissions"))
    return diagnostics


def parse_args() -> argparse.Namespace:
    """Parse skill-package linter CLI arguments.

    中文：解析技能目录、输出格式和严格 warning 模式参数。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--strict-warnings", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Validate all discovered skill packages and print diagnostics.

    中文：发现并校验全部技能包，输出文本或 JSON 诊断并返回退出码。
    """
    args = parse_args()
    skills_dir = args.skills_dir.resolve()
    if not skills_dir.is_dir():
        print(f"error: skills directory does not exist: {skills_dir}", file=sys.stderr)
        return 2
    skill_dirs = sorted(
        path for path in skills_dir.iterdir() if path.is_dir() and (path / "SKILL.md").exists()
    )
    if not skill_dirs:
        print(f"error: no skill packages found in {skills_dir}", file=sys.stderr)
        return 2

    diagnostics = [item for skill_dir in skill_dirs for item in validate_skill_diagnostics(skill_dir)]
    errors = sum(item.severity == "error" for item in diagnostics)
    warnings = sum(item.severity == "warning" for item in diagnostics)
    result = {
        "skills": len(skill_dirs),
        "errors": errors,
        "warnings": warnings,
        "diagnostics": [asdict(item) for item in diagnostics],
    }
    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=True, indent=2))
    else:
        for item in diagnostics:
            print(item.render(), file=sys.stderr)
        print(f"Validated {len(skill_dirs)} skill packages: {errors} error(s), {warnings} warning(s).")
    return 1 if errors or (args.strict_warnings and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
