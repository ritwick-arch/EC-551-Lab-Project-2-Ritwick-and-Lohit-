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
- **Names:** an ASCII letter first, then any mix of ASCII letters, digits and `_`. Names are case-sensitive.
- **Operands:** a name, or a non-negative whole number that fits the datapath width (e.g. `Y = X * 3`).
- **Skipped:** blank lines and `#` comments. One trailing `;` is accepted (amended 11/6).
- **File encoding (amended 11/6):**
  - UTF-8 with or without a BOM, or UTF-16 with a BOM, which is what `echo ... > file` writes in Windows PowerShell 5.1.
  - Any line endings are accepted.
  - Any other file that isn't valid UTF-8 is an error that names the line and the bad byte.
- **Errors:** the message names the line and nothing is generated. An error is raised for:
  - any other line shape: `X = A + B + C`, parentheses, `/`, `X = -A`, `X = A`, `3 = A + B`
  - an empty file
  - more than 20 equations
- An error names any non-ASCII character in the line by its code point (amended 11/6). For example, U+2212 is a Unicode minus pasted from Word that looks like `-`.
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
- `--schedule calap`: the same list scheduler run backward, then flipped. The backward pass starts from every op whose result nothing reads, including overwritten values B keeps, not only from outputs. It places the op with the largest ASAP time first, which is the backward form of critical-path-first. Measured on random programs, that makes it longer than `casap` in under 1% of cases, compared with about a third for reverse equation order. With `--latency L` the schedule is shifted to end at step L. It's an error if the limits can't fit in L. (Amended 11/6.)
- `--schedule custom`: **still open**. The options:
  - (1) Fewest units for a target latency. The list scheduler inside it starts the op with the earliest ALAP time first. Measured, it uses fewer units than ASAP in 35% of 4–8-op programs and 71% of 4–20-op programs, and never more.
  - (2) Critical-path-first list scheduling under the limits. Measured, it gives the same result as `casap` about 88% of the time, and with no limits it is exactly ASAP.
- Limits must be at least 1, even for a type the program doesn't use. A valid limit for a type the program doesn't use is ignored.
- **Flags per mode (amended 11/6):**
  - `asap` takes no limit or latency flags.
  - `alap` takes `--latency`.
  - `casap` takes the limits.
  - `calap` takes the limits and `--latency`.
  - `custom` takes `--latency`.
  - A flag the chosen mode doesn't use is an error, never silently ignored, e.g. `error: --mul is only used by casap and calap`.
- Every run prints the DAG (each op and the ops it depends on), the step-by-step schedule, the latency and the number of units of each type.

### F. Datapath (decided 11/6)

- **Units:** the count for each type is the most ops of that type running at once in any step. A multi-step op counts in every step it holds.
- **Binding:** ops are taken in start order. Each goes on the lowest-numbered unit of its type that's free for all of its steps (left-edge), so no more units are needed than the count above.
- **Registers:** one per value, never shared.
  - **Op results:** each result register is written in its op's last step, straight from its unit's output. It needs a write-enable from the FSM and no input mux.
  - **Switch inputs:** they follow the switches while the FSM is idle and freeze once stepping starts.
  - **Constants and hardcoded inputs:** plain Verilog constants, with no register.
  - **Reset:** every register clears on reset.
- **Muxes:** each unit input (left and right) gets a mux over the registers and constants that port reads anywhere in the schedule, and the FSM sets its select each step. A port with only one source is a plain wire. Operands are never swapped.
- Example: the spec example under ASAP with 1-cycle ops. add0 runs X in step 1 and Y in step 2, sub0 runs Z in step 2, and mul0 runs Q in step 3. add0's muxes are {A, X} on the left and {B, A} on the right. sub0 and mul0 have plain wires. The registers are A, B, X, Y, Z and Q.

### G. FSM / sequencer (decided 11/6)

- **States:** 0 = IDLE, 1…L = the schedule's steps, L+1 = DONE. The schedule is a straight line, so the state register is a counter. L is capped at 254 so the state fits in 2 hex digits.
- **Transitions:**
  - Each step pulse moves forward one state.
  - The first press leaves IDLE and freezes the inputs. L more presses run the steps, so a run takes L+1 presses.
  - A press in DONE does nothing.
  - Reset returns to IDLE and clears every register.
- **Outputs:** Moore-style. A `case (state)` drives named signals: each unit's mux selects (`<unit>_sel_a`/`_sel_b`), each register's write-enable (`<value>_we`), and a `<unit>_busy` flag that is 1 in steps where the unit holds an op. Only these signals drive the muxes and registers. H describes how the display uses `busy`.
- **Naming rule (amended 11/6):** every generated helper name ends in a letter suffix (`X_1_we`, `add0_sel_a`, `add0_busy`). SSA names always end in `_<digits>`, so the two can never collide. Prefix names like `we_X_1` could collide, for example with a user variable named `we_X`.
- **Multi-step ops:** the selects are held for all of the op's steps, and the write-enable is asserted only in the last one (D).
- **Clocking:** everything runs on the 100 MHz clock and changes only while the one-cycle step pulse is high. How the button produces that pulse is decided in H.

### H. Board I/O (decided 11/6)

- **Width:** 16-bit unsigned datapath.
  - Each switch input is one hex digit (4 bits, zero-extended).
  - Constants and `--set` values are 0–65535; anything larger is an error.
  - Results wrap mod 2^16. A final result that fits in 16 bits is still exact even if an intermediate step overflowed or went negative.
  - There is no overflow warning.
- **Switches:**
  - SW15–12 pick the observe code within the current page.
  - SW11–8, SW7–4 and SW3–0 are input slots 1–3, filled in the order the inputs first appear.
  - SW8 and SW9 are LVCMOS18.
- **Extra inputs:**
  - More inputs than slots is an error that names them, unless the extras are hardcoded with `--set NAME=VALUE`. That also frees their slots.
  - `--set` on a name that isn't an input is an error, and so is a duplicate `--set`.
  - This check only runs when generating Verilog. The tool prints the board map.
- **Buttons:**
  - BTNC = step, BTNU = next observe page (wraps around, cleared on reset), CPU_RESETN = reset.
  - In `top.v`, BTNC and BTNU are synchronized, debounced (sampled every ~10 ms) and edge-detected into one-cycle pulses.
  - BTNC is never used as a clock: its pin isn't clock-capable and the button bounces.
  - There is no free-running mode.
- **Reset:**
  - CPU_RESETN is synchronized and applied as a synchronous reset: back to IDLE, results cleared, page 0.
  - Power-up starts in the same state.
  - Inputs follow the switches in IDLE and freeze on the first press (F, G).
- **Observe codes:**
  - Code = 16 × page + SW15–12.
  - Order: every unit (adders, then subtractors, then multipliers, by index), then every result register in equation order with outputs marked, then the switch inputs.
  - At most 44 codes, so the code is 6 bits. The tool prints the code table in the same 2-digit hex.
- **Display (hex):**
  - Format `SS.CC.VVVV`: state (00 = IDLE, 01…L = steps, L+1 = DONE), observe code, then value, with decimal points between the fields.
  - LED0 lights in DONE.
- **Dashes:** the value shows `----` for a unit with no op in the current step, a register that hasn't been written yet, or a code past the end of the table.
- **What a unit shows:** in step k, a unit shows the result it's computing. That result is written to its register on the next press.

### I. Command line, files, repo layout (decided 11/6)

- **Command:** one-shot.
  ```
  python -m hls FILE [--schedule asap|alap|casap|calap|custom]
         [--add N --sub N --mul N] [--latency L] [--add-cycles N --sub-cycles N --mul-cycles N]
         [--set NAME=VALUE ...] [--eval NAME=VALUE ...] [--export-ssa FILE] [--out DIR]
  ```
  The default mode is `asap`.
- **Every run prints** (ASCII only):
  - the board map: which input is on which switch slot, plus the `--set` values
  - the SSA
  - the DAG table
  - the schedule grid, with one row per step and one column per unit
  - the unit counts, the latency and the number of presses
  - the observe-code table
- **`--out DIR`** writes `hls_core.v`, `testbench.v` and `schedule.txt` under these fixed names.
- **`--eval NAME=VALUE ...`** prints the expected value of every register, and of each unit in each step, in hex (as the board shows it) and in decimal. It evaluates the same equations as the testbench's reference, and pytest cross-checks the two.
- **Flag values:** mode names are case-insensitive (`--schedule ASAP` works). `--set` and `--eval` values are decimal.
- **Errors:** one `error: ...` line, exit code 1, nothing written, no traceback.
- **Output files:** written with UTF-8 and `\n` line endings, and with no timestamps, so a rerun produces byte-identical files on any machine.
- **Layout:**
  - `hls/`: the Python package
  - `rtl/`: `adder.v`, `subtractor.v`, `multiplier.v`, and `top.v` with the debounce and 7-seg logic
  - `constraints/nexys_a7.xdc`: written fresh, because the uploaded master has the prelab names active and the clock commented out
  - `examples/`: each example with its generated output (SSA, `schedule.txt`, `hls_core.v`, `testbench.v`, sim log) committed, since the spec asks for generated artifacts
  - `tests/`
  - `build/`: one folder per live run (L), git-ignored
- **Generated module (port list frozen 11/6):** always `hls_core` in `hls_core.v`, with this port list, so `top.v` and the XDC never change:
  ```verilog
  module hls_core(input clk, rst, step, input [11:0] sw,   // 3 switch slots
                  input [5:0] code,                         // {page, SW15-12}
                  output [15:0] value, output valid,        // valid = 0 shows ----
                  output [7:0] state, output done);
  ```
  - The core takes all of SW11–0, so the testbench can loop over all 4096 switch values.
  - `top.v` holds the BTNU page counter. It is 2 bits wide, so the page wraps from 3 back to 0.

### J. Verification (decided 11/6)

- **pytest, Python side:**
  - Parser accept/reject cases, SSA and DAG.
  - Scheduler property checks on thousands of random programs:
    - every dependency is respected
    - unit limits and the latency bound hold
    - every op is scheduled exactly once
    - `casap` with no limits equals `asap`, and `calap` with no limits equals `alap`
    - `custom` never uses more units than ASAP
    - the error cases fire
- **Generated Verilog on SCC:** each example's `hls_core.v` and the fixed RTL get Verilator lint (`-Wall`) and a Yosys synthesis check, which catches accidental latches.
- **`testbench.v`, generated per design:**
  - **DUT:** `hls_core`, with `step` pulsed directly. `top.v` is not simulated, because its debouncer makes each press about a million cycles.
  - **Reference:** the SSA equations written directly in the testbench, one Verilog line each and masked to 16 bits, with no schedule, binding or FSM involved.
  - **Inputs:** every switch setting, at most 16³ = 4096.
  - **Each run:** reset, set the switches, press L+1 times, check `done`, then read every register through the observe port and compare.
  - **Output:** the first few mismatches, then a final `PASS n/n` or `FAIL` line. It runs in Icarus on SCC (`module load yosys/0.48` provides Icarus 12.0) and in Vivado xsim.
- **End-to-end on SCC:** pytest generates designs for the examples and for random programs (all 5 modes, 1- and 2-cycle multiply), simulates each `testbench.v` with Icarus and expects PASS. It also cross-checks the Python model behind `--eval`.
- **Examples (`examples/`):**
  - the spec example
  - a file where all 5 schedules differ
  - reassignment, including a reassigned input
  - `A = A + A`
  - a constant-only op
  - 20 equations
  - more than 16 codes (paging)
  - overflow and negative results
  - a file with errors
- **Board:** an early smoke test with the spec example, to check the debounce, the 7-seg display and the XDC.

### K. Front end to scheduler hand-off (decided 11/6)

```python
@dataclass(frozen=True)
class Op:
    index: int      # 0-based, in line order
    dst: str        # SSA name, e.g. 'Y_2'
    kind: str       # 'add' | 'sub' | 'mul'
    a: str | int    # SSA name or constant
    b: str | int
    line: int       # line number in the input file

@dataclass
class DAG:
    ops: list[Op]             # line order
    preds: list[list[int]]    # ops each op reads (deduplicated)
    succs: list[list[int]]    # ops that read each op

def schedule(dag, mode, limits=None, latency=None, cycles=None) -> list[int]:
    """Start step (1-based) of each op; raises ValueError with a user-facing message."""
```

- **Arguments:**
  - `limits`: e.g. `{'mul': 1}`. A missing type is unlimited.
  - `cycles`: e.g. `{'add': 1, 'sub': 1, 'mul': 2}`.
- **What `schedule()` returns:**
  - Start steps only.
  - The generator works out latency, unit counts and binding (F).
  - The generator checks the schedule (dependencies, limits, bound) before it writes any Verilog.
- **Determinism:**
  - Everything is a list in line order.
  - Ties are broken by line.
  - Nothing iterates over a set, because set order changes between runs.
- **Who builds what:**
  - Lohit: `Op`/`DAG` (parser → SSA → DAG) and the generator.
  - Ritwick: `schedule()` and J's property tests, which need only random DAGs.
  - A stub module with these signatures is committed first, so both sides can start in parallel.
- **Suggested for Ritwick (his call):** build all five modes on one `place(order, limits, cycles)` helper.
  - It puts each op at the first step where its inputs are done and a unit of its type is free for all N steps.
  - The backward modes run it on the reversed DAG and mirror the result.

### L. Build flow and demo machine (decided 11/6)

- **Demo machine:** Lohit's ThinkPad, which has Python, Vivado 2025.1 and the board together.
  - The repo lives outside OneDrive (e.g. `C:/Users/daksh/ec551/`), because OneDrive locks Vivado's run files.
  - Still to confirm: Python 3.10+ on the laptop (the `str | int` hints in K need it), and where the board is for the first smoke test.
- **One folder per run (amended 11/6):** each run writes to its own folder (`--out build/run1`, then `build/run2`, …). Each script below takes that folder as its argument, so a later run can't overwrite an earlier run's files.
- **Build:** `vivado -mode batch -source scripts/build.tcl -tclargs build/run1`.
  - It reads the fixed RTL, the folder's `hls_core.v` and the XDC, runs synthesis and place-and-route, and writes the bitstream into the folder.
  - It doesn't program the board, so a build running in the background can't reprogram the board in the middle of the professor's check.
  - There is no project file, so the Vivado version doesn't matter (2025.1 on the laptop, 2024.1 in the lab).
- **Program:** `vivado -mode batch -source scripts/program.tcl -tclargs build/run1` loads that folder's bitstream onto the board.
  - It runs `catch {set_param labtools.enable_cs_server false}` before `open_hw_manager`.
  - The `catch` keeps the script working on a Vivado version that lacks that setting. We haven't checked 2024.1.
- **Live simulation:** `scripts/sim build/run1` runs `xvlog/xelab/xsim` on the folder's `testbench.v` from the command line. SCC uses Icarus instead.
- **Build time:** unmeasured. We'll measure it at the first board test; the demo plan covers the software walkthrough while a build runs.
- **Fallback:** pre-built bitstreams of two prepared examples, kept on the laptop.
