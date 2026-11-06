# Program 2 Plan: Hardware Synthesis (HLS)

**EC551, Fall 2026 · Ritwick & Lohit · Due Tue 11/10**: a public GitHub link, followed by a live 30-minute demo where Prof. Densmore writes his own equations and directs three test runs.

**How we work:** we settle the decisions first, then build one milestone at a time, and build only what the assignment asks for.

## Decisions

Each decision goes here once we both agree on it.

### A. Language, repo, branches (decided 11/6)

- **Language:** Python 3.12, standard library only; pytest for tests.
- **Where it runs:** the professor's equations get compiled live on the machine running Vivado (a lab PC or Lohit's laptop), so the tool uses no outside packages and nothing OS-specific.
- **Repo:** `ritwick-arch/EC-551-Lab-Project-2-Ritwick-and-Lohit-`.
- **Branches:** Lohit works on `Lohit`, Ritwick on his own branch, and they merge into `main` once at the end.

### B. Input format (decided 11/6)

- **Line format:** one equation per line, written `dst = a op b`. Spaces are optional.
- **Operations:** only the three in the spec: `+`, `-` (left minus right) and `*`. All three are unsigned, and results wrap at the datapath width chosen in H. Per the spec, negative results don't need handling.
- **Names:** a letter first, then any mix of letters, digits and `_`. Names are case-sensitive.
- **Operands:** a name, or a non-negative whole number that fits the datapath width (e.g. `Y = X * 3`).
- **Skipped:** blank lines and `#` comments. Windows line endings and a UTF-8 BOM are accepted.
- **Errors:** the message names the line and nothing is generated. An error is raised for:
  - any other line shape: `X = A + B + C`, parentheses, `/`, `X = -A`, `X = A`, `3 = A + B`
  - an empty file
  - more than 20 equations
- **Inputs:** names read before they're assigned, listed in order of first appearance.
- **Outputs:** the final value of every assigned variable.
- Equations are kept as written: duplicates aren't merged and unused results aren't dropped.

### C. SSA naming and export (decided 11/6)

- **Naming:** every value gets a version number. Inputs are `A_0`, and each assignment to `X` takes the next number: `X_1`, `X_2`, and so on.
- **Why version every value:** the digits after the last `_` are always the version, so names can't collide. A user variable called `X_1` becomes `X_1_1`, and a variable called `reg` becomes `reg_1`, so no name can match a Verilog keyword.
- **Export:** `--export-ssa FILE` writes the equations in the input's own `dst = a op b` format, in the original order, under a comment header that lists the inputs and outputs. The exported file is therefore a valid input file:
  ```
  # inputs: A_0 B_0
  # outputs: X_2 Y_1
  X_1 = A_0 + B_0
  X_2 = X_1 * 2
  Y_1 = X_2 - A_0
  ```
