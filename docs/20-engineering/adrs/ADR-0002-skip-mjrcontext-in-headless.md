# ADR-0002: Skip MjrContext Creation in Headless Mode

## Status
Accepted

## Context
The MuJoCo backend was experiencing segmentation faults when running in headless mode. Investigation revealed that `MjrContext` (MuJoCo's rendering context) requires an OpenGL context to be initialized, which is not available in headless environments by default.

**Problem:**
- Creating `MjrContext` in headless mode causes C-level segmentation faults
- Python exceptions cannot catch segfaults that occur in C libraries
- The backend is a scaffold implementation that returns placeholder images anyway

**Constraints:**
- Must maintain API contract (return `FrameBundle`)
- Should work in headless CI/CD environments
- Full OpenGL setup (EGL/OSMesa) is complex and beyond scaffold scope

## Options considered

1. **Set up EGL/OSMesa for headless OpenGL**
   - Pros: Enables full rendering capabilities
   - Cons: Complex setup, additional dependencies, significant implementation effort
   - Cons: May not work across all platforms/environments

2. **Lazy initialization with error handling**
   - Pros: Attempts to create context only when needed
   - Cons: Still crashes with segfault (can't catch C-level errors)
   - Cons: Doesn't solve the fundamental problem

3. **Skip MjrContext creation entirely, return placeholders**
   - Pros: Prevents segfaults, simple implementation
   - Pros: Maintains API contract, works in all environments
   - Cons: No actual rendering (but scaffold doesn't need it)

4. **Conditional context creation based on environment detection**
   - Pros: Could enable rendering when OpenGL is available
   - Cons: Complex detection logic, still risks segfaults if detection fails
   - Cons: Inconsistent behavior across environments

## Decision
**Skip `MjrContext` creation entirely** and return placeholder images from `render()`.

**Implementation:**
- Remove all `MjrContext` creation code from `start()` and `load_scene()`
- Simplify `render()` to return placeholder `FrameBundle` immediately
- Add clear comments explaining why context creation is skipped

## Consequences

**Positive**
- ✅ No more segmentation faults
- ✅ Works reliably in headless environments (CI/CD, servers)
- ✅ Simple, maintainable code
- ✅ Maintains API contract
- ✅ Fast execution (no OpenGL initialization overhead)

**Negative**
- ❌ No actual rendering (returns placeholder images)
- ❌ Future developers may need to implement EGL/OSMesa setup for real rendering
- ❌ May confuse users expecting actual rendered output

**Mitigations**
- Clear documentation in code comments
- Troubleshooting guide documents the limitation
- Scaffold nature of implementation is documented in README

## Follow-ups
- If full rendering is needed in the future, implement EGL/OSMesa setup
- Consider adding environment detection to enable rendering when OpenGL is available
- Document rendering limitations in user-facing documentation

## Date / Owners
- Date: 2025-12-27
- Owners: Founder

## References
- Troubleshooting guide: `docs/20-engineering/troubleshooting.md`
- Code: `simdata/backends/mujoco/backend.py`

