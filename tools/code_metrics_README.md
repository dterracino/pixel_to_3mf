# Code Metrics Tool

`code_metrics.py` scans Python source files, prints a per-file metrics table,
and can create a Markdown report that identifies likely refactoring candidates.
It is intended to be copied into a repository's `tools` directory along with
its sidecar configuration file, `code_metrics.json`.

The metrics are signals for investigation, not automatic proof that a file is
poorly designed. Use the report to guide review, then preserve behavior and
public APIs when refactoring.

## Files

- `code_metrics.py` - the executable scanner and report generator.
- `code_metrics.json` - repository-specific defaults.
- `code_metrics_README.md` - this guide.

The script treats the parent of `tools` as the repository root. Relative scan,
configuration, exclusion, and report paths are resolved from that root, not
from the shell's current directory.

## Requirements

- Python 3.10 or newer.
- No required third-party packages.
- [`rich`](https://pypi.org/project/rich/) is optional and provides the
  formatted, colored terminal table. Without it, the script prints a plain-text
  table.

Run commands from the repository root for clarity:

```powershell
python tools/code_metrics.py --help
```

If the repository has a virtual environment, use its Python executable instead:

```powershell
.\.venv\Scripts\python.exe tools\code_metrics.py
```

## Quick start

Scan the entire repository using `tools/code_metrics.json`:

```powershell
python tools/code_metrics.py
```

Scan one package or directory:

```powershell
python tools/code_metrics.py color_tools
```

Scan one Python file:

```powershell
python tools/code_metrics.py color_tools\api.py
```

Show only files with unresolved findings:

```powershell
python tools/code_metrics.py --problems-only
```

Generate the terminal table and the configured Markdown report:

```powershell
python tools/code_metrics.py --report
```

Generate a report at a specific repository-relative path:

```powershell
python tools/code_metrics.py color_tools --report reports\code_metrics.md
```

Force a nonzero exit status when unresolved findings exist, which is useful in
CI or automation:

```powershell
python tools/code_metrics.py --fail-on-problems
```

## Scan targets and paths

The optional positional `TARGET` is one Python file or one directory. When it
is omitted, `scan.target` from the effective configuration is used. The shipped
configuration uses `.` to scan the repository root.

Only one target can be scanned per invocation. To scan sibling directories
such as `color_tools` and `tests` together, scan their common parent:

```powershell
python tools/code_metrics.py .
```

This also considers other Python files below that parent, subject to the
configured exclusions. Multiple independent targets such as
`code_metrics.py color_tools tests` are not supported.

`--path TARGET` is retained as a compatibility alias for the positional form:

```powershell
python tools/code_metrics.py --path color_tools
```

Do not supply both a positional target and `--path`; that is a usage error.
Relative paths cannot use `..` to escape the repository root. Absolute target,
configuration, and report paths are accepted when deliberately needed.

## What the table measures

| Column | Meaning |
| --- | --- |
| `File` | File path relative to the display root. |
| `Lines` | Physical source lines, including blank and comment-only lines. |
| `Code` | Lines containing Python tokens, excluding docstring-only lines. |
| `Comment` | Comment and docstring lines that do not also contain code. |
| `Classes` | Class definitions, including nested classes. |
| `Methods` | Function and async-function definitions directly encountered as class members. |
| `Functions` | Function and async-function definitions outside direct class-member handling, including nested functions. |
| `Monoliths` | Functions or methods whose source span exceeds `definition_lines`. |
| `Size` | File size in bytes, displayed in human-readable units. |
| `Chars` | Number of decoded source characters. |

A threshold is exceeded only when the measured value is greater than the
limit. A file with exactly 500 lines does not exceed a limit of 500.

In the Rich table, unresolved values are red and accepted values are green. In
the plain table, `!` means unresolved and `~` means accepted. A `?` means the
metric could not be calculated because the file could not be read, decoded, or
parsed. The error is printed after the table and included in a generated
report.

Zero values are normal. For example, a module containing only functions has
zero classes and methods, while a data or package-initialization module can
have zero function definitions.

## Findings and thresholds

The tool can create four kinds of refactoring findings:

| Configuration field | CLI override | Finding condition |
| --- | --- | --- |
| `thresholds.lines` | `--line-limit N` | Physical lines exceed `N`. |
| `thresholds.code_lines` | `--code-line-limit N` | Code lines exceed `N`. |
| `thresholds.classes` | `--class-limit N` | Class definitions exceed `N`. |
| `thresholds.definition_lines` | `--function-line-limit N` | An individual function or method spans more than `N` lines. |

The line, code-line, and function-line limits must be positive integers. The
class limit may be zero. Set a threshold to `null` in JSON, or use its
`--no-...-limit` switch, to disable that category.

The definition span runs from the definition's `def` or `async def` line
through its final source line, inclusive. The output calls over-limit
definitions "monoliths" for compactness; it does not assert that every long
definition must be split.

## Configuration

Settings are applied in this order:

1. Built-in defaults in `code_metrics.py`.
2. The adjacent `tools/code_metrics.json`, or the file selected by `--config`.
3. Command-line overrides.

Later sources override earlier ones. Configuration files may contain only the
sections or fields they need to change, but unknown fields are rejected to
catch spelling mistakes.

Use this command to see the fully merged configuration that will actually be
used:

```powershell
python tools/code_metrics.py --show-config
```

Use a different configuration file:

```powershell
python tools/code_metrics.py --config config\strict_metrics.json
```

Ignore the adjacent JSON file and start from built-in defaults:

```powershell
python tools/code_metrics.py --no-config
```

`--config` and `--no-config` cannot be combined.

### Configuration reference

```json
{
  "schema_version": 1,
  "scan": {
    "target": ".",
    "use_default_exclusions": true,
    "excluded_directory_names": [".git", ".venv", "__pycache__"],
    "excluded_directory_patterns": ["*.egg-info"],
    "exclude_paths": []
  },
  "thresholds": {
    "lines": 500,
    "code_lines": 500,
    "classes": 1,
    "definition_lines": 100
  },
  "terminal": {
    "sort": "path",
    "color": "auto",
    "problems_only": false,
    "fail_on_problems": false
  },
  "report": {
    "enabled": false,
    "path": "code_metrics_report.md",
    "include_accepted_findings": true
  }
}
```

| Field | Description |
| --- | --- |
| `schema_version` | Configuration format version; currently must be `1`. |
| `scan.target` | Default Python file or directory to scan. |
| `scan.use_default_exclusions` | Enables directory-name and directory-pattern exclusions. |
| `scan.excluded_directory_names` | Exact directory names skipped anywhere below the target. |
| `scan.excluded_directory_patterns` | Glob patterns applied to directory names, such as `*.egg-info`. |
| `scan.exclude_paths` | Additional repository-relative file or directory glob patterns. |
| `thresholds.*` | Finding thresholds; `null` disables that threshold. |
| `terminal.sort` | Default table ordering. |
| `terminal.color` | `auto`, `always`, or `never`. |
| `terminal.problems_only` | Hides files without unresolved findings. |
| `terminal.fail_on_problems` | Returns exit code 1 when unresolved findings exist. |
| `report.enabled` | Generates a Markdown report on each run. |
| `report.path` | Report destination, relative to the repository root unless absolute. |
| `report.include_accepted_findings` | Includes accepted threshold findings in the report. |

The complete maintained exclusion lists live in `code_metrics.json`; the short
JSON example above is illustrative rather than a replacement for that file.

## Exclusions

Default exclusions prevent repository-root scans from descending into common
metadata, environment, cache, build, editor, and dependency directories. The
shipped configuration includes entries such as `.git`, `.venv`,
`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `build`, `dist`,
`.vscode`, `.vercel`, `node_modules`, and `*.egg-info`.

Add one or more repository-relative exclusions on the command line:

```powershell
python tools/code_metrics.py --exclude "tests/fixtures/**" --exclude "generated/*.py"
```

Patterns use shell-style globs. Forward slashes are the clearest portable form;
backslashes are normalized. A pattern containing `/` is matched against the
repository-relative path. A pattern without `/` can match any individual path
component.

Exclusion controls have deliberately separate responsibilities:

- `--exclude PATTERN` is repeatable and adds patterns for the current run.
- `--clear-excludes` removes `scan.exclude_paths` from the loaded JSON before
  adding any CLI `--exclude` values.
- `--no-default-excludes` disables the directory-name and directory-pattern
  lists, but leaves custom `exclude_paths` active.
- `--default-excludes` re-enables those default lists if the JSON disabled
  them.

For a completely unfiltered scan, clear both exclusion sources:

```powershell
python tools/code_metrics.py --no-default-excludes --clear-excludes
```

Symlinked directories and files are not followed.

## Markdown refactoring reports

`--report` writes a standalone handoff document after printing the terminal
table. The report contains:

- Scope, effective thresholds, and a reproduction command.
- An executive summary.
- Prioritized files with unresolved findings and measured overages.
- Long-definition names and source locations.
- Analysis errors.
- Optionally, findings explicitly accepted in source.
- Guardrails for an agent or developer performing the refactor.

With no path argument, `--report` uses `report.path` from JSON:

```powershell
python tools/code_metrics.py --report
```

With a path argument, it enables reporting and overrides the destination:

```powershell
python tools/code_metrics.py --report reports\current_metrics.md
```

When combining a target and a custom report path, put the target before
`--report` so the report path is not mistaken for the optional report value:

```powershell
python tools/code_metrics.py color_tools --report reports\color_tools_metrics.md
```

The report is replaced atomically, so a failed write does not intentionally
leave a partially written destination. Parent directories are created when
needed.

Use `--no-report` to disable a report enabled in JSON. Use
`--include-accepted-findings` or `--exclude-accepted-findings` to override the
corresponding report setting for one run.

## Accepting intentional findings

Occasionally a file is intentionally over a threshold. A file-wide source
marker can acknowledge that decision without changing the measured value:

```python
# code-metrics: accept lines -- generated lookup data is intentionally colocated.
# code-metrics: accept classes -- small related records share this module.
# code-metrics: accept monoliths -- parser state machine is kept together.
```

The supported categories are:

- `lines` accepts both physical-line and code-line findings.
- `classes` accepts the class-count finding.
- `monoliths` accepts every long-definition finding in that file.

Matching is case-insensitive, and the marker may include explanatory text
after the category. Accepted findings are shown in green or with `~`, are not
counted as unresolved problems, and do not trigger `--fail-on-problems`.

Use these markers only after review. A short reason makes the exception useful
to future maintainers.

## Complete command-line reference

| Option | Effect |
| --- | --- |
| `TARGET` | Scan one Python file or directory. |
| `--path TARGET` | Compatibility alias for positional `TARGET`. |
| `--config PATH` | Load a specific JSON configuration. |
| `--no-config` | Ignore the adjacent JSON configuration. |
| `--show-config` | Print the merged effective configuration and exit. |
| `--exclude PATTERN` | Add an exclusion; repeat for multiple patterns. |
| `--clear-excludes` | Clear JSON `scan.exclude_paths` before CLI exclusions. |
| `--default-excludes` | Enable configured directory exclusions. |
| `--no-default-excludes` | Disable configured directory exclusions. |
| `--line-limit N` | Override the physical-line threshold. |
| `--no-line-limit` | Disable physical-line findings. |
| `--code-line-limit N` | Override the code-line threshold. |
| `--no-code-line-limit` | Disable code-line findings. |
| `--class-limit N` | Override the class-count threshold. |
| `--no-class-limit` | Disable class-count findings. |
| `--function-line-limit N` | Override the function/method span threshold. |
| `--no-function-line-limit` | Disable long-definition findings. |
| `--sort KEY` | Sort by `path`, `size`, `lines`, `code`, `comment`, `classes`, `functions`, `methods`, `monoliths`, or `chars`. |
| `--color` | Force Rich color, including redirected output. |
| `--no-color` | Use the plain-text table. |
| `--problems-only` | Display only files with unresolved findings or errors. |
| `--all-files` | Display all files, overriding the JSON setting. |
| `--fail-on-problems` | Exit 1 if unresolved findings or analysis errors exist. |
| `--no-fail-on-problems` | Keep findings informational and exit 0. |
| `--report [PATH]` | Enable the Markdown report; optionally override its path. |
| `--no-report` | Disable report generation. |
| `--include-accepted-findings` | Include accepted findings in the report. |
| `--exclude-accepted-findings` | Omit accepted findings from the report. |
| `-h`, `--help` | Show argparse's concise command reference. |

Non-`path` sorts are descending, with the file path used to break ties. `path`
sorts alphabetically by displayed path.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Scan completed; either no unresolved findings exist or failure-on-problems is disabled. |
| `1` | Scan completed with unresolved findings while `--fail-on-problems` is active. |
| `2` | Invalid arguments/configuration, an invalid target, or an operational error. |

## Suggested workflows

Interactive repository review:

```powershell
python tools/code_metrics.py --sort lines
```

Create an agent-ready refactoring handoff:

```powershell
python tools/code_metrics.py --problems-only --report
```

Run a stricter one-time review without changing JSON:

```powershell
python tools/code_metrics.py --line-limit 350 --code-line-limit 300 --function-line-limit 75 --problems-only
```

Use in CI while avoiding terminal escape sequences:

```powershell
python tools/code_metrics.py --no-color --problems-only --fail-on-problems
```

Investigate unexpected scope or settings:

```powershell
python tools/code_metrics.py --show-config
```

## Moving the tool to another repository

Copy these files together into that repository's `tools` directory:

```text
tools/
  code_metrics.py
  code_metrics.json
  code_metrics_README.md
```

Then review `code_metrics.json`, especially the target, exclusions, thresholds,
and report destination. Because the script derives the repository root from
its own location, it remains independent of the directory from which it is
invoked.
