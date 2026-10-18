# Bend for provable invariants

Bend is the default for a new component whose value lies in invariants that can be proved, simulation and state-transition logic above all. Its own law-and-proof workflow is the method. Before choosing it for a component, confirm that the current release is ready and that it integrates with the surrounding code. The preference covers components that fit; it does not ask for existing projects to be migrated.

## Native workflow

The component itself is written in Bend, and the properties that matter are stated as laws with proofs the compiler checks. Start with `bend guide` for the release in use, keep the invariants in `LAWS.bend`, and make `bend PROOF.bend` pass before a commit. The release's own tooling is enough; a home-grown verification layer beside it is a smell.

The owner chooses the requirements. Include successful behavior alongside prohibitions: valid funded transfers must complete, not merely avoid invalid transfers. Changing the requirements is an explicit owner decision, not a way to make a failed proof pass.

Check the boundary to surrounding code. A proof of Bend simulation rules does not automatically verify an API, database, authentication layer, another-language implementation, or the realism of the simulation. Establish what the selected compiler and integration actually preserve.

## GPU work on rented Linux machines

Checked against the Bend 2.0.4 guide and compiler on 2026-09-17, not rechecked under 2.0.32; recheck `bend guide` and the selected release before provisioning. GPU execution has not yet been tested here.

- Use an NVIDIA machine with a working driver and CUDA 12 development toolkit, plus Bun and Clang 19+. A runtime-only CUDA image is insufficient. This release looks specifically for `/usr/local/cuda/include/nvrtc.h`, includes `/usr/local/cuda/include`, and links from `/usr/local/cuda/lib64` against `cuda` and `nvrtc`. Missing that header makes the compiler build the CPU path even for `!` calls.
- Install Bend on the remote machine; the laptop installation does not propagate. Confirm `bend --version`, `clang --version`, `nvidia-smi`, the header, and linkable CUDA/NVRTC libraries before a workload. Native builds compile the GPU program on that machine, so build where the GPU is available.
- Write balanced independent parallel calls and use `f!(...)` for the GPU entry point. Compile with `bend program.bend -o program`; plain `bend program.bend` uses the sequential JS backend for IO programs. Keep the generated `program.gpu` beside the binary. Run `./program --gpu 4GB`, choosing the memory budget for the device and workload.
- Before spending on a long run, compare the same native program with `--gpu off` and GPU enabled, verify matching results and actual GPU activity, and measure the representative workload. Successful output alone does not establish GPU execution or speedup. Uniform numeric work suits the GPU; divergent or unbalanced work may favor the CPU.
- The older launcher pilot had automatic updates coupled to telemetry (approved 2026-09-17). Record the Bend release and toolchain for reproducible experiments. On current 2.0.36, updates require `bend update` or the installer; do not assume an invocation upgraded the compiler.
- Renting still requires approval for external spend. Follow the chosen provider's operations reference, retain the instance handle, preserve artifacts, and observe the existing teardown/PULL_DONE rules. Include this brief in remote/delegate instructions: a fresh remote agent does not automatically inherit laptop configuration.

## Installation and pilot evidence

Bend 2.0.36 installed on 2026-10-08 at `<bend-root>` (`bin/bend` is one binary; `bend2/` holds Base and the Lean kernel source), exposed through `<user-bin>/bend`; the previous 2.0.32 installation is retained at `<bend-rollback-root>` for rollback, on the laptop and on the VPS. The release never updates itself: `bend update` or the installer does, and the installer removes `<bend-root>/app`. OptMem migrated to 2.0.32 on 2026-09-28 and retains hash-checked executable, Base and BendTT snapshots independently of the global installation. Its build checks proofs and the Lean-backed verdict before native compilation and activation; current contract and lifecycle: `<optmem-root>/BEND_SELECTION.md`. The old 2.0.4 copies are retained comparison artifacts, no longer a runtime dependency. `bend version` replaces `--version`; the gate prints ALL PROOFS CHECK or SOME PROOFS FAIL and exits 0 or 1. `bend PROOF.bend --verdict` rechecks with the kernel that has a Lean proof; it needs Lean 4.34.0, installed through elan at `<elan-root>` and kept off the shell PATH, so prefix `PATH="<elan-root>/bin:$PATH"`. The first run builds the kernel (23 s), later runs take under a second. Base has `Nat`, `U32` and `F32` only, TCP/UDP/File/Process effects, no HTTP, JSON or Unix sockets.

`<proof-lab-root>/` is a learning experiment: a two-account natural-number transfer model with four universal Bend laws covering conservation, authorization, exact funded transfers, and atomic underfunded rejection. The experiments include broken candidates and a lawful implementation change with repaired proofs.

The pilot uses a hash-pinned September 2026 browser checker. It is not a native Bend distribution or an independently verified kernel. Its custom runner remains experimental evidence, not a house platform to extend or a required dependency for future projects. The upstream preview bundle stays ignored under `.local/`; check the current upstream license before reuse or distribution.

Read the pilot README for reproduction. Recheck upstream availability when starting a real project rather than assuming the preview’s limitations still apply.
