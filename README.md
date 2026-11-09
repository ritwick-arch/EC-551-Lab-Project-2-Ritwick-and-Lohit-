# EC551 Program 2: Hardware Synthesis

Ritwick & Lohit, EC551 Fall 2026.

`hls` is a small high-level synthesis tool in Python. It reads up to 20 equations of the form `dst = a op b` with `+`, `-` or `*`. It turns them into SSA and a dependency DAG, schedules them with one of five schedulers, and writes a datapath and FSM in Verilog. That Verilog runs on a Nexys A7: a button steps the FSM one control step at a time, the switches set the inputs and pick what to show, and the 7-segment display shows the state, the observe code and the value.

The decisions behind every part are in [PLAN.md](PLAN.md), sections A–N.

## Quick start

On the demo laptop (Windows PowerShell, Python 3.10 or newer, and Vivado's `bin` folder on the PATH, e.g. `C:\Xilinx\2025.1\Vivado\bin`):

```powershell
mkdir build                                                              # once
notepad build\run1.txt                                                   # write the equations
python -m hls build\run1.txt --schedule casap --mul 1 --out build\run1   # compile
vivado -mode batch -source scripts/build.tcl   -tclargs build/run1       # bitstream, about 2 min
vivado -mode batch -source scripts/sim.tcl     -tclargs build/run1       # testbench in xsim
vivado -mode batch -source scripts/program.tcl -tclargs build/run1       # load the board
python -m hls build\run1.txt --schedule casap --mul 1 --eval A=3 B=4     # values the board should show
```

Each run gets its own folder, so a later run never overwrites an earlier run's files. The build doesn't program the board, so it can run in the background while the previous run is being checked on the board.

On SCC, for the tests: `module load yosys/0.48` (it provides Icarus Verilog and Yosys), then `python3 -m pytest`. The lint test also needs `VERILATOR` set to a Verilator binary. Tests whose tools are missing are skipped.

## Input format

```
# comments and blank lines are skipped; one trailing ';' is allowed
X = A + B
Y = X * 3
X = Y - A        # reassignment is fine: SSA gives every value its own name
```

- One equation per line: `dst = a op b`, where `op` is `+`, `-` or `*`, and each operand is a name or a whole number 0–65535.
- Names start with a letter, then letters, digits or `_`. They are case-sensitive.
- The datapath is 16 bits unsigned. Results wrap mod 2^16, so `A - B` with `A < B` shows the two's-complement bit pattern.
- Inputs are the names read before they are assigned. The first three, in order of first appearance, go on the switches as one hex digit each: SW11–8, SW7–4, SW3–0. Any further input must be hardcoded with `--set NAME=VALUE`.
- At most 20 equations. A bad line is an error that names the line, and nothing is written.
- Files may be UTF-8 (with or without a BOM) or UTF-16 with a BOM, which is what PowerShell 5.1's `>` writes. Any line endings work.

## Command line

```
python -m hls FILE [--schedule asap|alap|casap|calap|custom]
       [--add N --sub N --mul N] [--latency L] [--add-cycles N --sub-cycles N --mul-cycles N]
       [--set NAME=VALUE ...] [--eval NAME=VALUE ...] [--export-ssa FILE] [--out DIR]
```

| Flag | Meaning |
|---|---|
| `--schedule` | Scheduling mode, default `asap`. Case doesn't matter. |
| `--add/--sub/--mul N` | The most units of that type in use at once (`casap`, `calap`). A type with no limit is unlimited. |
| `--latency L` | The step the schedule must end by (`alap`, `calap`, `custom`). It defaults to the ASAP length. |
| `--add/sub/mul-cycles N` | Steps each op of that type takes, 1–254 (default 1). Units aren't pipelined: an op holds its unit for all N steps. |
| `--set NAME=VALUE` | Hardcode an input as a constant, which frees its switch slot. |
| `--eval NAME=VALUE ...` | Print what the board should show for these switch values: every register at DONE, and every unit in every step. |
| `--export-ssa FILE` | Write the SSA form. It is itself a valid input file. |
| `--out DIR` | Write `hls_core.v`, `testbench.v` and `schedule.txt` into DIR. |

A flag the chosen mode doesn't use is an error, not silently ignored. Every error is one `error: ...` line with exit code 1.

Every run prints:
- the inputs and outputs
- the board map
- the SSA
- the DAG
- the schedule grid (one row per step, one column per unit), the latency, the presses to DONE and the unit counts
- the observe-code table

`schedule.txt` holds the same report under a header line with the exact command. The output files have no timestamps, so rerunning a command produces the same bytes.

## Architecture

```
equations ──parser──▶ SSA ──▶ DAG ──schedule()──▶ start steps ──check──▶ binding ──▶ hls_core.v
                                                                            │        testbench.v
                                                                            └──────▶ schedule.txt, --eval
```

| Module | What it does |
|---|---|
| `hls/parser.py` | Reads and checks the equation file (PLAN B). |
| `hls/ssa.py` | Renames every value to `NAME_k`, with inputs as `NAME_0`, and writes `--export-ssa` (C). |
| `hls/dag.py` | Builds the dependency DAG: an edge from each op to every op that reads its result. |
| `hls/schedule.py` | The five schedulers (E). They return each op's start step. |
| `hls/check.py` | Checks every schedule before any Verilog is written: dependencies, unit limits, the latency bound, and at most 254 steps (K). |
| `hls/datapath.py` | Binds ops to units, places the inputs on the switch slots, lists the observe codes, and holds the `--eval` model (F, H). |
| `hls/verilog.py` | Writes `hls_core.v` and `testbench.v` (F, G, J). |
| `hls/report.py`, `hls/cli.py` | The printed report and the command line (I). |

### Timing model

One control step is one FSM state, and one press of BTNC. During step *k* the units compute that step's ops from registers, and the press that ends the step writes the results. An op starts only after every input has been written. An op of a type with `--X-cycles N` holds its unit, and its mux selects, for N steps, and its result register is written at the end of the last one.

### Schedulers

| Mode | How it places ops |
|---|---|
| `asap` | Each op starts as soon as its inputs are ready, with unlimited units. |
| `alap` | Each op starts as late as it can while the program still ends by step L. |
| `casap` | List scheduling forward, step by step. It starts ready ops in equation order while a unit of their type is free. |
| `calap` | The same list scheduler run backward from the end, then flipped. It places the op with the largest ASAP time first, which is the backward form of critical-path-first. With `--latency L` the schedule is shifted to end at step L. |
| `custom` | The fewest units that still finish by step L. It tries unit budgets in order (fewest in total, then fewest multipliers, then fewest adders), and for each budget runs `casap` and then `calap`. It returns the first schedule that ends by L, and prints which mode found it. So it never needs more units than another mode at the same latency. |

Ties always go to the equation written first, so every run gives the same schedule.

### Datapath

- **Units:** the number of each type is the most ops of that type running in any one step. They are instances of `rtl/adder.v`, `rtl/subtractor.v` and `rtl/multiplier.v`, which are combinational and 16 bits wide.
- **Binding:** ops are taken in start order, and each goes on the lowest-numbered unit of its type that is free for all of its steps (left-edge). This never needs more units than the count above.
- **Registers:** one 16-bit register per SSA value, written once. Switch inputs follow the switches while the FSM is idle and freeze at the first press. Constants and `--set` inputs are plain Verilog constants.
- **Muxes:** each unit input gets a mux over the registers and constants it reads anywhere in the schedule, and the FSM sets its select in each step. An input with only one source is a plain wire.

### FSM

The state is a counter: 0 = IDLE, 1…L = the steps, L+1 = DONE. Each step pulse moves it forward one state, and a press in DONE does nothing. A Moore `case (state)` drives every mux select (`add0_sel_a`), every register write-enable (`X_1_we`) and every unit's busy flag (`add0_busy`). Every helper name ends in a letter, while SSA names end in `_<digits>`, so the two can never collide.

### Board

| Board | Use |
|---|---|
| SW11–8, SW7–4, SW3–0 | Input slots 1–3, one hex digit each. Read while the state is 00, frozen at the first BTNC press. |
| SW15–12 and BTNU | The observe code is 16 × page + SW15–12. BTNU steps the page (0–3, wrapping). |
| BTNC | Step. It is synchronized, debounced (sampled every 10 ms) and edge-detected into a one-cycle enable. It never drives a clock. |
| CPU_RESETN | Reset: back to IDLE, registers cleared, page 0. |
| 7-segment | `SS.CC.VVVV`: state, observe code, value, all in hex. `----` means nothing is valid there: a unit idle this step, a register not written yet, or a code past the table. |
| LED0 | Lit in DONE. |

The observe codes run through every unit (adders, subtractors, then multipliers), then every result register in equation order, then the switch inputs. A unit shows the result it is computing in the current step, which is written to its register on the next press.

## Repo layout

```
hls/                    the tool (Python standard library only)
rtl/                    fixed Verilog: adder, subtractor, multiplier, debounce, sevenseg, top
constraints/            nexys_a7.xdc
scripts/                build.tcl, program.tcl, sim.tcl (Vivado batch); make_examples.py
examples/<name>/        an input file, its SSA, and one folder per run with
                        schedule.txt, hls_core.v, testbench.v and the Icarus sim.log
tests/                  pytest: parser, SSA, DAG, schedulers, generator, end to end
PLAN.md                 the design decisions
build/                  live demo runs (git-ignored)
```

| Example | Shows |
|---|---|
| `spec` | The assignment's example, ASAP. |
| `five` | A program where all five schedules differ, with one folder per mode. We build these on the laptop as the fallback for each mode. |
| `reassign` | A reassigned variable, a reassigned input, and `A = A + A`, with a 2-step multiply. |
| `constant` | A constant-only op and one input. Under `alap --latency 4`, step 1 is idle. |
| `twenty` | 20 equations, observe codes past one page, and `--set` for a fourth input. |
| `overflow` | Results that wrap past 65535 or below 0. |
| `errors` | A bad line and the error it gives. |

`python scripts/make_examples.py` regenerates all of them, and a test fails if the committed files are stale.

## Verification

- **Python (`pytest`):**
  - accept and reject cases for the parser, SSA and DAG
  - scheduler property checks on random programs (dependencies, limits, latency bounds, `casap` = `asap` and `calap` = `alap` with no limits)
  - binding never uses more units than the schedule needs
  - error cases, `--eval`, and byte-identical reruns
- **Generated testbench:** `testbench.v` drives `hls_core` with all 4096 switch settings. For each one it resets, sets the switches, presses L+1 times (changing the switches after the first press, which must be ignored), and checks `done`. Then it reads every observe code and compares it with the equations written out directly in Verilog, with no schedule involved. It prints `PASS 4096/4096`.
- **End to end on SCC:** every example in all five modes, with 1- and 2-step multiply, plus random programs, generated and simulated in Icarus. A trace bench also checks every observe code in every state against the `--eval` model. Verilator `-Wall` lint and a Yosys latch check run on every committed core.
- **Vivado (laptop, measured 11/9):**
  - The spec example builds in 77 s, with timing met at 100 MHz (WNS +2.07 ns).
  - The 20-equation example (`twenty`, casap) builds in 134 s and uses 433 LUTs, 418 flip-flops and 2 DSPs. Its testbench passes in xsim in 14 s.
  - Vivado reports that `twenty` misses 100 MHz by 1.3 ns, so its build prints a timing warning. The worst path runs from the FSM through a multiplier and the observe mux into the 7-segment display register. Every path through the core starts at a register that changes only on a press, and results are only written on a press, so at worst the display is wrong for one 10 ns clock after a press.

## Demo plan (30 minutes)

The professor writes the equations, picks the mode and limits, and directs three runs. The runs overlap: each run's build starts as soon as it compiles, and we explain that run while it builds.

**Every run follows the same steps:**
1. The professor writes the equations in Notepad as `build\runN.txt`. Before run 1 they get the rules from [Input format](#input-format).
2. We compile with the professor's mode and limits: `python -m hls build\runN.txt --schedule ... --out build\runN`.
3. We start the build and the simulation in a second window.
4. While it builds, we walk through the printed report and `hls_core.v`, then show the testbench's `PASS 4096/4096`.
5. We program the board. The professor picks switch values, and `--eval` with the same flags prints what the board should show.
6. The professor steps with BTNC, switching the observe code between units, and checks every output at DONE.

| min | who | what |
|---|---|---|
| 0–2 | Ritwick | The architecture in one picture, and why BTNC is a clock enable rather than a clock. The professor writes run 1. |
| 2–8 | Lohit | Run 1: compile, start the build and sim. Then the SSA, the DAG, all five schedules for these equations, `hls_core.v`, PASS. Ask for run 2. |
| 8–9 | Lohit | Compile run 2 and start its build. |
| 9–13 | Ritwick | Run 1 on the board. |
| 13–14 | Lohit | Run 2's output: what the new limits changed. The professor writes run 3. |
| 14–18 | Ritwick | Run 2 on the board, while Lohit starts run 3's build. |
| 18–23 | both | Run 3's output, then run 3 on the board. |
| 23–30 | both | Buffer: the professor's questions, a bad line to show an error message, or a fallback. |

**Where each part of the assignment is shown:**
- Parse errors: one deliberately bad line.
- SSA, `--export-ssa`, the DAG and all five schedulers: run 1. The other four schedules are printed by rerunning the command without `--out`.
- Muxes, registers, FSM and unit counts: `hls_core.v` in run 1, then what changed in runs 2 and 3.
- Testbench, build and programming, the step button, observe select and 7-segment display: every run.

**If the professor asks for ideas:** a constrained mode with tight limits (`--schedule casap --mul 1`), then `custom` with `--latency` one step above the minimum, or `--mul-cycles 2`.

**Fallbacks:**
- The build fails or isn't done after about 8 minutes: show the run passing in simulation, continue on the board with the prebuilt bitstream of the same mode (`program.tcl -tclargs build/five_<mode>`, built from `examples/five/<mode>`), and return to the run when the build finishes.
- Programming fails: replug the USB and rerun `program.tcl`.
- The tool rejects the input: the error names the line, and we fix it together.

**Before the slot:** the laptop is on power with sleep off, the repo is at the submitted commit, the board shows a prebuilt example, two PowerShell windows are open in the repo, and the fallback bitstreams are built.

## Who built what

- **Lohit:** the parser, SSA and DAG; the generator (binding, Verilog, testbench, report, `--eval`); the board files and Vivado scripts; the examples and end-to-end tests.
- **Ritwick:** the five schedulers and their property tests.
