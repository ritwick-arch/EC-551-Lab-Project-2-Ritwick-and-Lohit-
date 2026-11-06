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

### D. Timing model (decided 11/6)

- **Control step:** one FSM state, which is one button press. During step *k* the units compute that step's ops from registers. On the next press the results are written and the FSM moves on.
- **Latency per op type:** each type takes N steps, set with `--add-cycles N`, `--sub-cycles N` and `--mul-cycles N` (default 1, minimum 1). The total step count has to fit the state display, and H sets that limit.
- **Unit occupancy:** a unit is busy for all N steps of its op; units aren't pipelined. An op can start only after every input has finished. Unit counts come from the most ops of a type running at once.
- **Hardware:** the units stay combinational. For a multi-step op the FSM holds the unit's input mux selects for its N steps and enables the result register's write only in the last one. Every value has its own register that's written once (F), so operands stay put while a slow op runs.
- Example with 1 multiplier and `--mul-cycles 2`: `P = A*B; Q = C*D; R = P+Q` runs P in steps 1–2, Q in 3–4 and R in 5, for a latency of 5. With 2 multipliers the latency is 3.

### E. Schedulers (decided 11/6, except custom)

- **Shared rules:** every mode uses D's timing: an op holds its unit for its N steps and can start only once all its inputs have finished. Ties go to the equation written first, so every run gives the same result.
- `--schedule asap`: each op starts as soon as its inputs are ready, with unlimited units.
- `--schedule alap`: each op starts as late as it can while the program still ends by step L. L is set with `--latency L` and defaults to the ASAP length. L shorter than the critical path is an error.
- `--schedule casap`: list scheduling. It goes step by step and starts ready ops while a unit of their type is free. Limits are set with `--add/--sub/--mul N`; a type with no limit is unlimited.
- `--schedule calap`: the same list scheduler run backward, placing the last ops first, then flipped. With `--latency L` the schedule is shifted to end at step L. It's an error if the limits can't fit in L.
- `--schedule custom`: **still open**. Either (1) fewest units for a target latency, or (2) least-slack-first list scheduling under the limits.
- Limits must be at least 1. A limit of 0 on a type the program uses is an error. `asap` and `alap` ignore the limits.
- Every run prints the DAG (each op and the ops it depends on), the step-by-step schedule, the latency and the number of units of each type.
