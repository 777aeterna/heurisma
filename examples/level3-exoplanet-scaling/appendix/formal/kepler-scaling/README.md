# Formal Verification Workspace: `kepler-scaling`

Layout modeled on `anthropics/formal-math`:
- `Challenge.lean`: formal target statement (`namespace Challenge`; `sorry` permitted only as problem placeholder).
- `Solution.lean`: machine-checked proof (`namespace Solution`; `0` `sorry`, standard axioms only, kernel-checked to inhabit `Challenge`'s exact theorem type).
- Toolchain: `leanprover/lean4:v4.16.0` (standalone Core/Std; pass --mathlib when Mathlib4 is required).
- Verify locally: `python3 -B <skill-dir>/scripts/formal_math.py check kepler-scaling`
