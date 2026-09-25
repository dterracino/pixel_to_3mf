"""Portable per-file metrics and refactoring reports for Python codebases.

Paths are relative to the repository root (the parent of this script's tools
directory), regardless of the current working directory. With no target, the
whole repository is scanned using exclusions from code_metrics.json.

Examples:
    python tools/code_metrics.py
    python tools/code_metrics.py color_tools/api
    python tools/code_metrics.py --path color_tools --sort lines
    python tools/code_metrics.py . --exclude "tooling/**"
    python tools/code_metrics.py color_tools --report
    python tools/code_metrics.py --show-config
"""

# code-metrics: accept lines -- kept as one file so the tool remains portable.
# code-metrics: accept classes -- small immutable report records are colocated.


from __future__ import annotations

import argparse
import ast
import copy
import fnmatch
import io
import json
import os
import re
import shutil
import sys
import tempfile
import tokenize
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

try:
    import rich  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = Path(__file__).with_suffix(".json")
SORT_KEYS = (
    "path", "size", "lines", "code", "comment", "classes", "functions",
    "methods", "monoliths", "chars",
)
ACCEPT_MARKER_RE = re.compile(
    r"#\s*code-metrics:\s*accept\s+(lines|classes|monoliths)\b",
    re.IGNORECASE,
)
UNSET = object()

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "scan": {
        "target": ".",
        "use_default_exclusions": True,
        "excluded_directory_names": [
            ".git", ".hg", ".svn", ".venv", "venv", "env", "ENV",
            "__pypackages__", "site-packages", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".ruff_cache", ".pyright", ".hypothesis", ".tox",
            ".nox", ".cache", "build", "dist", ".eggs", "eggs", "htmlcov",
            ".vscode", ".idea", ".vercel", "node_modules",
        ],
        "excluded_directory_patterns": ["*.egg-info"],
        "exclude_paths": [],
    },
    "thresholds": {
        "lines": 500,
        "code_lines": 500,
        "classes": 1,
        "definition_lines": 100,
    },
    "terminal": {
        "sort": "path",
        "color": "auto",
        "problems_only": False,
        "fail_on_problems": False,
    },
    "report": {
        "enabled": False,
        "path": "code_metrics_report.md",
        "include_accepted_findings": True,
    },
}


class ConfigError(ValueError):
    """A configuration file or merged option is invalid."""


@dataclass(frozen=True)
class ScanConfig:
    target: str
    use_default_exclusions: bool
    excluded_directory_names: tuple[str, ...]
    excluded_directory_patterns: tuple[str, ...]
    exclude_paths: tuple[str, ...]


@dataclass(frozen=True)
class Thresholds:
    lines: int | None
    code_lines: int | None
    classes: int | None
    definition_lines: int | None


@dataclass(frozen=True)
class TerminalConfig:
    sort: str
    color: str
    problems_only: bool
    fail_on_problems: bool


@dataclass(frozen=True)
class MarkdownReportConfig:
    enabled: bool
    path: str
    include_accepted_findings: bool


@dataclass(frozen=True)
class EffectiveConfig:
    scan: ScanConfig
    thresholds: Thresholds
    terminal: TerminalConfig
    report: MarkdownReportConfig
    source: str


@dataclass(frozen=True)
class ClassMetric:
    qualified_name: str
    line: int


@dataclass(frozen=True)
class DefinitionMetric:
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    span: int


@dataclass(frozen=True)
class FileMetrics:
    path: Path
    display_path: str
    size_bytes: int
    line_count: int
    code_line_count: int | None
    comment_line_count: int | None
    char_count: int | None
    classes: tuple[ClassMetric, ...]
    definitions: tuple[DefinitionMetric, ...]
    accepted_checks: frozenset[str]
    error_category: str | None = None
    error: str | None = None

    @property
    def class_count(self) -> int | None:
        return None if self.error else len(self.classes)

    @property
    def function_count(self) -> int | None:
        return None if self.error else sum(d.kind == "function" for d in self.definitions)

    @property
    def method_count(self) -> int | None:
        return None if self.error else sum(d.kind == "method" for d in self.definitions)


@dataclass(frozen=True)
class Finding:
    category: str
    measured: int | None
    threshold: int | None
    overage: int
    accepted: bool
    detail: str = ""
    line: int | None = None


@dataclass(frozen=True)
class FileReport:
    metrics: FileMetrics
    findings: tuple[Finding, ...]

    @property
    def unresolved(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if not f.accepted)

    @property
    def accepted(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.accepted)


@dataclass(frozen=True)
class Summary:
    files_scanned: int
    files_with_problems: int
    line_findings: int
    class_findings: int
    monolith_findings: int
    analysis_errors: int
    total_size: int
    total_lines: int
    total_code: int
    total_comment: int
    total_classes: int
    total_functions: int
    total_methods: int
    total_monoliths: int
    total_chars: int


@dataclass(frozen=True)
class MetricsReport:
    files: tuple[FileReport, ...]
    summary: Summary


def _merge_known(base: dict[str, Any], override: dict[str, Any], prefix: str = "") -> None:
    for key, value in override.items():
        field = f"{prefix}.{key}" if prefix else key
        if key not in base:
            raise ConfigError(f"unknown configuration field: {field}")
        if isinstance(base[key], dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{field} must be an object")
            _merge_known(base[key], value, field)
        else:
            base[key] = value


def _string(value: Any, field: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ConfigError(f"{field} must be a nonempty string")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ConfigError(f"{field} must be true or false")
    return value


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigError(f"{field} must be an array of nonempty strings")
    return tuple(_string(item, f"{field}[{index}]") for index, item in enumerate(value))


def _threshold(value: Any, field: str, *, allow_zero: bool = False) -> int | None:
    if value is None:
        return None
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum:
        qualifier = "a nonnegative" if allow_zero else "a positive"
        raise ConfigError(f"{field} must be {qualifier} integer or null")
    return value


def _validate_relative(value: str, field: str) -> str:
    path = Path(value)
    if not path.is_absolute() and ".." in path.parts:
        raise ConfigError(f"{field} must not escape the repository root with '..'")
    return value


def _build_config(raw: dict[str, Any], source: str) -> EffectiveConfig:
    if raw["schema_version"] != 1 or type(raw["schema_version"]) is not int:
        raise ConfigError("schema_version must be 1")
    scan = raw["scan"]
    thresholds = raw["thresholds"]
    terminal = raw["terminal"]
    report = raw["report"]
    target = _validate_relative(_string(scan["target"], "scan.target"), "scan.target")
    exclude_paths = _strings(scan["exclude_paths"], "scan.exclude_paths")
    for index, pattern in enumerate(exclude_paths):
        _validate_relative(pattern, f"scan.exclude_paths[{index}]")
    sort = _string(terminal["sort"], "terminal.sort")
    if sort not in SORT_KEYS:
        raise ConfigError(f"terminal.sort must be one of: {', '.join(SORT_KEYS)}")
    color = _string(terminal["color"], "terminal.color")
    if color not in {"auto", "always", "never"}:
        raise ConfigError('terminal.color must be "auto", "always", or "never"')
    report_path = _validate_relative(_string(report["path"], "report.path"), "report.path")
    return EffectiveConfig(
        scan=ScanConfig(
            target=target,
            use_default_exclusions=_boolean(scan["use_default_exclusions"], "scan.use_default_exclusions"),
            excluded_directory_names=_strings(scan["excluded_directory_names"], "scan.excluded_directory_names"),
            excluded_directory_patterns=_strings(scan["excluded_directory_patterns"], "scan.excluded_directory_patterns"),
            exclude_paths=exclude_paths,
        ),
        thresholds=Thresholds(
            lines=_threshold(thresholds["lines"], "thresholds.lines"),
            code_lines=_threshold(thresholds["code_lines"], "thresholds.code_lines"),
            classes=_threshold(thresholds["classes"], "thresholds.classes", allow_zero=True),
            definition_lines=_threshold(thresholds["definition_lines"], "thresholds.definition_lines"),
        ),
        terminal=TerminalConfig(
            sort=sort,
            color=color,
            problems_only=_boolean(terminal["problems_only"], "terminal.problems_only"),
            fail_on_problems=_boolean(terminal["fail_on_problems"], "terminal.fail_on_problems"),
        ),
        report=MarkdownReportConfig(
            enabled=_boolean(report["enabled"], "report.enabled"),
            path=report_path,
            include_accepted_findings=_boolean(
                report["include_accepted_findings"], "report.include_accepted_findings"
            ),
        ),
        source=source,
    )


def _load_raw_config(path: Path | None, *, explicit: bool) -> tuple[dict[str, Any], str]:
    raw = copy.deepcopy(DEFAULT_CONFIG)
    if path is None or (not explicit and not path.is_file()):
        return raw, "built-in defaults"
    if not path.is_file():
        raise ConfigError(f"configuration file not found: {path}")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read configuration {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError("configuration root must be an object")
    _merge_known(raw, loaded)
    return raw, path.as_posix()


def _resolve_repo_path(value: str, repo_root: Path, field: str) -> Path:
    _validate_relative(value, field)
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _parser() -> argparse.ArgumentParser:
    module_description = __doc__ or "Portable per-file metrics for Python codebases."
    parser = argparse.ArgumentParser(description=module_description.splitlines()[0])
    parser.add_argument("target", nargs="?", default=UNSET, help="Python file or directory, relative to repository root")
    parser.add_argument("--path", dest="legacy_path", default=UNSET, help="Compatibility alias for positional target")
    parser.add_argument("--config", default=None, help="JSON config path, relative to repository root")
    parser.add_argument("--no-config", action="store_true", help="Ignore the adjacent JSON config")
    parser.add_argument("--show-config", action="store_true", help="Print merged effective config and exit")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATTERN", help="Add a repository-relative exclusion")
    parser.add_argument("--clear-excludes", action="store_true", help="Clear config exclude_paths before CLI exclusions")
    exclusions = parser.add_mutually_exclusive_group()
    exclusions.add_argument("--default-excludes", dest="default_excludes", action="store_const", const=True, default=UNSET)
    exclusions.add_argument("--no-default-excludes", dest="default_excludes", action="store_const", const=False)
    for option, dest, description in (
        ("line", "lines", "physical line"),
        ("code-line", "code_lines", "code line"),
        ("class", "classes", "class count"),
        ("function-line", "definition_lines", "function/method span"),
    ):
        group = parser.add_mutually_exclusive_group()
        group.add_argument(f"--{option}-limit", dest=dest, type=int, default=UNSET, metavar="N", help=f"Set {description} limit")
        group.add_argument(f"--no-{option}-limit", dest=dest, action="store_const", const=None, help=f"Disable {description} findings")
    parser.add_argument("--sort", choices=SORT_KEYS, default=UNSET)
    color = parser.add_mutually_exclusive_group()
    color.add_argument("--color", dest="color", action="store_const", const="always", default=UNSET)
    color.add_argument("--no-color", dest="color", action="store_const", const="never")
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument("--problems-only", dest="problems_only", action="store_const", const=True, default=UNSET)
    visibility.add_argument("--all-files", dest="problems_only", action="store_const", const=False)
    failure = parser.add_mutually_exclusive_group()
    failure.add_argument("--fail-on-problems", dest="fail_on_problems", action="store_const", const=True, default=UNSET)
    failure.add_argument("--no-fail-on-problems", dest="fail_on_problems", action="store_const", const=False)
    report = parser.add_mutually_exclusive_group()
    report.add_argument("--report", dest="report", nargs="?", const=True, default=UNSET, metavar="PATH")
    report.add_argument("--no-report", dest="report", action="store_const", const=False)
    accepted = parser.add_mutually_exclusive_group()
    accepted.add_argument("--include-accepted-findings", dest="include_accepted", action="store_const", const=True, default=UNSET)
    accepted.add_argument("--exclude-accepted-findings", dest="include_accepted", action="store_const", const=False)
    return parser


def _apply_cli(raw: dict[str, Any], args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.target is not UNSET and args.legacy_path is not UNSET:
        parser.error("TARGET and --path cannot be used together")
    selected_target = args.target if args.target is not UNSET else args.legacy_path
    if selected_target is not UNSET:
        raw["scan"]["target"] = selected_target
    if args.default_excludes is not UNSET:
        raw["scan"]["use_default_exclusions"] = args.default_excludes
    configured_excludes = [] if args.clear_excludes else list(raw["scan"]["exclude_paths"])
    raw["scan"]["exclude_paths"] = configured_excludes + args.exclude
    for dest in ("lines", "code_lines", "classes", "definition_lines"):
        value = getattr(args, dest)
        if value is not UNSET:
            raw["thresholds"][dest] = value
    for dest in ("sort", "color", "problems_only", "fail_on_problems"):
        value = getattr(args, dest)
        if value is not UNSET:
            raw["terminal"][dest] = value
    if args.report is not UNSET:
        raw["report"]["enabled"] = args.report is not False
        if isinstance(args.report, str):
            raw["report"]["path"] = args.report
    if args.include_accepted is not UNSET:
        raw["report"]["include_accepted_findings"] = args.include_accepted


def load_effective_config(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    repo_root: Path,
    default_config_path: Path,
) -> EffectiveConfig:
    if args.config and args.no_config:
        parser.error("--config and --no-config cannot be used together")
    if args.no_config:
        path, explicit = None, False
    elif args.config:
        path = _resolve_repo_path(args.config, repo_root, "--config")
        explicit = True
    else:
        path, explicit = default_config_path, False
    raw, source = _load_raw_config(path, explicit=explicit)
    _apply_cli(raw, args, parser)
    return _build_config(raw, source)


def effective_config_dict(config: EffectiveConfig) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "config_source": config.source,
        "scan": asdict(config.scan),
        "thresholds": asdict(config.thresholds),
        "terminal": asdict(config.terminal),
        "report": asdict(config.report),
    }


def _relative_display(path: Path, display_root: Path) -> str:
    try:
        relative = path.relative_to(display_root)
        return relative.as_posix() or "."
    except ValueError:
        return path.as_posix()


def _matches_custom(relative: str, patterns: tuple[str, ...], *, directory: bool) -> bool:
    relative = relative.strip("/")
    parts = relative.split("/") if relative else []
    for original in patterns:
        pattern = original.replace("\\", "/").strip("/")
        if fnmatch.fnmatchcase(relative, pattern):
            return True
        if "/" not in pattern and any(fnmatch.fnmatchcase(part, pattern) for part in parts):
            return True
        if directory and fnmatch.fnmatchcase(f"{relative}/_", pattern):
            return True
    return False


def _excluded(path: Path, *, is_dir: bool, repo_root: Path, config: ScanConfig) -> bool:
    try:
        relative_path = path.resolve().relative_to(repo_root.resolve())
        relative = relative_path.as_posix()
        directory_parts = relative_path.parts if is_dir else relative_path.parent.parts
    except ValueError:
        relative = path.name
        directory_parts = (path.name,) if is_dir else ()
    if config.use_default_exclusions:
        if any(name in config.excluded_directory_names for name in directory_parts):
            return True
        if any(
            fnmatch.fnmatchcase(part, pattern)
            for part in directory_parts
            for pattern in config.excluded_directory_patterns
        ):
            return True
    return _matches_custom(relative, config.exclude_paths, directory=is_dir)


def discover_python_files(target: Path, repo_root: Path, config: ScanConfig) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix == ".py" and not _excluded(target, is_dir=False, repo_root=repo_root, config=config) else []
    if _excluded(target, is_dir=True, repo_root=repo_root, config=config):
        return []
    files: list[Path] = []
    for root_text, directories, filenames in os.walk(target, followlinks=False):
        root = Path(root_text)
        directories[:] = sorted(
            name for name in directories
            if not (root / name).is_symlink()
            and not _excluded(root / name, is_dir=True, repo_root=repo_root, config=config)
        )
        for name in sorted(filenames):
            path = root / name
            if path.suffix == ".py" and not path.is_symlink() and not _excluded(path, is_dir=False, repo_root=repo_root, config=config):
                files.append(path)
    return files


def _docstring_lines(tree: ast.Module) -> set[int]:
    result: set[int] = set()
    containers = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, containers) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            end = first.end_lineno or first.lineno
            result.update(range(first.lineno, end + 1))
    return result


def _source_line_counts(text: str, tree: ast.Module) -> tuple[int, int]:
    docstrings = _docstring_lines(tree)
    code: set[int] = set()
    comments = set(docstrings)
    ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT, tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL}
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            comments.add(token.start[0])
        elif token.type not in ignored:
            code.update(line for line in range(token.start[0], token.end[0] + 1) if line not in docstrings)
    comments.difference_update(code)
    return len(code), len(comments)


class _StructureVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: list[str] = []
        self.classes: list[ClassMetric] = []
        self.definitions: list[DefinitionMetric] = []

    def _qualified(self, name: str) -> str:
        return ".".join((*self.names, name))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(ClassMetric(self._qualified(node.name), node.lineno))
        self.names.append(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_definition(child, "method")
            else:
                self.visit(child)
        self.names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition(node, "function")

    def _visit_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        end = node.end_lineno or node.lineno
        self.definitions.append(DefinitionMetric(self._qualified(node.name), kind, node.lineno, end, end - node.lineno + 1))
        self.names.append(node.name)
        self.generic_visit(node)
        self.names.pop()


def analyze_file(path: Path, display_root: Path) -> FileMetrics:
    display = _relative_display(path, display_root)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return FileMetrics(path, display, 0, 0, None, None, None, (), (), frozenset(), "read", str(exc))
    basic_lines = len(raw.splitlines())
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
    except (SyntaxError, UnicodeError) as exc:
        return FileMetrics(path, display, len(raw), basic_lines, None, None, None, (), (), frozenset(), "decode", str(exc))
    accepted = frozenset(match.group(1).lower() for match in ACCEPT_MARKER_RE.finditer(text))
    try:
        tree = ast.parse(text, filename=str(path))
        code_lines, comment_lines = _source_line_counts(text, tree)
        visitor = _StructureVisitor()
        visitor.visit(tree)
    except (SyntaxError, IndentationError, tokenize.TokenError) as exc:
        return FileMetrics(path, display, len(raw), len(text.splitlines()), None, None, len(text), (), (), accepted, "parse", str(exc))
    return FileMetrics(
        path, display, len(raw), len(text.splitlines()), code_lines, comment_lines,
        len(text), tuple(visitor.classes), tuple(visitor.definitions), accepted,
    )


def _over(value: int | None, threshold: int | None) -> int:
    return 0 if value is None or threshold is None else max(0, value - threshold)


def evaluate_file(metrics: FileMetrics, thresholds: Thresholds) -> FileReport:
    findings: list[Finding] = []
    if metrics.error:
        findings.append(Finding("error", None, None, 0, False, f"{metrics.error_category}: {metrics.error}"))
        return FileReport(metrics, tuple(findings))
    values = (("lines", metrics.line_count, thresholds.lines), ("code_lines", metrics.code_line_count, thresholds.code_lines))
    for category, measured, threshold in values:
        overage = _over(measured, threshold)
        if overage:
            findings.append(Finding(category, measured, threshold, overage, "lines" in metrics.accepted_checks))
    class_overage = _over(metrics.class_count, thresholds.classes)
    if class_overage:
        detail = ", ".join(f"{item.qualified_name} (line {item.line})" for item in metrics.classes)
        findings.append(Finding("classes", metrics.class_count, thresholds.classes, class_overage, "classes" in metrics.accepted_checks, detail))
    if thresholds.definition_lines is not None:
        for definition in metrics.definitions:
            overage = _over(definition.span, thresholds.definition_lines)
            if overage:
                detail = f"{definition.kind} {definition.qualified_name}, lines {definition.start_line}-{definition.end_line}"
                findings.append(Finding("monoliths", definition.span, thresholds.definition_lines, overage, "monoliths" in metrics.accepted_checks, detail, definition.start_line))
    return FileReport(metrics, tuple(findings))


def build_report(metrics: Sequence[FileMetrics], thresholds: Thresholds) -> MetricsReport:
    files = tuple(evaluate_file(item, thresholds) for item in metrics)
    unresolved = [finding for file in files for finding in file.unresolved]
    valid = [file.metrics for file in files if not file.metrics.error]
    summary = Summary(
        files_scanned=len(files),
        files_with_problems=sum(bool(file.unresolved) for file in files),
        line_findings=sum(f.category in {"lines", "code_lines"} for f in unresolved),
        class_findings=sum(f.category == "classes" for f in unresolved),
        monolith_findings=sum(f.category == "monoliths" for f in unresolved),
        analysis_errors=sum(f.category == "error" for f in unresolved),
        total_size=sum(file.metrics.size_bytes for file in files),
        total_lines=sum(file.metrics.line_count for file in files),
        total_code=sum(item.code_line_count or 0 for item in valid),
        total_comment=sum(item.comment_line_count or 0 for item in valid),
        total_classes=sum(item.class_count or 0 for item in valid),
        total_functions=sum(item.function_count or 0 for item in valid),
        total_methods=sum(item.method_count or 0 for item in valid),
        total_monoliths=sum(f.category == "monoliths" for file in files for f in file.findings),
        total_chars=sum(item.char_count or 0 for item in valid),
    )
    return MetricsReport(files, summary)


def _sort_value(file: FileReport, key: str) -> int:
    metrics = file.metrics
    monoliths = sum(f.category == "monoliths" for f in file.findings)
    values = {
        "size": metrics.size_bytes, "lines": metrics.line_count, "code": metrics.code_line_count,
        "comment": metrics.comment_line_count, "classes": metrics.class_count,
        "functions": metrics.function_count, "methods": metrics.method_count,
        "monoliths": monoliths, "chars": metrics.char_count,
    }
    return int(values[key] if values[key] is not None else -1)


def ordered_files(files: Sequence[FileReport], sort_key: str) -> list[FileReport]:
    if sort_key == "path":
        return sorted(files, key=lambda file: file.metrics.display_path)
    return sorted(files, key=lambda file: (-_sort_value(file, sort_key), file.metrics.display_path))


def _finding(file: FileReport, categories: set[str]) -> list[Finding]:
    return [finding for finding in file.findings if finding.category in categories]


def _human_size(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024**2:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024**2:.1f} MB"


def _plain_value(value: int | None, findings: Sequence[Finding]) -> str:
    if value is None:
        return "?"
    suffix = "~" if findings and all(f.accepted for f in findings) else "!" if any(not f.accepted for f in findings) else ""
    return f"{value}{suffix}"


def render_plain(files: Sequence[FileReport], report: MetricsReport) -> None:
    headers = ("File", "Lines", "Code", "Comment", "Classes", "Methods", "Functions", "Monoliths", "Size", "Chars")
    width = max([len(headers[0]), *(len(file.metrics.display_path) for file in files)])
    def row(values: Sequence[str]) -> str:
        return f"{values[0]:<{width}}  " + "  ".join(f"{value:>10}" for value in values[1:])
    print(row(headers))
    print("-" * (width + 12 * 9))
    for file in files:
        m = file.metrics
        monoliths = _finding(file, {"monoliths"})
        print(row((
            m.display_path,
            _plain_value(m.line_count, _finding(file, {"lines"})),
            _plain_value(m.code_line_count, _finding(file, {"code_lines"})),
            "?" if m.comment_line_count is None else str(m.comment_line_count),
            _plain_value(m.class_count, _finding(file, {"classes"})),
            "?" if m.method_count is None else str(m.method_count),
            "?" if m.function_count is None else str(m.function_count),
            _plain_value(None if m.error else len(monoliths), monoliths),
            _human_size(m.size_bytes),
            "?" if m.char_count is None else str(m.char_count),
        )))
    s = report.summary
    print("-" * (width + 12 * 9))
    print(row((f"TOTAL ({s.files_scanned} files)", str(s.total_lines), str(s.total_code), str(s.total_comment), str(s.total_classes), str(s.total_methods), str(s.total_functions), str(s.total_monoliths), _human_size(s.total_size), str(s.total_chars))))
    print("\n! = over threshold and unresolved; ~ = over threshold and accepted")


def render_rich(files: Sequence[FileReport], report: MetricsReport, *, force_color: bool) -> None:
    from rich.console import Console  # type: ignore[import-not-found]
    from rich.table import Table  # type: ignore[import-not-found]
    from rich.text import Text  # type: ignore[import-not-found]

    console = Console(width=shutil.get_terminal_size(fallback=(120, 25)).columns, force_terminal=force_color)
    table = Table(header_style="bold")
    for name in ("File", "Lines", "Code", "Comment", "Classes", "Methods", "Functions", "Monoliths", "Size", "Chars"):
        table.add_column(name, justify="left" if name == "File" else "right", no_wrap=name == "File", overflow="ellipsis")
    def cell(value: int | None, findings: Sequence[Finding]) -> Text:
        if value is None:
            return Text("?", style="dim")
        style = "green" if findings and all(f.accepted for f in findings) else "red bold" if any(not f.accepted for f in findings) else None
        result = Text(str(value))
        if style is not None:
            result.stylize(style)
        return result
    for file in files:
        m = file.metrics
        monoliths = _finding(file, {"monoliths"})
        table.add_row(
            m.display_path, cell(m.line_count, _finding(file, {"lines"})), cell(m.code_line_count, _finding(file, {"code_lines"})),
            cell(m.comment_line_count, ()), cell(m.class_count, _finding(file, {"classes"})), cell(m.method_count, ()), cell(m.function_count, ()),
            cell(None if m.error else len(monoliths), monoliths), _human_size(m.size_bytes), cell(m.char_count, ()),
        )
    s = report.summary
    table.add_section()
    table.add_row(f"TOTAL ({s.files_scanned} files)", str(s.total_lines), str(s.total_code), str(s.total_comment), str(s.total_classes), str(s.total_methods), str(s.total_functions), str(s.total_monoliths), _human_size(s.total_size), str(s.total_chars), style="bold")
    console.print(table)
    console.print("[red bold]red[/] = unresolved; [green]green[/] = accepted")


def print_terminal(report: MetricsReport, config: EffectiveConfig) -> None:
    files = [file for file in report.files if not config.terminal.problems_only or file.unresolved]
    target = config.scan.target
    if not files and config.terminal.problems_only:
        print(f"Scanned {report.summary.files_scanned} .py file(s) under {target} -- none flagged. Nothing to show for --problems-only.")
        return
    print(f"Scanning {target} ({report.summary.files_scanned} .py files, {len(files)} displayed)...\n")
    ordered = ordered_files(files, config.terminal.sort)
    use_rich = RICH_AVAILABLE and config.terminal.color != "never"
    if use_rich:
        render_rich(ordered, report, force_color=config.terminal.color == "always")
    else:
        render_plain(ordered, report)
    s = report.summary
    print(f"{s.files_with_problems} file(s) with unresolved findings: {s.line_findings} line, {s.class_findings} class, {s.monolith_findings} long-definition, {s.analysis_errors} analysis error(s).")
    errors = [file for file in report.files if file.metrics.error]
    for file in errors:
        print(f"  {file.metrics.display_path}: {file.metrics.error_category}: {file.metrics.error}")


def _priority(file: FileReport) -> tuple[int, int, int, int, int, str]:
    unresolved = file.unresolved
    errors = any(f.category == "error" for f in unresolved)
    monoliths = [f for f in unresolved if f.category == "monoliths"]
    line_overage = max((f.overage for f in unresolved if f.category in {"lines", "code_lines"}), default=0)
    class_overage = max((f.overage for f in unresolved if f.category == "classes"), default=0)
    return (-int(errors), -len(monoliths), -max((f.overage for f in monoliths), default=0), -line_overage, -class_overage, file.metrics.display_path)


def _threshold_text(value: int | None) -> str:
    return "disabled" if value is None else str(value)


def markdown_report(report: MetricsReport, config: EffectiveConfig) -> str:
    s = report.summary
    unresolved_files = sorted((file for file in report.files if file.unresolved), key=_priority)
    lines = [
        "# Code Metrics Refactoring Report", "", "## Scope and configuration", "",
        f"- Target: `{config.scan.target}`", f"- Configuration: `{config.source}`",
        f"- Default exclusions enabled: `{str(config.scan.use_default_exclusions).lower()}`",
        f"- Custom exclusions: {', '.join(f'`{item}`' for item in config.scan.exclude_paths) or 'none'}",
        f"- Thresholds: lines {_threshold_text(config.thresholds.lines)}, code lines {_threshold_text(config.thresholds.code_lines)}, classes {_threshold_text(config.thresholds.classes)}, definition lines {_threshold_text(config.thresholds.definition_lines)}",
        f"- Reproduce: `python tools/code_metrics.py {config.scan.target} --report`", "",
        "## Executive summary", "",
        f"- Files scanned: {s.files_scanned}", f"- Files with unresolved findings: {s.files_with_problems}",
        f"- Line findings: {s.line_findings}", f"- Class findings: {s.class_findings}",
        f"- Long-definition findings: {s.monolith_findings}", f"- Analysis errors: {s.analysis_errors}", "",
        "## Refactoring candidates", "",
    ]
    candidates = [file for file in unresolved_files if not file.metrics.error]
    if not candidates:
        lines.append("No unresolved refactoring candidates were found.")
        lines.append("")
    for file in candidates:
        lines.extend((f"### `{file.metrics.display_path}`", ""))
        for finding in file.unresolved:
            if finding.category == "error":
                continue
            label = {"lines": "Physical lines", "code_lines": "Code lines", "classes": "Classes", "monoliths": "Long definition"}[finding.category]
            detail = f"; {finding.detail}" if finding.detail else ""
            lines.append(f"- {label}: {finding.measured} (limit {finding.threshold}, over by {finding.overage}){detail}")
        suggestions: list[str] = []
        categories = {finding.category for finding in file.unresolved}
        if categories & {"lines", "code_lines"}:
            suggestions.append("Examine whether the file contains separable responsibilities before splitting it.")
        if "classes" in categories:
            suggestions.append("Check whether the classes are cohesive and intentionally colocated.")
        if "monoliths" in categories:
            suggestions.append("Look for cohesive phases or helpers that can be extracted without changing behavior.")
        lines.extend(("", "Suggested investigation:", ""))
        lines.extend(f"- {item}" for item in suggestions)
        lines.append("")
    lines.extend(("## Analysis errors", ""))
    error_files = [file for file in unresolved_files if file.metrics.error]
    lines.extend((f"- `{file.metrics.display_path}`: {file.metrics.error_category}: {file.metrics.error}" for file in error_files))
    if not error_files:
        lines.append("None.")
    lines.extend(("", "## Accepted findings", ""))
    accepted = [(file, finding) for file in report.files for finding in file.accepted]
    if config.report.include_accepted_findings and accepted:
        for file, finding in sorted(accepted, key=lambda item: (item[0].metrics.display_path, item[1].category, item[1].line or 0)):
            detail = f"; {finding.detail}" if finding.detail else ""
            lines.append(f"- `{file.metrics.display_path}`: {finding.category} {finding.measured} (limit {finding.threshold}){detail}")
    else:
        lines.append("None included.")
    lines.extend((
        "", "## Agent handoff constraints", "",
        "- Inspect existing behavior and tests before modifying a candidate.",
        "- Preserve public APIs and observable behavior unless separately authorized.",
        "- Treat these metrics as signals, not automatic proof of poor design.",
        "- Apply separation of concerns and DRY without introducing needless abstractions.",
        "- Run relevant tests and static checks after each coherent refactor.", "",
    ))
    return "\n".join(lines)


def write_markdown_report(path: Path, content: str) -> None:
    if path.exists() and path.is_dir():
        raise OSError(f"report destination is a directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path = REPO_ROOT,
    default_config_path: Path = DEFAULT_CONFIG_PATH,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        config = load_effective_config(args, parser, repo_root, default_config_path)
        if args.show_config:
            print(json.dumps(effective_config_dict(config), indent=2, sort_keys=True))
            return 0
        target = _resolve_repo_path(config.scan.target, repo_root, "scan.target")
        if not target.exists():
            raise ConfigError(f"target does not exist: {target}")
        if not target.is_dir() and not (target.is_file() and target.suffix == ".py"):
            raise ConfigError(f"target must be a directory or .py file: {target}")
        display_root = repo_root if target.is_relative_to(repo_root) else (target if target.is_dir() else target.parent)
        paths = discover_python_files(target, repo_root, config.scan)
        metrics = [analyze_file(path, display_root) for path in paths]
        report = build_report(metrics, config.thresholds)
        print_terminal(report, config)
        if config.report.enabled:
            destination = _resolve_repo_path(config.report.path, repo_root, "report.path")
            write_markdown_report(destination, markdown_report(report, config))
            print(f"Markdown report written to {_relative_display(destination, repo_root)}")
        return 1 if config.terminal.fail_on_problems and report.summary.files_with_problems else 0
    except (ConfigError, OSError) as exc:
        print(f"code_metrics: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
