#!/bin/bash
# MacIP real-device self-test.
#
# Run on a Linux box as root:
#     sudo ./tools/self_test.sh
#
# What it does:
#   * creates a throwaway `dummy` interface (no real traffic, zero risk to
#     your real NICs)
#   * runs every MacIP tool against it through the real `ip` command path
#   * verifies each change by re-reading the interface state
#   * tests the save/restore round trip and the Ctrl+C restore behaviour
#   * removes the dummy interface when done
#
# Nothing outside the dummy interface is touched. Exit status is non-zero if
# any check fails.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="python3"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON="python"

IFACE="macip-test0"
PASS=0
FAIL=0

say()  { printf '%s\n' "$*"; }
ok()   { say "  [PASS] $*"; PASS=$((PASS + 1)); }
bad()  { say "  [FAIL] $*"; FAIL=$((FAIL + 1)); }
step() { say ""; say "=== $* ==="; }
die()  { say "[-] $*"; exit 1; }

# --- environment checks ----------------------------------------------------
[[ $EUID -eq 0 ]] || die "Run as root: sudo $0"
command -v ip >/dev/null 2>&1 || die "'ip' (iproute2) is required on this system."

read_mac() { local dev="${1:-$IFACE}"; ip -o link show "$dev" 2>/dev/null | grep -oE 'link/ether [0-9a-fA-F:]{17}' | awk '{print $2}'; }
read_ip()  { local dev="${1:-$IFACE}"; ip -o -4 addr show "$dev" 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print $2}' | head -1; }
read_ip6() { local dev="${1:-$IFACE}"; ip -o -6 addr show "$dev" 2>/dev/null | grep -oE 'inet6 [0-9a-fA-F:]+' | awk '{print $2}' | grep -v '^fe8' | head -1; }

# --- set up the dummy interface -------------------------------------------
step "Set up dummy interface '$IFACE'"
ip link show "$IFACE" >/dev/null 2>&1 && ip link del "$IFACE" >/dev/null 2>&1
if ! ip link add "$IFACE" type dummy 2>/dev/null; then
    modprobe dummy 2>/dev/null
    ip link add "$IFACE" type dummy 2>/dev/null || die "Could not create dummy interface (needs the 'dummy' kernel module)."
fi
ip link set "$IFACE" up
say "  interface ready: $(ip -o link show "$IFACE")"

cleanup() {
    say ""
    step "Cleanup"
    ip link del "${IFACE2:-}" >/dev/null 2>&1
    ip link del "$IFACE" >/dev/null 2>&1
    say "  removed dummy interface(s)"
    say ""
    say "==== $PASS passed, $FAIL failed ===="
    [[ $FAIL -eq 0 ]]
}
trap cleanup EXIT

# --- 0. interface discovery ------------------------------------------------
step "interfaces.py lists the dummy interface"
out="$("$PYTHON" "$SCRIPT_DIR/interfaces.py" 2>&1)"
echo "$out" | grep -q "$IFACE" && ok "interfaces.py shows '$IFACE'" || bad "interfaces.py does not list '$IFACE'"

# --- 1. manual MAC change + restore round trip ------------------------------
step "01 - manual MAC change"
ORIG_MAC="$(read_mac)"
TARGET_MAC="02:aa:bb:cc:dd:01"
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE" -m "$TARGET_MAC" >/dev/null 2>&1
NOW_MAC="$(read_mac)"
[[ "$NOW_MAC" == "$TARGET_MAC" ]] && ok "MAC is now $NOW_MAC" || bad "MAC is '$NOW_MAC', expected '$TARGET_MAC'"

step "restore.py reverts to the original MAC"
"$PYTHON" "$SCRIPT_DIR/restore.py" -i "$IFACE" >/dev/null 2>&1
RESTORED_MAC="$(read_mac)"
[[ "$RESTORED_MAC" == "$ORIG_MAC" ]] && ok "MAC restored to $RESTORED_MAC" || bad "MAC is '$RESTORED_MAC', expected '$ORIG_MAC'"

# --- 3. manual IP change -----------------------------------------------------
step "03 - manual IP change"
TARGET_IP="10.99.99.99"
"$PYTHON" "$SCRIPT_DIR/03_ip_changer.py" -i "$IFACE" -ip "$TARGET_IP" >/dev/null 2>&1
NOW_IP="$(read_ip)"
[[ "$NOW_IP" == "$TARGET_IP" ]] && ok "IP is now $NOW_IP" || bad "IP is '$NOW_IP', expected '$TARGET_IP'"

# --- 5. manual combined change -----------------------------------------------
step "05 - manual MAC + IP change"
TARGET_MAC="02:aa:bb:cc:dd:05"
TARGET_IP="10.99.99.105"
"$PYTHON" "$SCRIPT_DIR/05_macip_changer.py" -i "$IFACE" -m "$TARGET_MAC" -ip "$TARGET_IP" >/dev/null 2>&1
NOW_MAC="$(read_mac)"
NOW_IP="$(read_ip)"
[[ "$NOW_MAC" == "$TARGET_MAC" && "$NOW_IP" == "$TARGET_IP" ]] \
    && ok "MAC=$NOW_MAC IP=$NOW_IP" \
    || bad "MAC='$NOW_MAC' IP='$NOW_IP', expected MAC='$TARGET_MAC' IP='$TARGET_IP'"

# --- 3b. manual IPv6 change ----------------------------------------------------
step "03 - manual IPv6 change"
TARGET_IP6="fd00::1234"
"$PYTHON" "$SCRIPT_DIR/03_ip_changer.py" -i "$IFACE" -ip "$TARGET_IP6" >/dev/null 2>&1
NOW_IP6="$(read_ip6)"
[[ "$NOW_IP6" == "$TARGET_IP6" ]] && ok "IPv6 is now $NOW_IP6" || bad "IPv6 is '$NOW_IP6', expected '$TARGET_IP6'"

# --- 2. auto MAC changer ------------------------------------------------------
step "02 - auto MAC changer (3 changes)"
out="$("$PYTHON" "$SCRIPT_DIR/02_auto_mac_changer.py" -i "$IFACE" --times 3 --interval 0.2 2>&1)"
echo "$out" | grep -q "Done. Applied 3 MAC changes" \
    && ok "completed 3 changes" || bad "did not complete 3 changes"
NOW_MAC="$(read_mac)"
[[ "$NOW_MAC" =~ ^02: ]] && ok "MAC is locally administered: $NOW_MAC" || bad "MAC '$NOW_MAC' is not locally administered"

# --- 4. auto IP changer --------------------------------------------------------
step "04 - auto IP changer (3 changes)"
out="$("$PYTHON" "$SCRIPT_DIR/04_auto_ip_changer.py" -i "$IFACE" --times 3 --interval 0.2 2>&1)"
echo "$out" | grep -q "Done. Applied 3 IP changes" \
    && ok "completed 3 changes" || bad "did not complete 3 changes"

# --- 6. auto combined changer ---------------------------------------------------
step "06 - auto MAC+IP changer (2 changes)"
out="$("$PYTHON" "$SCRIPT_DIR/06_auto_macip_changer.py" -i "$IFACE" --times 2 --interval 0.2 2>&1)"
echo "$out" | grep -q "Done. Applied 2 MAC and IP changes" \
    && ok "completed 2 changes" || bad "did not complete 2 changes"

# --- 4b. auto IPv6 changer -------------------------------------------------------
step "04 - auto IPv6 changer (3 changes)"
out="$("$PYTHON" "$SCRIPT_DIR/04_auto_ip_changer.py" -i "$IFACE" --ipv6 --times 3 --interval 0.2 2>&1)"
echo "$out" | grep -q "Done. Applied 3 IP changes" \
    && ok "completed 3 changes" || bad "did not complete 3 changes"

# --- 6b. auto combined with IPv6 -------------------------------------------------
step "06 - auto MAC+IPv6 changer (2 changes)"
out="$("$PYTHON" "$SCRIPT_DIR/06_auto_macip_changer.py" -i "$IFACE" --ipv6 --times 2 --interval 0.2 2>&1)"
echo "$out" | grep -q "Done. Applied 2 MAC and IP changes" \
    && ok "completed 2 changes" || bad "did not complete 2 changes"

# --- dry-run must not touch the interface --------------------------------------
step "dry-run leaves the interface untouched"
BEFORE_MAC="$(read_mac)"
BEFORE_IP="$(read_ip)"
BEFORE_IP6="$(read_ip6)"
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE" -m "02:00:00:00:00:99" --dry-run >/dev/null 2>&1
AFTER_MAC="$(read_mac)"
[[ "$AFTER_MAC" == "$BEFORE_MAC" ]] \
    && ok "MAC unchanged after dry-run ($AFTER_MAC)" || bad "MAC changed by dry-run: $BEFORE_MAC -> $AFTER_MAC"
"$PYTHON" "$SCRIPT_DIR/03_ip_changer.py" -i "$IFACE" -ip "fd00:dead::99" --dry-run >/dev/null 2>&1
AFTER_IP6="$(read_ip6)"
[[ "$AFTER_IP6" == "$BEFORE_IP6" ]] \
    && ok "IPv6 unchanged after dry-run ($AFTER_IP6)" || bad "IPv6 changed by dry-run: $BEFORE_IP6 -> $AFTER_IP6"

# --- Ctrl+C restores the saved configuration ------------------------------------
step "Ctrl+C during auto mode restores the configuration"
LOG="$(mktemp)"
"$PYTHON" "$SCRIPT_DIR/06_auto_macip_changer.py" -i "$IFACE" --times 10 --interval 5 >"$LOG" 2>&1 &
PID=$!
sleep 2
kill -INT "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
RC=$?
grep -q "Interrupted by user" "$LOG" && ok "process reported the interrupt" || bad "no interrupt message in output"
grep -q "Original configuration restored" "$LOG" && ok "configuration was restored on interrupt" || bad "no restore message on interrupt"
[[ $RC -eq 130 ]] && ok "exited with code 130 (SIGINT)" || bad "exit code was $RC, expected 130"
rm -f "$LOG"

# --- restore-all reverts every touched interface --------------------------------
step "restore-all reverts every touched interface"
IFACE2="macip-test1"
ip link add "$IFACE2" type dummy 2>/dev/null && ip link set "$IFACE2" up
PRE0="$(read_mac "$IFACE")"
PRE2="$(read_mac "$IFACE2")"
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE" -m "02:aa:bb:cc:dd:77" >/dev/null 2>&1
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE2" -m "02:aa:bb:cc:dd:88" >/dev/null 2>&1
NOW0="$(read_mac "$IFACE")"
NOW2="$(read_mac "$IFACE2")"
[[ "$NOW0" == "02:aa:bb:cc:dd:77" && "$NOW2" == "02:aa:bb:cc:dd:88" ]] \
    && ok "both interfaces changed ($IFACE=$NOW0, $IFACE2=$NOW2)" \
    || bad "interfaces not changed (got '$NOW0', '$NOW2')"
"$PYTHON" "$SCRIPT_DIR/restore.py" --all --yes >/dev/null 2>&1
REST0="$(read_mac "$IFACE")"
REST2="$(read_mac "$IFACE2")"
[[ "$REST0" == "$PRE0" && "$REST2" == "$PRE2" ]] \
    && ok "both interfaces restored to their pre-change values" \
    || bad "restore-all failed (got '$REST0', '$REST2'; expected '$PRE0', '$PRE2')"
ip link del "$IFACE2" >/dev/null 2>&1

# --- status.py reports MacIP state -------------------------------------------------
step "status.py reports MacIP state"
out="$("$PYTHON" "$SCRIPT_DIR/status.py" 2>&1)"
echo "$out" | grep -q "MacIP status" \
    && ok "status.py ran and printed the report" || bad "status.py failed: $(echo "$out" | head -2)"

# --- --no-save preserves the original across scheduled rotations ---------------
step "--no-save preserves the original saved configuration"
PRE_MAC="$(read_mac "$IFACE")"
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE" -m "02:aa:bb:cc:dd:99" >/dev/null 2>&1
"$PYTHON" "$SCRIPT_DIR/01_mac_changer.py" -i "$IFACE" -m "02:aa:bb:cc:dd:98" --no-save >/dev/null 2>&1
"$PYTHON" "$SCRIPT_DIR/restore.py" -i "$IFACE" --yes >/dev/null 2>&1
REST_MAC="$(read_mac "$IFACE")"
[[ "$REST_MAC" == "$PRE_MAC" ]] \
    && ok "restore reverted to the true original ($PRE_MAC), not the intermediate change" \
    || bad "restore got '$REST_MAC', expected the original '$PRE_MAC'"
