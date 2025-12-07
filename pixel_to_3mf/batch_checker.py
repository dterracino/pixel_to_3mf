"""
Batch compatibility checker for multiple 3MF models.

Reads .info.json files for multiple models and analyzes whether they
can be printed together in one batch, considering color/filament constraints.
"""

from pathlib import Path
from typing import List
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

from .model_info import find_info_file_for_model, verify_model_info


def check_batch_compatibility_folder(folder_path: str) -> None:
    """
    Check batch compatibility for all .3MF files in a folder.
    
    Scans the specified folder for all .3mf files (case-insensitive),
    then calls check_batch_compatibility() with the discovered files.
    
    Args:
        folder_path: Path to folder containing .3mf files. Defaults to current directory.
    """
    console = Console()
    folder = Path(folder_path).resolve()
    
    if not folder.exists():
        console.print(f"[red]❌ Error: Folder not found: {folder}[/red]")
        return
    
    if not folder.is_dir():
        console.print(f"[red]❌ Error: Not a directory: {folder}[/red]")
        return
    
    # Find all .3mf files (case-insensitive)
    model_files = sorted([
        str(f) for f in folder.glob('*')
        if f.suffix.lower() == '.3mf' and f.is_file()
    ])
    
    if not model_files:
        console.print(f"[yellow]⚠️  No .3MF files found in: {folder}[/yellow]")
        return
    
    console.print(f"[cyan]📁 Found {len(model_files)} .3MF file(s) in: {folder}[/cyan]")
    console.print()
    
    # Call the regular batch checker with discovered files
    check_batch_compatibility(model_files)


def check_batch_compatibility(model_paths: List[str]) -> None:
    """
    Check if multiple 3MF models can be printed together in one batch.
    
    Reads .info.json files for each model, verifies file hashes, and
    analyzes color/filament compatibility.
    
    Args:
        model_paths: List of paths to 3MF files to check. Can be:
            - Full paths: "samples/test_samus.3mf"
            - Relative paths: "test_samus.3mf"
            - Just filenames: "test_samus" (adds .3mf, looks in current dir)
    """
    console = Console()
    
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🔍 Batch Compatibility Checker[/bold cyan]",
        border_style="cyan"
    ))
    console.print()
    
    # Step 1: Normalize paths and load info files for all models
    console.print("[bold]Loading model information...[/bold]")
    
    models_data = []
    warnings = []
    
    for model_path_str in model_paths:
        # Normalize the path:
        # - If no .3mf extension, add it
        # - Convert to Path object
        # - If relative, resolve against current working directory
        model_path = Path(model_path_str)
        
        # Add .3mf extension if missing
        # Use endswith() instead of suffix to handle filenames with dots (e.g., "3.5-floppy.png")
        if not model_path_str.lower().endswith('.3mf'):
            model_path = Path(model_path_str + '.3mf')
        
        # If path doesn't exist, try current directory
        if not model_path.exists():
            cwd_path = Path.cwd() / model_path.name
            if cwd_path.exists():
                model_path = cwd_path
        
        # Check if file exists
        if not model_path.exists():
            console.print(f"  [red]✗[/red] {model_path.name}: File not found")
            console.print(f"    [dim]Looked for: {model_path.absolute()}[/dim]")
            continue
        
        # Find .info.json file
        info_file = find_info_file_for_model(model_path)
        
        if not info_file:
            console.print(f"  [red]✗[/red] {model_path.name}: No .info.json file found")
            console.print(f"    [dim]Expected: {model_path.with_suffix('.info.json')}[/dim]")
            console.print(f"    [yellow]Hint: Convert this file first to generate the .info.json[/yellow]")
            continue
        
        # Read and verify info file
        try:
            info, hash_valid, message = verify_model_info(info_file)
            
            if hash_valid:
                console.print(f"  [green]✓[/green] {model_path.name}: {message}")
                models_data.append((model_path, info))
            else:
                console.print(f"  [yellow]⚠[/yellow] {model_path.name}: {message}")
                warnings.append(f"{model_path.name}: {message}")
                models_data.append((model_path, info))
        
        except Exception as e:
            console.print(f"  [red]✗[/red] {model_path.name}: Error reading info file - {e}")
            continue
    
    console.print()
    
    # If no valid models, exit
    if not models_data:
        console.print("[red]No valid model data found. Cannot perform batch check.[/red]")
        return
    
    # Show warnings if any
    if warnings:
        console.print(Panel(
            "\n".join(f"• {w}" for w in warnings),
            title="[yellow]⚠️  Warnings[/yellow]",
            border_style="yellow"
        ))
        console.print()
    
    # Step 2: Analyze compatibility
    console.print("[bold]Analyzing batch compatibility...[/bold]")
    console.print()
    
    # Get AMS configuration from first model (all should use same config)
    # Default to 4 AMS units with 4 slots each = 16 total slots
    ams_count = 4
    ams_slots_per_unit = 4
    max_slots = ams_count * ams_slots_per_unit
    
    console.print(f"[dim]AMS Configuration: {ams_count} units × {ams_slots_per_unit} slots = {max_slots} total slots[/dim]")
    console.print()
    
    # Aggregate colors from all models
    # Track: color_name -> {rgb, hex, models, count}
    color_aggregation = {}
    
    for model_path, info in models_data:
        model_name = model_path.name
        for color_info in info.get('colors', []):
            color_name = color_info['name']
            
            if color_name not in color_aggregation:
                color_aggregation[color_name] = {
                    'rgb': tuple(color_info['rgb']),
                    'hex': color_info['hex'],
                    'models': [],
                    'count': 0
                }
            
            # Track which models use this color
            color_aggregation[color_name]['models'].append(model_name)
            color_aggregation[color_name]['count'] += 1
    
    # Debug: Show all unique colors found
    console.print(f"[dim]Found {len(color_aggregation)} unique colors:[/dim]")
    for color_name in sorted(color_aggregation.keys()):
        count = color_aggregation[color_name]['count']
        console.print(f"[dim]  • {color_name} (used {count} times)[/dim]")
    console.print()
    
    # Sort colors by priority:
    # 1. Most common "White" (exact match, case-insensitive)
    # 2. Most common "Black" or "Charcoal" (exact match, case-insensitive)
    # 3. Ensure at least one complete model can be printed (all its colors loaded)
    # 4. Rest sorted by count (descending), then by name
    #
    # The key constraint: If we can't fit all colors, we MUST ensure at least
    # one complete model's colors are included, otherwise we load 16 colors
    # but can't print anything!
    
    sorted_colors = []
    white_colors = []
    black_colors = []
    other_colors = []
    
    for color_name, color_data in color_aggregation.items():
        # Check if this is white, black, or charcoal
        # Look for exact word matches (case-insensitive)
        name_lower = color_name.lower()
        words = name_lower.split()
        
        if 'white' in words:
            white_colors.append((color_name, color_data))
        elif 'black' in words or 'charcoal' in words:
            black_colors.append((color_name, color_data))
        else:
            other_colors.append((color_name, color_data))
    
    # Sort whites and blacks by count (descending) to get most common first
    white_colors.sort(key=lambda x: (-x[1]['count'], x[0]))
    black_colors.sort(key=lambda x: (-x[1]['count'], x[0]))
    
    # Start building color list: most common white, most common black
    priority_colors = []
    if white_colors:
        priority_colors.append(white_colors[0])  # Only take the most common white
    if black_colors:
        priority_colors.append(black_colors[0])  # Only take the most common black
    
    # Get the set of colors we've already included
    included_color_names = {color_name for color_name, _ in priority_colors}
    
    # Check if all colors fit - if yes, we don't need special logic
    total_colors = len(color_aggregation)
    colors_fit = total_colors <= max_slots
    
    if not colors_fit:
        # We can't fit everything. Goal: Maximize the NUMBER of models that can print.
        # Strategy: Find the combination of colors that allows the most models to complete.
        
        slots_used = len(priority_colors)
        slots_remaining = max_slots - slots_used
        
        console.print(f"[dim]Optimizing color selection to maximize printable models...[/dim]")
        
        # Build list of all models with their color requirements
        model_requirements = []
        for model_path, info in models_data:
            model_colors = {c['name'] for c in info.get('colors', [])}
            additional_needed = model_colors - included_color_names
            model_requirements.append({
                'name': model_path.name,
                'all_colors': model_colors,
                'additional_needed': additional_needed,
                'num_additional': len(additional_needed)
            })
        
        # Try greedy approach: repeatedly pick the model that adds the FEWEST new colors
        # while maximizing total printable models
        selected_colors = set(included_color_names)
        printable_models = []
        
        while slots_remaining > 0:
            best_choice = None
            best_new_printable = 0
            
            # For each model not yet printable, see how many slots it would need
            for model_req in model_requirements:
                if model_req['name'] in [m['name'] for m in printable_models]:
                    continue  # Already printable
                
                # Calculate colors needed for this model
                colors_needed = model_req['all_colors'] - selected_colors
                num_needed = len(colors_needed)
                
                if num_needed == 0:
                    # This model is already printable! Add it.
                    printable_models.append(model_req)
                    continue
                
                if num_needed > slots_remaining:
                    continue  # Can't fit this model
                
                # If we add this model's colors, how many NEW models become printable?
                test_colors = selected_colors | colors_needed
                new_printable_count = 0
                new_printable_models = []
                
                for other_model in model_requirements:
                    if other_model['name'] in [m['name'] for m in printable_models]:
                        continue
                    if other_model['all_colors'].issubset(test_colors):
                        new_printable_count += 1
                        new_printable_models.append(other_model)
                
                # Pick the model that enables the most new printable models
                # Tiebreaker: fewest colors needed
                if new_printable_count > best_new_printable or \
                   (new_printable_count == best_new_printable and 
                    (best_choice is None or num_needed < len(best_choice['colors_needed']))):
                    best_new_printable = new_printable_count
                    best_choice = {
                        'model': model_req,
                        'colors_needed': colors_needed,
                        'new_printable': new_printable_models
                    }
            
            # If we found a beneficial choice, apply it
            if best_choice and best_new_printable > 0:
                model_name = best_choice['model']['name']
                colors_to_add = best_choice['colors_needed']
                
                console.print(f"[dim]  Adding {len(colors_to_add)} colors for {model_name} (enables {best_new_printable} model(s))[/dim]")
                
                for color_name in colors_to_add:
                    priority_colors.append((color_name, color_aggregation[color_name]))
                    selected_colors.add(color_name)
                
                slots_remaining -= len(colors_to_add)
                
                # Mark all newly printable models
                for new_model in best_choice['new_printable']:
                    printable_models.append(new_model)
            else:
                # No beneficial choice found, stop optimization
                break
        
        # Update included_color_names with optimized selection
        included_color_names = selected_colors
        
        console.print(f"[dim]Optimization complete: {len(printable_models)} model(s) can print with {max_slots - slots_remaining} colors[/dim]")
        console.print()
    
    # Sort remaining colors by count (desc), then name (asc)
    # Only exclude colors already included in priority_colors
    remaining_colors = []
    for name, data in color_aggregation.items():
        if name in included_color_names:
            continue
        remaining_colors.append((name, data))
    
    remaining_colors.sort(key=lambda x: (-x[1]['count'], x[0]))
    
    # Build final sorted list
    sorted_colors = priority_colors + remaining_colors
    
    # Assign slots
    from .summary_writer import index_to_ams_slot
    
    slot_assignments = []
    for i, (color_name, color_data) in enumerate(sorted_colors):
        if i >= max_slots:
            # Ran out of slots
            break
        
        slot_name = index_to_ams_slot(i, ams_count, ams_slots_per_unit)
        slot_assignments.append({
            'slot': slot_name,
            'color_name': color_name,
            'hex': color_data['hex'],
            'rgb': color_data['rgb'],
            'count': color_data['count'],
            'models': color_data['models']
        })
    
    # Re-check if all colors fit (after our adjustments)
    total_colors = len(sorted_colors)
    colors_fit = total_colors <= max_slots
    
    console.print(f"[bold]Total unique colors across all models: {total_colors}[/bold]")
    if colors_fit:
        console.print(f"[green]✓ All colors fit in available AMS slots ({max_slots} slots)[/green]")
    else:
        console.print(f"[yellow]⚠ Too many colors! Need {total_colors} slots but only have {max_slots}[/yellow]")
    console.print()
    
    # Show loaded models summary
    summary_table = Table(title="Loaded Models", box=box.ROUNDED)
    summary_table.add_column("Model", style="cyan")
    summary_table.add_column("Colors", justify="right", style="white")
    summary_table.add_column("Dimensions (mm)", justify="right", style="white")
    
    for model_path, info in models_data:
        colors_count = len(info.get('colors', []))
        dims = info.get('model_dimensions', {})
        dim_str = f"{dims.get('width_mm', 0):.1f} × {dims.get('height_mm', 0):.1f}"
        
        summary_table.add_row(
            model_path.name,
            str(colors_count),
            dim_str
        )
    
    console.print(summary_table)
    console.print()
    
    # Determine first batch models if colors don't fit
    first_batch_model_names = []
    if not colors_fit:
        assigned_color_names = {slot['color_name'] for slot in slot_assignments}
        for model_path, info in models_data:
            model_colors = {c['name'] for c in info.get('colors', [])}
            if model_colors.issubset(assigned_color_names):
                first_batch_model_names.append(model_path.name)
    
    # Show AMS slot assignments
    slot_table = Table(title="Recommended AMS Slot Assignments", box=box.ROUNDED)
    slot_table.add_column("Slot", style="cyan", justify="center")
    slot_table.add_column("Color/Filament", style="white")
    slot_table.add_column("Hex", style="dim")
    slot_table.add_column("Used In", justify="right", style="yellow")
    slot_table.add_column("Models", style="dim")
    
    for slot_info in slot_assignments:
        # Format model list (truncate if too long)
        models_str = ", ".join(slot_info['models'])
        if len(models_str) > 40:
            models_str = models_str[:37] + "..."
        
        # Determine styling:
        # - Bold green: used in ALL models (never swap)
        # - Dim: only used in remaining models (could skip/load later)
        # - Normal: used in first batch models
        is_in_all_models = slot_info['count'] == len(models_data)
        
        # Check if this color is only in remaining models (not in first batch)
        only_in_remaining = False
        if not colors_fit and first_batch_model_names:
            color_models = set(slot_info['models'])
            only_in_remaining = len(color_models.intersection(first_batch_model_names)) == 0
        
        if is_in_all_models:
            row_style = "bold green"
        elif only_in_remaining:
            row_style = "dim"
        else:
            row_style = None
        
        slot_table.add_row(
            slot_info['slot'],
            slot_info['color_name'],
            slot_info['hex'],
            f"{slot_info['count']}/{len(models_data)}",
            models_str,
            style=row_style
        )
    
    console.print(slot_table)
    console.print()
    
    # Show recommendations
    if colors_fit:
        console.print(Panel(
            "[green]✓ All models can be printed in one batch![/green]\n\n"
            f"Load the {len(slot_assignments)} colors shown above into your AMS units and\n"
            "you can print all models without needing to swap filaments.",
            title="[bold green]Batch Compatible[/bold green]",
            border_style="green"
        ))
    else:
        # Determine which models can be printed first
        # Models that only use colors in the first max_slots colors
        assigned_color_names = {slot['color_name'] for slot in slot_assignments}
        
        first_batch_models = []
        remaining_models = []
        
        for model_path, info in models_data:
            model_colors = {c['name'] for c in info.get('colors', [])}
            if model_colors.issubset(assigned_color_names):
                first_batch_models.append(model_path.name)
            else:
                remaining_models.append((model_path.name, model_colors - assigned_color_names))
        
        # Sort remaining models by number of extra colors needed (descending - most colors first)
        remaining_models.sort(key=lambda x: (-len(x[1]), x[0]))
        
        console.print(Panel(
            f"[yellow]⚠ Too many colors for one batch[/yellow]\n\n"
            f"You have {total_colors} unique colors but only {max_slots} AMS slots.\n\n"
            f"[bold]Recommended approach:[/bold]\n"
            f"1. Load the {len(slot_assignments)} colors shown above (most frequently used)\n"
            f"2. Print these models first: [cyan]{', '.join(first_batch_models) if first_batch_models else 'None (all need color swaps)'}[/cyan]\n"
            f"3. After first batch, swap filaments for remaining models\n\n"
            f"[dim]Models needing color swaps: {len(remaining_models)}[/dim]",
            title="[bold yellow]Batch Requires Multiple Builds[/bold yellow]",
            border_style="yellow"
        ))
        
        if remaining_models:
            console.print()
            console.print("[bold]Remaining models and their additional colors:[/bold]")
            for model_name, extra_colors in remaining_models:
                colors_list = ', '.join(sorted(extra_colors))
                console.print(f"  • [cyan]{model_name}[/cyan]: {colors_list}")
