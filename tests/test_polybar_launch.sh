#!/usr/bin/env bash
#
# test_polybar_launch.sh
#
# Verifies the Polybar launch-path fix documented in
# docs/issues/polybar-fix/{issue.md,fix.md}.
#
# The original bug: config/polybar/launch.sh passed the config path as
# "~/.config/polybar/config.ini". A tilde inside double quotes is NOT
# expanded by the shell, so Polybar received a literal "~" and could not
# find its config. The fix expands the path (via $HOME) so Polybar gets a
# real absolute path, and routes qtile through the same script.
#
# This test asserts the *behaviour* of the fix, not one exact spelling:
#   1. launch.sh no longer contains the literal quoted-tilde pattern.
#   2. The --config argument, evaluated the way the shell would, expands to
#      an absolute path (no leading "~") that actually resolves to a file.
#   3. qtile autostarts Polybar through launch.sh with the path expanded,
#      instead of launching a bare `polybar`.
#
# Exit status: 0 if every assertion passes, 1 otherwise.
# The test is self-contained: it never launches the real Polybar and only
# reads the repo files, so it is safe to run in CI.

set -u

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

LAUNCH="$REPO_ROOT/config/polybar/launch.sh"
QTILE="$REPO_ROOT/flavours/qtile/config.py"

pass=0
fail=0

ok()   { printf '  ok   - %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  FAIL - %s\n' "$1"; fail=$((fail + 1)); }

# --- Preconditions -----------------------------------------------------------

[ -f "$LAUNCH" ] || { printf 'missing file: %s\n' "$LAUNCH" >&2; exit 2; }
[ -f "$QTILE" ]  || { printf 'missing file: %s\n' "$QTILE"  >&2; exit 2; }

echo "launch.sh quoting"

# --- 1. Regression guard: no literal quoted tilde ----------------------------

if grep -q '"~/' "$LAUNCH"; then
    bad 'launch.sh still contains a literal quoted tilde ("~/...)'
else
    ok 'launch.sh has no literal quoted tilde'
fi

# --- 2. Behavioural: the --config argument expands to a real path ------------

# Pull the token that follows --config= on the polybar line, quotes and all.
config_arg=$(grep -E 'polybar[[:space:]]+--config=' "$LAUNCH" \
    | head -1 \
    | sed -E 's/.*--config=//; s/[[:space:]]*$//')

if [ -z "$config_arg" ]; then
    bad 'could not find a `polybar --config=...` line in launch.sh'
else
    fake_home=$(mktemp -d)
    mkdir -p "$fake_home/.config/polybar"
    : > "$fake_home/.config/polybar/config.ini"

    # Expand the argument exactly as the shell would when running launch.sh,
    # but under a controlled HOME so the result is predictable.
    expanded=$(
        HOME="$fake_home"
        eval "printf '%s' $config_arg"
    )

    case "$expanded" in
        "~/"*|"~") bad "config path stays literal after expansion: $expanded" ;;
        /*)        ok  "config path expands to an absolute path" ;;
        *)         bad "config path is not absolute after expansion: $expanded" ;;
    esac

    if [ -f "$expanded" ]; then
        ok 'expanded config path resolves to an existing file'
    else
        bad "expanded config path does not resolve to a file: $expanded"
    fi

    rm -rf "$fake_home"
fi

echo "qtile launch path"

# --- 3. qtile routes Polybar through launch.sh with expansion ----------------

if grep -q 'launch.sh' "$QTILE"; then
    ok 'qtile references launch.sh'
else
    bad 'qtile does not reference launch.sh (still launching bare polybar?)'
fi

if grep -qE "processes[[:space:]]*=[[:space:]]*\[[[:space:]]*'polybar'[[:space:]]*\]" "$QTILE"; then
    bad "qtile still autostarts a bare 'polybar' process"
else
    ok 'qtile no longer autostarts a bare polybar process'
fi

if grep -q 'expanduser' "$QTILE"; then
    ok 'qtile expands the launch-script path (expanduser)'
else
    bad 'qtile does not expand the launch-script path (tilde will not resolve)'
fi

# --- Summary -----------------------------------------------------------------

echo
printf '%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
