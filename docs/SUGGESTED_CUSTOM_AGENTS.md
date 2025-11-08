# Suggested Custom Agents

This document contains suggestions for new custom agents that could help improve development efficiency and code quality for this project. These are ideas that haven't been implemented yet but would be valuable additions.

## High Priority Suggestions

### 1. Test Generator

**Purpose:** Automatically generate comprehensive unit tests for Python code.

**Rationale:** While we have good test coverage, adding tests for new features is time-consuming. A specialized agent could generate unittest-based tests following our existing patterns.

**Capabilities:**
- Generate test cases for new functions/classes
- Follow unittest framework patterns
- Use test_helpers.py utilities
- Create test fixtures programmatically
- Cover edge cases and error conditions
- Follow project's test structure and naming

**Example Usage:**
```
Use the test-generator to create comprehensive tests for the new quantization module
```

**Implementation Notes:**
- Should understand unittest framework
- Must use test_helpers.py for image creation
- Should create both success and failure test cases
- Must include proper setUp/tearDown

---

### 2. Performance Optimizer

**Purpose:** Analyze and optimize code performance, particularly for image processing and mesh generation.

**Rationale:** Large images and complex meshes can be slow to process. A specialist could identify bottlenecks and suggest optimizations.

**Capabilities:**
- Profile code to find performance bottlenecks
- Suggest algorithmic improvements
- Identify inefficient NumPy usage
- Recommend caching strategies
- Optimize loop structures
- Suggest parallel processing opportunities

**Example Usage:**
```
Use the performance-optimizer to improve mesh generation speed for large images
```

**Implementation Notes:**
- Should use Python profiling tools (cProfile, timeit)
- Must maintain code correctness
- Should measure before/after performance
- Must not sacrifice code readability for marginal gains

---

### 3. Config Specialist

**Purpose:** Manage configuration files, constants, and user-configurable options.

**Rationale:** As the project grows, configuration management becomes more complex. A specialist could ensure consistent configuration patterns.

**Capabilities:**
- Manage constants.py organization
- Add new configuration options
- Ensure proper defaults
- Update CLI arguments for new config
- Validate configuration values
- Document configuration options

**Example Usage:**
```
Use the config-specialist to add support for custom color palettes
```

**Implementation Notes:**
- Must update constants.py
- Should update CLI arguments
- Must add validation
- Should update documentation

---

### 4. 3MF Format Specialist

**Purpose:** Expert in the 3MF file format specification and implementation.

**Rationale:** 3MF format is complex with many optional features. A specialist could ensure spec compliance and add advanced features.

**Capabilities:**
- Deep understanding of 3MF specification
- Implement advanced 3MF features
- Ensure slicer compatibility
- Debug 3MF validation issues
- Add support for new 3MF extensions
- Optimize 3MF file size

**Example Usage:**
```
Use the 3mf-format-specialist to add support for textures in the 3MF output
```

**Implementation Notes:**
- Must maintain slicer compatibility
- Should validate against 3MF spec
- Must test with multiple slicers
- Should document format decisions

---

### 5. Dependency Manager

**Purpose:** Manage project dependencies, versions, and compatibility.

**Rationale:** Keeping dependencies up to date and compatible is important but tedious. A specialist could automate this.

**Capabilities:**
- Update requirements.txt
- Check for security vulnerabilities
- Ensure version compatibility
- Suggest dependency alternatives
- Update dependency-related code
- Test after dependency updates

**Example Usage:**
```
Use the dependency-manager to update Pillow to the latest version
```

**Implementation Notes:**
- Must run tests after updates
- Should check security advisories
- Must verify compatibility
- Should update documentation

---

## Medium Priority Suggestions

### 6. Error Message Specialist

**Purpose:** Create helpful, user-friendly error messages throughout the application.

**Rationale:** Good error messages improve user experience. A specialist could ensure all errors are clear and actionable.

**Capabilities:**
- Review and improve error messages
- Add helpful tips to errors
- Ensure consistent error format
- Add context to exceptions
- Suggest solutions in error text
- Validate error message clarity

**Example Usage:**
```
Use the error-message-specialist to improve validation error messages
```

---

### 7. Example Generator

**Purpose:** Create comprehensive usage examples and sample files.

**Rationale:** Good examples help users understand features. A specialist could generate varied examples.

**Capabilities:**
- Create sample pixel art images
- Generate example code snippets
- Create batch processing examples
- Generate comparison examples
- Create troubleshooting examples
- Update README with examples

**Example Usage:**
```
Use the example-generator to create examples for the new quantization feature
```

---

### 8. Migration Specialist

**Purpose:** Help migrate code between Python versions or update deprecated patterns.

**Rationale:** Python evolves, and keeping code modern is important. A specialist could handle migrations systematically.

**Capabilities:**
- Update to newer Python syntax
- Replace deprecated patterns
- Modernize type hints
- Update to new library APIs
- Ensure backward compatibility
- Test migration changes

**Example Usage:**
```
Use the migration-specialist to update code to Python 3.12 syntax
```

---

### 9. Batch Processing Specialist

**Purpose:** Optimize and enhance batch image processing capabilities.

**Rationale:** Batch processing is a key feature that could be enhanced with better error handling, parallelization, and reporting.

**Capabilities:**
- Improve batch processing logic
- Add parallel processing support
- Enhance error handling for batches
- Create detailed batch reports
- Optimize batch performance
- Add batch configuration options

**Example Usage:**
```
Use the batch-processing-specialist to add parallel processing for batch conversions
```

---

### 10. Validation Specialist

**Purpose:** Add comprehensive input validation throughout the application.

**Rationale:** Robust validation prevents errors and improves user experience. A specialist could ensure thorough validation.

**Capabilities:**
- Add input validation
- Create validation functions
- Ensure consistent validation patterns
- Add helpful validation messages
- Validate configuration
- Test validation edge cases

**Example Usage:**
```
Use the validation-specialist to add comprehensive input validation for image files
```

---

## Lower Priority Suggestions

### 11. Logging Specialist

**Purpose:** Add comprehensive logging throughout the application.

**Rationale:** Good logging helps with debugging and monitoring. Currently minimal logging exists.

**Capabilities:**
- Add Python logging framework
- Configure log levels
- Add strategic log points
- Create log message templates
- Ensure no performance impact
- Configure log output formats

---

### 12. Internationalization (i18n) Specialist

**Purpose:** Prepare application for multi-language support.

**Rationale:** Global users would benefit from translated UI. Currently English-only.

**Capabilities:**
- Extract translatable strings
- Implement i18n framework
- Create translation templates
- Support multiple languages
- Maintain translation files
- Test with different locales

---

### 13. Accessibility Specialist

**Purpose:** Ensure CLI output is accessible to all users.

**Rationale:** Users with screen readers or color blindness need accessible output.

**Capabilities:**
- Ensure screen reader compatibility
- Provide text alternatives to emojis
- Support --no-color mode
- Create accessible error messages
- Test with accessibility tools
- Document accessibility features

---

### 14. Security Specialist

**Purpose:** Audit and improve application security.

**Rationale:** File processing applications can have security vulnerabilities. Need systematic review.

**Capabilities:**
- Audit for security issues
- Validate user inputs
- Check file operations safety
- Prevent path traversal
- Handle malicious images safely
- Follow security best practices

---

### 15. Deployment Specialist

**Purpose:** Help with packaging and distribution of the application.

**Rationale:** Making the application easy to install and distribute is important for users.

**Capabilities:**
- Create PyPI package
- Write setup.py/pyproject.toml
- Create installation instructions
- Build distribution packages
- Create release process
- Update versioning

---

## Specialized Domain Agents

### 16. Mesh Topology Specialist

**Purpose:** Expert in 3D mesh topology and manifold geometry.

**Rationale:** Mesh generation is complex and errors can cause slicer failures. Deep expertise needed.

**Capabilities:**
- Ensure manifold meshes
- Fix topology errors
- Optimize mesh structure
- Validate mesh properties
- Improve mesh algorithms
- Debug slicer compatibility

---

### 17. Color Science Specialist

**Purpose:** Expert in color theory, color spaces, and color matching.

**Rationale:** Color matching and naming is complex. Delta E calculations could be improved.

**Capabilities:**
- Improve color matching algorithms
- Support different color spaces
- Enhance color quantization
- Optimize Delta E calculations
- Add color calibration
- Support ICC profiles

---

### 18. Image Processing Specialist

**Purpose:** Expert in image processing algorithms and PIL/Pillow.

**Rationale:** Image processing is core functionality. Specialist could optimize and enhance.

**Capabilities:**
- Optimize image loading
- Improve color extraction
- Enhance transparency handling
- Add image preprocessing
- Implement filtering
- Support more formats

---

### 19. Geometry Optimization Specialist

**Purpose:** Expert in polygon simplification and geometric optimization.

**Rationale:** The polygon_optimizer.py module needs expertise in computational geometry.

**Capabilities:**
- Improve Douglas-Peucker algorithm
- Add other simplification methods
- Optimize for 3D printing
- Balance detail vs file size
- Handle complex geometries
- Benchmark optimization results

---

### 20. Slicing Software Specialist

**Purpose:** Expert in slicer software compatibility (PrusaSlicer, Bambu Studio, Cura, etc.).

**Rationale:** Output needs to work well in various slicers. Specialist could ensure compatibility.

**Capabilities:**
- Test with multiple slicers
- Ensure compatibility
- Optimize for slicer performance
- Debug slicer-specific issues
- Add slicer-specific features
- Document slicer requirements

---

## Implementation Priority

### Immediate Value
1. Test Generator - Most impactful for development speed
2. Performance Optimizer - Addresses user pain points
3. Config Specialist - Growing configuration complexity

### Short Term
4. 3MF Format Specialist - Core functionality enhancement
5. Error Message Specialist - Improves user experience
6. Example Generator - Helps users understand features

### Medium Term
7. Batch Processing Specialist - Enhances key feature
8. Validation Specialist - Improves robustness
9. Migration Specialist - Keeps code modern

### Long Term
10. All others as needed based on project evolution

## Creating These Agents

To create any of these suggested agents, use the **custom-agent-generator**:

```
Use the custom-agent-generator to create a [suggested-agent-name] based on the suggestions in SUGGESTED_CUSTOM_AGENTS.md
```

The generator will:
1. Review the suggestion
2. Design the complete agent
3. Create the agent definition file
4. Include project-specific context
5. Provide implementation guidance

## Contributing Suggestions

Have an idea for a new custom agent? Add it to this document with:

1. **Purpose:** Clear description of what the agent does
2. **Rationale:** Why this agent would be valuable
3. **Capabilities:** What the agent can do
4. **Example Usage:** How to invoke the agent
5. **Implementation Notes:** Key considerations

Then update the priority ranking based on current project needs.

## See Also

- [Custom Agents](CUSTOM_AGENTS.md) - Documentation for existing agents
- [Copilot Instructions](../.github/copilot-instructions.md) - General agent guidelines
- [Custom Agent Generator](../.github/agents/custom-agent-generator.md) - Tool for creating new agents
