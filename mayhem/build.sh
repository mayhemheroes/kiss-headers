#!/usr/bin/env bash
#
# mayhem/build.sh — build the kiss-headers Atheris fuzz harness + its standalone reproducer,
# and prepare the project's own pytest suite. Runs inside the commit image (mayhem/Dockerfile)
# as `mayhem` in /mayhem. Python adaptation of the C/C++ template.
#
# What it does (must be idempotent + air-gapped on re-run — SPEC §6.2 item 9 / §6.5):
#   1. Populate / reuse an in-image wheelhouse under /opt/toolchains/python (HOME-independent),
#      then install atheris + pytest OFFLINE from that wheelhouse into a fixed site dir on
#      PYTHONPATH. The first (online) build fills the wheelhouse; the air-gapped PATCH re-run
#      resolves entirely from it (pip --no-index --find-links). kiss_headers itself stays the
#      editable source tree ($SRC/src on PYTHONPATH) so PATCH edits take effect immediately.
#   2. Compile launcher.c -> the ELF Mayhem target `parse-fuzz` (Atheris is a Python script;
#      Mayhem needs an ELF cmd, and the gate needs DWARF < 4 — hence a compiled wrapper).
#   3. Build the same launcher as the standalone (run-once) reproducer `parse-fuzz-standalone`.
#   4. Compile the run_tests ELF wrapper the pytest oracle (test.sh) runs through.
set -euo pipefail

[ -n "${SOURCE_DATE_EPOCH:-}" ] || unset SOURCE_DATE_EPOCH

# The base image exports the build contract (CC, SANITIZER_FLAGS, DEBUG_FLAGS, ...). The launcher
# is a thin C exec wrapper — Atheris instruments the fuzzed *Python* at import time — but we still
# honor $SANITIZER_FLAGS on it (default ASan+UBSan halting; --build-arg SANITIZER_FLAGS= for none).
[ "${SANITIZER_FLAGS+set}" = set ] || SANITIZER_FLAGS="-fsanitize=address,undefined -fno-sanitize-recover=all"
: "${DEBUG_FLAGS:=-g -gdwarf-3}"
: "${CC:=clang}"
: "${MAYHEM_JOBS:=$(nproc)}"
export DEBUG_FLAGS CC MAYHEM_JOBS

SRC="${SRC:-/mayhem}"
cd "$SRC"

# ── Python toolchain caches at a FIXED, $HOME-independent prefix (SPEC §6.2 item 8) ──
PY_PREFIX=/opt/toolchains/python
WHEELHOUSE="$PY_PREFIX/wheelhouse"
SITE="$PY_PREFIX/site"
mkdir -p "$WHEELHOUSE" "$SITE"

PY="$(command -v python3)"

# 1) Wheelhouse: download every runtime/test dependency ONCE (online). On the air-gapped re-run
#    the directory is already populated, so pip never reaches the network. atheris ships a prebuilt
#    manylinux wheel for this CPython; pytest runs the project's suite; requests is imported by
#    tests/test_serializer.py at collection time (its offline tests still run).
PKGS=(atheris pytest requests)
need_download=0
"$PY" -c "import os,glob,sys; sys.exit(0 if glob.glob(os.path.join('$WHEELHOUSE','atheris-*.whl')) else 1)" || need_download=1
if [ "$need_download" -eq 1 ]; then
  echo ">> populating wheelhouse (online) at $WHEELHOUSE"
  "$PY" -m pip download --dest "$WHEELHOUSE" "${PKGS[@]}"
else
  echo ">> wheelhouse already populated — reusing $WHEELHOUSE (air-gapped re-run path)"
fi

# 2) Install the deps into the fixed site dir, OFFLINE from the wheelhouse. Idempotent: once the
#    site dir holds atheris+pytest we SKIP the reinstall.
if "$PY" -c "import os,glob,sys; sys.exit(0 if (glob.glob(os.path.join('$SITE','atheris*')) and glob.glob(os.path.join('$SITE','pytest*'))) else 1)"; then
  echo ">> deps already installed in $SITE — skipping (idempotent re-run)"
else
  echo ">> installing deps (offline) into $SITE"
  "$PY" -m pip install --no-index --find-links="$WHEELHOUSE" --target "$SITE" "${PKGS[@]}"
fi

# kiss_headers itself: keep it as the editable source tree ($SRC/src on PYTHONPATH) so a PATCH
# agent's edits under src/kiss_headers take effect with no reinstall.
PYRUN="$SITE:$SRC/src"

# Record the site dir + interpreter for test.sh / the launcher to consume.
cat > "$PY_PREFIX/env.sh" <<EOF
export PYTHONPATH="$PYRUN\${PYTHONPATH:+:\$PYTHONPATH}"
export PYTHON_BIN="$PY"
EOF

# Sanity: the harness imports must resolve offline now.
PYTHONPATH="$PYRUN" "$PY" -c 'import atheris, kiss_headers, pytest; print("imports OK:", kiss_headers.__version__)'

# 3) Compile the ELF launcher target + the standalone reproducer (DWARF < 4 via $DEBUG_FLAGS).
HARNESS="$SRC/mayhem/fuzz_parser.py"
echo ">> compiling parse-fuzz (+ standalone) with DEBUG_FLAGS=$DEBUG_FLAGS"
$CC $DEBUG_FLAGS $SANITIZER_FLAGS -DPYTHON="\"$PY\"" -DHARNESS="\"$HARNESS\"" \
    "$SRC/mayhem/launcher.c" -o "$SRC/parse-fuzz"
# The standalone reproducer is the same launcher: libFuzzer runs a single input file once when
# given a file path (no fuzzing loop) — exactly the run-once reproducer contract.
$CC $DEBUG_FLAGS $SANITIZER_FLAGS -DPYTHON="\"$PY\"" -DHARNESS="\"$HARNESS\"" \
    "$SRC/mayhem/launcher.c" -o "$SRC/parse-fuzz-standalone"

# 4) The pytest oracle runs through a compiled NON-system ELF wrapper so the gate's anti-reward-hack
#    sabotage check (which neuters non-system binaries to exit(0)) actually bites the suite.
$CC $DEBUG_FLAGS -DPYTHON="\"$PY\"" "$SRC/mayhem/run_tests.c" -o "$SRC/kiss_headers_run_tests"

echo ">> build.sh complete"
ls -la "$SRC/parse-fuzz" "$SRC/parse-fuzz-standalone" "$SRC/kiss_headers_run_tests"
