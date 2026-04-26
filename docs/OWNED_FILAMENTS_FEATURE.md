# Owned Filaments Feature - Design Document

## Overview

Allow users to maintain a list of filaments they actually own, and match image colors against only those filaments instead of using broad maker/type/finish filters.

**Benefits:**

- More accurate color matching (only filaments you have)
- Reduces waste (no suggestions for filaments you don't own)
- Better planning (know immediately if you can print with current inventory)
- Flexibility (combine owned list with filters to narrow further)

---

## Architecture

### Core Implementation: **color-tools library**

The filament database and filtering logic already live here. Other tools could benefit from this feature.

### CLI Integration: **pixel_to_3mf**

User-facing commands and workflow integration.

---

## Design Decisions

### 1. Filament Identifier Format

Use existing kebab-case IDs from the color-tools filament database:

```text
bambu-lab-pla-basic-red
bambu-lab-pla-basic-blue
bambu-lab-pla-matte-black
polymaker-petg-matte-galaxy-black
```

**Rationale:** These IDs already exist, are unique, and are human-readable.

### 2. Storage Location

**File:** `~/.color-tools/owned-filaments.json`

**Format:** JSON array of filament IDs

```json
{
  "owned": [
    "bambu-lab-pla-basic-red",
    "bambu-lab-pla-basic-blue",
    "bambu-lab-pla-matte-black",
    "polymaker-petg-matte-galaxy-black"
  ]
}
```

**Rationale:**

- Structured and extensible (can add metadata later: quantities, notes, purchase dates)
- Still human-readable and editable
- Cross-platform (uses home directory)
- Easy to parse and validate
- Version control friendly (if user wants to track it)
- Future-proof for features like quantity tracking

### 3. File Management

**Location logic:**

1. Check `COLORTOOLS_CONFIG` environment variable (if user wants custom location)
2. Fall back to `~/.color-tools/owned-filaments.json`
3. Create directory and file if they don't exist (initialize with empty owned array)

**Atomicity:** Use temp file + rename pattern for safe writes

**Validation:** Validate JSON structure on load, gracefully handle corrupted files

---

## Implementation Plan

## Phase 1: color-tools Library

### New Module: `color_tools/owned.py`

```python
"""
Owned filaments management.

Maintains a list of filament IDs that the user owns, stored in
~/.color-tools/owned-filaments.json
"""

from pathlib import Path
from typing import Set, List
import os
import json

def get_owned_file_path() -> Path:
    """
    Get the path to the owned filaments file.
    
    Checks COLORTOOLS_CONFIG env var, falls back to ~/.color-tools/
    """
    if env_path := os.getenv('COLORTOOLS_CONFIG'):
        return Path(env_path) / 'owned-filaments.json'
    
    config_dir = Path.home() / '.color-tools'
    config_dir.mkdir(exist_ok=True)
    return config_dir / 'owned-filaments.json'


def load_owned_filaments() -> Set[str]:
    """
    Load the set of owned filament IDs from disk.
    
    Returns:
        Set of filament IDs (e.g., {'bambu-lab-pla-basic-red', ...})
    """
    owned_file = get_owned_file_path()
    
    if not owned_file.exists():
        return set()
    
    try:
        data = json.loads(owned_file.read_text(encoding='utf-8'))
        return set(data.get('owned', []))
    except (json.JSONDecodeError, ValueError) as e:
        # Corrupted file - return empty set and log warning
        import warnings
        warnings.warn(f"Corrupted owned filaments file: {e}. Starting fresh.")
        return set()


def save_owned_filaments(owned: Set[str]) -> None:
    """
    Save the set of owned filament IDs to disk.
    
    Uses atomic write (temp file + rename) for safety.
    """
    owned_file = get_owned_file_path()
    temp_file = owned_file.with_suffix('.tmp')
    
    # Create JSON structure
    data = {
        'owned': sorted(owned)  # Sort for consistent ordering
    }
    
    # Write to temp file
    temp_file.write_text(
        json.dumps(data, indent=2) + '\n',
        encoding='utf-8'
    )
    
    # Atomic rename
    temp_file.replace(owned_file)


def add_owned_filament(filament_id: str) -> bool:
    """
    Add a filament ID to the owned list.
    
    Args:
        filament_id: Filament ID (e.g., 'bambu-lab-pla-basic-red')
        
    Returns:
        True if added, False if already in list
    """
    owned = load_owned_filaments()
    
    if filament_id in owned:
        return False
    
    owned.add(filament_id)
    save_owned_filaments(owned)
    return True


def remove_owned_filament(filament_id: str) -> bool:
    """
    Remove a filament ID from the owned list.
    
    Args:
        filament_id: Filament ID to remove
        
    Returns:
        True if removed, False if not in list
    """
    owned = load_owned_filaments()
    
    if filament_id not in owned:
        return False
    
    owned.remove(filament_id)
    save_owned_filaments(owned)
    return True


def list_owned_filaments() -> List[str]:
    """
    Get a sorted list of owned filament IDs.
    
    Returns:
        List of filament IDs, sorted alphabetically
    """
    return sorted(load_owned_filaments())


def is_owned(filament_id: str) -> bool:
    """
    Check if a filament ID is in the owned list.
    
    Args:
        filament_id: Filament ID to check
        
    Returns:
        True if owned, False otherwise
    """
    return filament_id in load_owned_filaments()
```

### Update: `color_tools/palette.py`

Add `owned_only` parameter to `FilamentPalette.filter()`:

```python
def filter(
    self,
    maker: str | List[str] | None = None,
    type_name: str | List[str] | None = None,
    finish: str | List[str] | None = None,
    owned_only: bool = False,  # NEW
) -> 'FilamentPalette':
    """
    Filter filaments by maker, type, finish, and/or owned status.
    
    Args:
        maker: Maker name(s) to include
        type_name: Type name(s) to include  
        finish: Finish name(s) to include
        owned_only: If True, only include filaments in owned list
        
    Returns:
        New FilamentPalette with filtered filaments
    """
    from .owned import load_owned_filaments
    
    filtered = self.filaments
    
    # Apply owned filter first (if requested)
    if owned_only:
        owned_ids = load_owned_filaments()
        filtered = [f for f in filtered if f.id in owned_ids]
    
    # Then apply other filters
    if maker:
        makers = [maker] if isinstance(maker, str) else maker
        filtered = [f for f in filtered if f.maker in makers]
    
    if type_name:
        types = [type_name] if isinstance(type_name, str) else type_name
        filtered = [f for f in filtered if f.type in types]
    
    if finish:
        finishes = [finish] if isinstance(finish, str) else finish
        filtered = [f for f in filtered if f.finish in finishes]
    
    return FilamentPalette(filtered)
```

### Update: `color_tools/__init__.py`

Export owned management functions:

```python
from .owned import (
    add_owned_filament,
    remove_owned_filament,
    list_owned_filaments,
    is_owned,
    load_owned_filaments,
)
```

---

## Phase 2: pixel_to_3mf Integration

### 1. CLI Flag: `--owned-filaments`

Add to `cli.py`:

```python
parser.add_argument(
    "--owned-filaments",
    action="store_true",
    help="Match colors only against filaments marked as owned. "
         "Can be combined with --filament-maker, --filament-type, --filament-finish "
         "to further filter the owned set. Use 'python -m pixel_to_3mf.manage_filaments' "
         "to manage your owned filaments list."
)
```

### 2. Config Update: `config.py`

Add field to `ConversionConfig`:

```python
@dataclass
class ConversionConfig:
    # ... existing fields ...
    
    owned_filaments_only: bool = False
    """If True, match against owned filaments only (ignores maker/type/finish filters unless combined)"""
```

### 3. Usage in `threemf_writer.py`

Update the filament filtering logic:

```python
# In assign_filaments_greedy_no_merge() or wherever filtering happens
filtered = palette.filter(
    maker=maker_list,
    type_name=type_list,
    finish=finish_list,
    owned_only=config.owned_filaments_only  # NEW
)
```

### 4. Management Tool: `pixel_to_3mf/manage_filaments.py`

New module for managing owned filaments:

```python
#!/usr/bin/env python3
"""
Filament inventory management tool.

Manage your owned filaments list used by --owned-filaments flag.
"""

import sys
import argparse
from typing import List

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from color_tools import (
    FilamentPalette,
    add_owned_filament,
    remove_owned_filament,
    list_owned_filaments,
)


console = Console()


def cmd_add(args):
    """Add a filament to owned list."""
    if add_owned_filament(args.filament_id):
        console.print(f"[green]✅ Added: {args.filament_id}[/green]")
    else:
        console.print(f"[yellow]⚠️  Already owned: {args.filament_id}[/yellow]")


def cmd_remove(args):
    """Remove a filament from owned list."""
    if remove_owned_filament(args.filament_id):
        console.print(f"[green]✅ Removed: {args.filament_id}[/green]")
    else:
        console.print(f"[yellow]⚠️  Not in owned list: {args.filament_id}[/yellow]")


def cmd_list(args):
    """List all owned filaments."""
    owned = list_owned_filaments()
    
    if not owned:
        console.print("[yellow]No owned filaments yet.[/yellow]")
        console.print("\nAdd filaments with:")
        console.print("  python -m pixel_to_3mf.manage_filaments add <filament-id>")
        return
    
    # Load full palette to get filament details
    palette = FilamentPalette.from_database()
    
    table = Table(title=f"Owned Filaments ({len(owned)})", box=box.ROUNDED)
    table.add_column("ID", style="cyan")
    table.add_column("Maker", style="yellow")
    table.add_column("Type", style="magenta")
    table.add_column("Finish", style="blue")
    table.add_column("Color", style="white")
    table.add_column("RGB", style="dim")
    
    for filament_id in owned:
        # Find filament details
        filament = next((f for f in palette.filaments if f.id == filament_id), None)
        
        if filament:
            rgb_str = f"#{filament.rgb[0]:02X}{filament.rgb[1]:02X}{filament.rgb[2]:02X}"
            table.add_row(
                filament.id,
                filament.maker,
                filament.type,
                filament.finish,
                filament.color,
                rgb_str
            )
        else:
            # Filament ID not found in database (maybe removed?)
            table.add_row(filament_id, "[red]NOT FOUND[/red]", "", "", "", "")
    
    console.print(table)


def cmd_interactive(args):
    """Interactive mode to browse and add filaments."""
    palette = FilamentPalette.from_database()
    owned = set(list_owned_filaments())
    
    console.print("[bold cyan]Interactive Filament Browser[/bold cyan]")
    console.print()
    
    # Filter options
    maker = Prompt.ask("Filter by maker (leave empty for all)", default="")
    type_name = Prompt.ask("Filter by type (leave empty for all)", default="")
    finish = Prompt.ask("Filter by finish (leave empty for all)", default="")
    
    # Apply filters
    filtered = palette
    if maker:
        filtered = filtered.filter(maker=maker)
    if type_name:
        filtered = filtered.filter(type_name=type_name)
    if finish:
        filtered = filtered.filter(finish=finish)
    
    if not filtered.filaments:
        console.print("[red]No filaments match your filters.[/red]")
        return
    
    console.print(f"\n[cyan]Found {len(filtered.filaments)} filaments[/cyan]")
    console.print()
    
    # Display and prompt to add
    for filament in filtered.filaments:
        owned_status = "✅ OWNED" if filament.id in owned else ""
        console.print(f"[bold]{filament.maker} {filament.type} {filament.finish} {filament.color}[/bold] {owned_status}")
        console.print(f"  ID: [cyan]{filament.id}[/cyan]")
        console.print(f"  RGB: #{filament.rgb[0]:02X}{filament.rgb[1]:02X}{filament.rgb[2]:02X}")
        
        if filament.id not in owned:
            if Confirm.ask("  Add to owned list?", default=False):
                add_owned_filament(filament.id)
                owned.add(filament.id)
                console.print("  [green]✅ Added![/green]")
        
        console.print()


def cmd_clear(args):
    """Clear all owned filaments."""
    if not Confirm.ask("[red]Are you sure you want to clear ALL owned filaments?[/red]", default=False):
        console.print("Cancelled.")
        return
    
    owned = list_owned_filaments()
    for filament_id in owned:
        remove_owned_filament(filament_id)
    
    console.print(f"[green]✅ Cleared {len(owned)} filaments[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Manage your owned filaments inventory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add a filament
  %(prog)s add bambu-lab-pla-basic-red
  
  # Remove a filament
  %(prog)s remove bambu-lab-pla-basic-red
  
  # List all owned filaments
  %(prog)s list
  
  # Interactive browser to add filaments
  %(prog)s interactive
  
  # Clear all owned filaments
  %(prog)s clear
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a filament to owned list')
    add_parser.add_argument('filament_id', help='Filament ID (e.g., bambu-lab-pla-basic-red)')
    add_parser.set_defaults(func=cmd_add)
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a filament from owned list')
    remove_parser.add_argument('filament_id', help='Filament ID to remove')
    remove_parser.set_defaults(func=cmd_remove)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all owned filaments')
    list_parser.set_defaults(func=cmd_list)
    
    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive browser to add filaments')
    interactive_parser.set_defaults(func=cmd_interactive)
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all owned filaments')
    clear_parser.set_defaults(func=cmd_clear)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()
```

### 5. Make it Runnable: `pixel_to_3mf/__main__.py`

Create or update to allow `python -m pixel_to_3mf.manage_filaments`:

```python
"""
Allow running manage_filaments as a module.
"""

import sys

if __name__ == '__main__':
    # Check if we're running manage_filaments submodule
    if len(sys.argv) > 1 and sys.argv[1] == 'manage_filaments':
        # Remove 'manage_filaments' from args
        sys.argv.pop(1)
        from .manage_filaments import main
        main()
    else:
        # Default to CLI
        from .cli import main
        main()
```

Actually, simpler approach - just document it as:

```bash
python pixel_to_3mf/manage_filaments.py
```

---

## User Workflows

### Initial Setup

```bash
# Interactive mode - browse and add filaments
python -m pixel_to_3mf.manage_filaments interactive

# Or add specific filaments you know you have
python -m pixel_to_3mf.manage_filaments add bambu-lab-pla-basic-red
python -m pixel_to_3mf.manage_filaments add bambu-lab-pla-basic-blue
python -m pixel_to_3mf.manage_filaments add bambu-lab-pla-matte-black
```

### Using Owned Filaments

```bash
# Match against owned filaments only
python run_converter.py image.png --owned-filaments

# Combine with filters to narrow owned set
python run_converter.py image.png --owned-filaments --filament-type PLA

# Still works - fallback to broad filters if owned list is empty
python run_converter.py image.png --filament-maker "Bambu Lab"
```

### Managing Inventory

```bash
# List what you have
python -m pixel_to_3mf.manage_filaments list

# Add new filament
python -m pixel_to_3mf.manage_filaments add polymaker-petg-silk-gold

# Remove used-up filament
python -m pixel_to_3mf.manage_filaments remove bambu-lab-pla-basic-red

# Clear everything (start fresh)
python -m pixel_to_3mf.manage_filaments clear
```

---

## Testing Plan

### color-tools Tests

1. Test owned filaments CRUD operations
2. Test file creation/deletion
3. Test atomic writes (concurrent access)
4. Test invalid filament IDs
5. Test owned_only filter with various combinations

### pixel_to_3mf Tests

1. Test `--owned-filaments` flag
2. Test combination with other filters
3. Test behavior when owned list is empty
4. Test management commands
5. Integration test: add owned filaments, run conversion, verify matching

---

## Documentation Updates

### README.md

Add section:

```markdown
### Using Owned Filaments

Instead of broad filters like `--filament-maker "Bambu Lab"`, you can maintain a list of filaments you actually own and match against only those:

\`\`\`bash
# First, add your filaments to the owned list
python -m pixel_to_3mf.manage_filaments add bambu-lab-pla-basic-red
python -m pixel_to_3mf.manage_filaments add bambu-lab-pla-basic-blue
python -m pixel_to_3mf.manage_filaments list

# Then convert using owned filaments
python run_converter.py image.png --owned-filaments
\`\`\`

See [Managing Your Filament Inventory](#managing-filament-inventory) for details.
```

### New Section: Managing Filament Inventory

Full walkthrough of the management tool.

---

## Future Enhancements

1. **Export/Import:** Share owned lists between machines
2. **Quantities:** Track how much of each filament you have
3. **Colors:** Group filaments by color family for quick browsing
4. **Auto-detect:** Scan 3MF files to suggest adding filaments used
5. **Shopping List:** Generate list of filaments needed for a conversion
6. **Bambu Lab Integration:** Import from Bambu Studio/Handy AMS configuration

---

## Implementation Timeline

### Phase 1: color-tools (Week 1)

- [ ] Create `owned.py` module
- [ ] Add `owned_only` parameter to `FilamentPalette.filter()`
- [ ] Write tests
- [ ] Update color-tools documentation
- [ ] Publish new version

### Phase 2: pixel_to_3mf (Week 2)

- [ ] Add `--owned-filaments` CLI flag
- [ ] Update `ConversionConfig`
- [ ] Create `manage_filaments.py` tool
- [ ] Write tests
- [ ] Update README
- [ ] Update CHANGELOG

### Phase 3: Polish (Week 3)

- [ ] User testing and feedback
- [ ] Bug fixes
- [ ] Documentation improvements
- [ ] Video walkthrough/demo

---

## Design Decisions - CONFIRMED ✅

1. **Filter combination logic:** If `--owned-filaments` and `--filament-maker` (or other filters) are both specified:
   - ✅ **AND logic (intersect)**: Filter WITHIN the owned list
   - Example: `--owned-filaments --filament-maker "Bambu Lab"` → Only Bambu Lab filaments from your owned list
   - This allows users to further narrow their owned inventory

2. **Empty owned list behavior:** If `--owned-filaments` is used but owned list is empty:
   - ✅ **Error with helpful message**: "No owned filaments configured. Use 'python -m pixel_to_3mf.manage_filaments add' to add filaments."
   - Clear and explicit - user must set up their inventory before using the feature
   - Prevents confusion from unexpected fallback behavior

3. **File format:**
   - ✅ **JSON from the start**: Use `owned-filaments.json` with structured format
   - Allows future extensibility (quantities, notes, purchase dates, etc.)
   - Still human-readable and editable

4. **Interactive mode dependencies:**
   - ✅ **Require Rich**: Already a dependency of pixel_to_3mf, provides excellent UX
   - No need for separate CLI/TUI versions

---

## Summary

This feature provides a powerful way to match colors against an actual filament inventory. By implementing the core in color-tools and the UI in pixel_to_3mf, we keep concerns separated and make the feature reusable for other tools.

The design is simple (JSON file of IDs), extensible (can add metadata like quantities), and user-friendly (interactive browser + command-line management).

**Key behaviors:**

- `--owned-filaments` matches against your inventory
- Combine with filters to narrow within owned set: `--owned-filaments --filament-type PLA`
- Errors if owned list is empty (forces explicit setup)
- JSON format allows future enhancements without breaking changes
