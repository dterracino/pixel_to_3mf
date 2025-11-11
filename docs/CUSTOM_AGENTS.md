# Custom AI Agents

This document describes the custom AI agents available for this project. These specialized agents have been tuned for specific tasks and should be used when working on their respective areas.

## Overview

Custom agents are specialized AI assistants with domain-specific expertise. They understand this project's architecture, conventions, and patterns. When working in their area of expertise, they provide better results than general-purpose assistants.

## Available Agents

### 3D Printing Specialist

**File:** `.github/agents/3d-printing-specialist.md`

**Purpose:** Expert in FDM printing, Bambu Lab printers, filament behavior, G-code, 3MF format, and HueForge-style layered printing.

**When to Use:**

- Working with 3MF file format and structure
- Optimizing meshes for 3D printing
- Printer-specific optimization (especially Bambu Lab)
- Debugging mesh topology issues (manifold meshes, winding order)
- Filament selection and color matching for printing
- Understanding G-code generation and slicing behavior
- HueForge multi-color layer printing techniques

**Capabilities:**

- Deep knowledge of 3MF file format specification
- Understanding of manifold mesh requirements
- Expertise in mesh geometry and topology
- Printer calibration and tuning (flow, retraction, pressure advance)
- Filament behavior and material properties
- G-code analysis and optimization
- Multi-material and multi-color printing strategies
- Integration with color_tools for filament matching

**Example Usage:**

```text
Use the 3d-printing-specialist to optimize the mesh generation for better slicing results
```

---

### Bug Specialist

**File:** `.github/agents/bug-specialist.md`

**Purpose:** Identifies and fixes bugs, detects code smells, creates bug reports, and ensures code quality.

**When to Use:**

- Debugging issues or errors
- Fixing failing tests
- Investigating unexpected behavior
- Scanning for code quality issues
- Adding missing type hints
- Finding and fixing magic numbers
- Detecting separation of concerns violations

**Capabilities:**

- Root cause analysis of bugs
- Detection of common code smells:
  - Magic numbers not in constants
  - Missing type hints
  - Separation of concerns violations
  - DRY violations
  - Missing input validation
  - Poor error handling
- Creation of detailed bug reports for complex issues
- Addition of regression tests
- Code quality improvements

**Example Usage:**

```text
Use the bug-specialist to investigate why the mesh generator is producing non-manifold geometry
```

---

### Cleanup Specialist

**File:** `.github/agents/cleanup-specialist.md`

**Purpose:** Cleans up messy code, removes duplication, and improves maintainability.

**When to Use:**

- Removing dead code
- Eliminating duplicate code
- Cleaning up documentation
- Simplifying complex logic
- Standardizing code style

**Capabilities:**

- Identifying and removing unused code
- Consolidating duplicate logic
- Simplifying overly complex functions
- Cleaning up documentation
- Improving code organization

**Example Usage:**

```text
Use the cleanup-specialist to remove duplicate color validation code across modules
```

---

### Color Science Specialist

**File:** `.github/agents/color-science-specialist.md`

**Purpose:** Expert in color spaces, conversion accuracy, Delta E metrics, gamut mapping, and color matching using the color_tools library.

**When to Use:**

- Color space conversions (RGB, Lab, HSL, HSV, XYZ, OKLab)
- Calculating color differences (Delta E 2000, Delta E 76, etc.)
- Filament color matching and recommendations
- Gamut mapping and color accuracy
- Understanding transfer functions and gamma correction
- CSS color name matching
- Perceptual color analysis

**Capabilities:**

- Deep understanding of color spaces and their properties
- Expertise in Delta E 2000 for perceptual color distance
- Knowledge of sRGB, Display P3, Rec.709, Rec.2020 gamuts
- Transfer function expertise (sRGB EOTF/OETF, linearization)
- Integration with color_tools library (color-match-tools package)
- Filament palette management and matching
- CSS color database knowledge (147 named colors)
- Understanding of human color perception

**Example Usage:**

```text
Use the color-science-specialist to improve the Delta E calculation for better color matching
```

---

### Custom Agent Generator

**File:** `.github/agents/custom-agent-generator.md`

**Purpose:** Creates new custom agent definition files following project conventions.

**When to Use:**

- Creating new custom agents
- Updating existing agent definitions
- Designing agent workflows and capabilities

**Capabilities:**

- Understanding agent file structure and conventions
- Designing focused, single-purpose agents
- Selecting appropriate tools and permissions
- Including project-specific context
- Writing actionable guidance

**Example Usage:**

```text
Use the custom-agent-generator to create a new agent specialized in mesh optimization
```

---

### Docstring Specialist

**File:** `.github/agents/docstring-specialist.md`

**Purpose:** Creates and updates docstring comments that explain WHY over WHAT.

**When to Use:**

- Adding docstrings to new functions
- Improving existing documentation
- Explaining complex algorithms
- Documenting design decisions

**Capabilities:**

- Writing WHY-focused docstrings
- Following Google-style docstring format
- Explaining design decisions and trade-offs
- Adding helpful examples
- Maintaining friendly, approachable tone
- Understanding Python 3.10+ features

**Example Usage:**

```text
Use the docstring-specialist to add comprehensive docstrings to the polygon optimizer module
```

---

### Implementation Planner

**File:** `.github/agents/implementation-planner.md`

**Purpose:** Creates detailed implementation plans for new features and complex changes.

**When to Use:**

- Planning new features
- Breaking down complex changes
- Designing architecture for new functionality
- Assessing risks and dependencies
- Creating roadmaps for major work

**Capabilities:**

- Breaking down requirements into actionable tasks
- Identifying dependencies and ordering work
- Planning for testing at each stage
- Anticipating edge cases and risks
- Creating comprehensive task checklists
- Ensuring alignment with project architecture

**Example Usage:**

```text
Use the implementation-planner to create a plan for adding image preprocessing support
```

---

### README Specialist

**File:** `.github/agents/readme-specialist.md`

**Purpose:** Creates and improves README files and project documentation.

**When to Use:**

- Creating or updating README.md
- Writing project documentation
- Creating usage examples
- Documenting features

**Capabilities:**

- Writing clear, comprehensive documentation
- Creating effective examples
- Structuring documentation logically
- Maintaining consistent tone

**Example Usage:**

```text
Use the readme-specialist to update the README with the new quantization feature
```

---

### Refactoring Specialist

**File:** `.github/agents/refactoring-specialist.md`

**Purpose:** Expert in Python refactoring, code cleanup, bug fixes, documentation, and unit testing with deep knowledge of this project's architecture.

**When to Use:**

- Large-scale refactoring
- Improving code structure
- Extracting common patterns
- Simplifying complex code
- Adding or improving tests

**Capabilities:**

- Deep understanding of project architecture
- Knowledge of all design patterns used
- Expertise in Python 3.10+ features
- Unit testing with unittest framework
- Maintaining separation of concerns
- Following DRY principles

**Example Usage:**

```text
Use the refactoring-specialist to refactor the mesh generation pipeline for better maintainability
```

---

### Test Specialist

**File:** `.github/agents/test-specialist.md`

**Purpose:** Expert in creating comprehensive unit tests and ensuring thorough test coverage.

**When to Use:**

- Writing tests for new features
- Adding regression tests for bug fixes
- Improving test coverage
- Testing edge cases
- Creating test fixtures and helpers

**Capabilities:**

- Expertise in unittest framework
- Test design patterns (AAA, Given-When-Then)
- Edge case identification
- Testing exceptions and callbacks
- Using test helpers and fixtures
- Integration vs unit test decisions
- Coverage analysis

**Example Usage:**

```text
Use the test-specialist to create comprehensive tests for the new quantization module
```

---

### Type Specialist

**File:** `.github/agents/type-specialist.md`

**Purpose:** Expert in Python type hinting and static type checking with Pylance/Pyright.

**When to Use:**

- Adding type hints to code
- Fixing type errors from Pylance/Pyright
- Ensuring type safety
- Modernizing type hints to Python 3.10+ syntax

**Capabilities:**

- Modern Python 3.10+ type syntax (str | None, list[str])
- Pyright/Pylance error resolution
- Type narrowing and type guards
- Generic types and protocols
- Version-appropriate type hints
- Running and fixing pyright errors

**Example Usage:**

```text
Use the type-specialist to add type hints to the new configuration module
```

---

### UI Specialist

**File:** `.github/agents/ui-specialist.md`

**Purpose:** Creates and reviews application UI, progress reporting, text output, and command-line interfaces.

**When to Use:**

- Adding new CLI arguments
- Improving user feedback
- Standardizing error messages
- Adding progress reporting
- Improving help text
- Fixing UI inconsistencies

**Capabilities:**

- CLI design with argparse
- Progress reporting patterns
- Error message formatting
- User communication best practices
- Separation of UI from business logic
- DRY principles for UI code
- Consistent terminology and messaging

**Example Usage:**

```text
Use the ui-specialist to improve the progress reporting during mesh generation
```

## General Guidelines

### When to Use Custom Agents

**Use custom agents when:**

- Working in their area of expertise
- Need specialized knowledge of project patterns
- Want consistent, high-quality results
- Task aligns with agent's purpose

**Don't use custom agents when:**

- Task is outside their scope
- Need general programming help
- Simple one-line changes
- Exploratory analysis

### How to Trigger Custom Agents

Custom agents can be invoked by explicitly mentioning them or through context-based automatic triggering:

**Explicit Invocation:**

```text
Use the [agent-name] to [specific task]
```

**Context-Based (Automatic):**

- 3D printing/geometry issues → 3D printing specialist
- Color matching/conversion → Color science specialist
- Editing Python code → Consider type-specialist for type hints
- Adding CLI arguments → UI specialist
- Fixing bugs → Bug specialist
- Writing docstrings → Docstring specialist
- Creating new agent → Custom-agent-generator
- Planning new features → Implementation planner
- Writing tests → Test specialist

### Combining Multiple Agents

For complex tasks, multiple agents can work sequentially:

```text
1. Use implementation-planner to break down a complex feature
2. Use 3d-printing-specialist to fix the mesh topology issue
3. Use type-specialist to add proper type hints to the fixed code
4. Use test-specialist to create comprehensive tests
5. Use docstring-specialist to document why the fix works
6. Use refactoring-specialist to clean up the final code
```

## Project-Specific Context

All custom agents understand these project principles:

### Architecture

- **Separation of Concerns**: CLI layer (cli.py) vs business logic (all other modules)
- **DRY Principles**: No duplicate code, extract common patterns
- **Constants Centralization**: All magic numbers in constants.py

### Python Standards

- **Version**: Python 3.10+ (use modern syntax)
- **Type Hints**: Required on all functions (str | None, list[str])
- **Docstrings**: Explain WHY, not just WHAT (Google-style)
- **Testing**: unittest framework

### Critical Conventions

1. NO print statements in business logic modules
2. ALL magic numbers must be in constants.py
3. Type hints required on ALL function signatures
4. Docstrings explain WHY, not just WHAT
5. Progress reporting via callbacks, not print

## Creating New Custom Agents

To create a new custom agent, use the **custom-agent-generator**:

```text
Use the custom-agent-generator to create a new agent for [specific purpose]
```

The generator will:

1. Design an appropriate agent structure
2. Define the agent's scope and capabilities
3. Select necessary tools
4. Include project-specific context
5. Provide actionable guidance
6. Create quality checklists

## Troubleshooting

**Agent not understanding project context?**

- Ensure the agent's definition file is up to date
- Provide additional context in your request
- Check that the agent is the right one for the task

**Agent making changes outside its scope?**

- Be more specific in your request
- Use a different agent better suited for the task
- Review the agent's capabilities in this document

**Need a new agent?**

- Use the custom-agent-generator to create one
- Document the new agent in this file
- Update .github/copilot-instructions.md with triggering rules

## Contributing

When updating custom agents:

1. Edit the agent file in `.github/agents/`
2. Update this documentation file
3. Update `.github/copilot-instructions.md` if triggering rules change
4. Test the agent with typical use cases
5. Document any new capabilities

## See Also

- [Suggested Custom Agents](SUGGESTED_CUSTOM_AGENTS.md) - Ideas for future agents
- [Copilot Instructions](../.github/copilot-instructions.md) - General agent guidelines and project-wide AI instructions
