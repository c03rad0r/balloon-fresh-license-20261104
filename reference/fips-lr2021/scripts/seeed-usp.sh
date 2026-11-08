#!/usr/bin/env bash
# Set up and drive the pinned Semtech USP Zephyr samples without global installs.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REFERENCE_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)

USP_ZEPHYR_URL=${USP_ZEPHYR_URL:-https://github.com/Lora-net/usp_zephyr.git}
USP_ZEPHYR_REF=${USP_ZEPHYR_REF:-64f416bddd5c95ec4504b00627aa932eb88c7bd5}
ZEPHYR_SDK_VERSION=${ZEPHYR_SDK_VERSION:-1.0.1}
WORKSPACE=${SEED_USP_WORKSPACE:-$REFERENCE_DIR/build/seeed-usp-workspace}
VENV_DIR="$WORKSPACE/.venv"
USP_DIR="$WORKSPACE/usp_zephyr"
ZEPHYR_DIR="$WORKSPACE/zephyr"
SDK_DIR="$WORKSPACE/sdk/zephyr-sdk-$ZEPHYR_SDK_VERSION"
WEST_BIN="$VENV_DIR/bin/west"
LOCAL_HOME="$WORKSPACE/.home"
ORIGINAL_PATH=$PATH

BOARD=xiao_nrf54l15/nrf54l15/cpuapp
PER_SAMPLE=samples/usp/sdk/packet_error_rate_flrc
FLRP_SAMPLE=samples/usp/rac/flrp_api
DEFAULT_FLRP_DATA_SIZE='(20*1024)'

usage() {
    cat <<'EOF'
Usage: scripts/seeed-usp.sh COMMAND [ROLE]

Commands:
  setup                         Create the local venv, checkout and Zephyr SDK.
  doctor                        Report host/workspace/probe/serial prerequisites.
  build per-rx|per-tx|flrp-initiator|flrp-slave
  flash per-rx|per-tx|flrp-initiator|flrp-slave   (requires PROBE)
  monitor                       Open the stock UART console (requires PORT).

Environment:
  SEED_USP_WORKSPACE  Defaults to reference/fips-lr2021/build/seeed-usp-workspace.
  USP_ZEPHYR_REF      Full immutable commit; defaults to the pinned v1.2.1 source.
  ZEPHYR_SDK_VERSION  Defaults to 1.0.1.
  FLRP_DATA_SIZE      Defaults to (20*1024); integer or compact A*B expression.
  FLRP_LOW_FREQ       true (stock sub-GHz default) or false (2.4 GHz).
  FLRP_CRYPTO         true (AES-CMAC integrity) or false (radio CRC).
  PROBE               Explicit CMSIS-DAP unique ID for flash; never guessed.
  PORT                Explicit serial device for monitor; /dev/serial/by-id preferred.
  BAUD                Console baud rate; defaults to 115200.
EOF
}

log() {
    printf 'seeed-usp: %s\n' "$*"
}

warn() {
    printf 'seeed-usp: WARNING: %s\n' "$*" >&2
}

die() {
    printf 'seeed-usp: ERROR: %s\n' "$*" >&2
    exit 1
}

require_var() {
    local name=$1
    local purpose=$2
    local value=${!name:-}
    [[ -n "$value" ]] || die "$name is required for $purpose (for example: $name=<value> make ...)."
}

validate_ref() {
    [[ "$USP_ZEPHYR_REF" =~ ^[0-9a-f]{40}$ ]] ||
        die "USP_ZEPHYR_REF must be a full 40-character lowercase commit ID; main/tags are not accepted."
}

prepare_local_environment() {
    mkdir -p "$LOCAL_HOME" "$WORKSPACE/.cache/pip" "$WORKSPACE/.config" "$WORKSPACE/logs"
    export HOME="$LOCAL_HOME"
    export XDG_CACHE_HOME="$WORKSPACE/.cache"
    export XDG_CONFIG_HOME="$WORKSPACE/.config"
    export PIP_CACHE_DIR="$WORKSPACE/.cache/pip"
    export ZEPHYR_SDK_INSTALL_DIR="$SDK_DIR"
    export ZEPHYR_TOOLCHAIN_VARIANT=zephyr
    export ZEPHYR_BASE="$ZEPHYR_DIR"
    export VIRTUAL_ENV="$VENV_DIR"
    export PATH="$VENV_DIR/bin:$ORIGINAL_PATH"
}

run_west() {
    prepare_local_environment
    (
        cd "$WORKSPACE"
        export ZEPHYR_BASE="$ZEPHYR_DIR"
        "$WEST_BIN" "$@"
    )
}

verify_usp_ref() {
    [[ -d "$USP_DIR/.git" ]] ||
        die "Pinned USP checkout is missing at $USP_DIR; run 'make seeed-setup'."
    local actual
    if ! actual=$(git -C "$USP_DIR" rev-parse HEAD 2>/dev/null); then
        die "Cannot read HEAD in $USP_DIR. Repair that checkout; the helper will not reset it."
    fi
    [[ "$actual" == "$USP_ZEPHYR_REF" ]] ||
        die "USP checkout is $actual, expected $USP_ZEPHYR_REF. Use a fresh workspace or deliberately check out the requested immutable ref; no automatic reset is done."
}

validate_flrp_options() {
    local size=${FLRP_DATA_SIZE:-$DEFAULT_FLRP_DATA_SIZE}
    local low_freq=${FLRP_LOW_FREQ:-true}
    local crypto=${FLRP_CRYPTO:-true}

    [[ "$size" =~ ^[0-9]+$ || "$size" =~ ^\([0-9]+\*[0-9]+\)$ ]] ||
        die "FLRP_DATA_SIZE must be an integer or compact expression such as (20*1024); whitespace and arbitrary C are rejected."
    [[ "$low_freq" == true || "$low_freq" == false ]] ||
        die "FLRP_LOW_FREQ must be exactly 'true' or 'false'."
    [[ "$crypto" == true || "$crypto" == false ]] ||
        die "FLRP_CRYPTO must be exactly 'true' or 'false'."
}

role_settings() {
    local role=$1
    BUILD_NAME=
    SAMPLE_REL=
    EXTRA_CFLAGS=

    case "$role" in
        per-rx)
            BUILD_NAME=seeed-per-rx
            SAMPLE_REL=$PER_SAMPLE
            EXTRA_CFLAGS=-DROLE=RECEIVER
            ;;
        per-tx)
            BUILD_NAME=seeed-per-tx
            SAMPLE_REL=$PER_SAMPLE
            EXTRA_CFLAGS=-DROLE=TRANSMITTER
            ;;
        flrp-initiator|flrp-slave)
            validate_flrp_options
            BUILD_NAME="seeed-$role"
            SAMPLE_REL=$FLRP_SAMPLE
            if [[ "$role" == flrp-initiator ]]; then
                EXTRA_CFLAGS=-DFLRP_API_ROLE=FLRP_API_ROLE_INITIATOR
            else
                EXTRA_CFLAGS=-DFLRP_API_ROLE=FLRP_API_ROLE_SLAVE
            fi
            EXTRA_CFLAGS+=" -DFLRP_API_DATA_SIZE=${FLRP_DATA_SIZE:-$DEFAULT_FLRP_DATA_SIZE}"
            EXTRA_CFLAGS+=" -DFLRP_API_IS_LOW_FREQUENCY=${FLRP_LOW_FREQ:-true}"
            EXTRA_CFLAGS+=" -DFLRP_API_CRYPTO_ENABLED=${FLRP_CRYPTO:-true}"
            ;;
        *)
            die "Unknown role '$role'. Expected per-rx, per-tx, flrp-initiator or flrp-slave."
            ;;
    esac

    BUILD_DIR="$WORKSPACE/build/$BUILD_NAME"
    APP_DIR="$USP_DIR/$SAMPLE_REL"
}

require_workspace() {
    validate_ref
    [[ -x "$WEST_BIN" ]] ||
        die "Local west is missing at $WEST_BIN; run 'make seeed-setup' (no global west is used)."
    [[ -f "$WORKSPACE/.west/config" ]] ||
        die "West workspace is not initialized at $WORKSPACE; run 'make seeed-setup'."
    [[ -f "$ZEPHYR_DIR/scripts/west_commands/build.py" ]] ||
        die "Zephyr v4.4.0 checkout is missing at $ZEPHYR_DIR; rerun 'make seeed-setup'."
    [[ -f "$SDK_DIR/sdk_version" ]] ||
        die "Local Zephyr SDK is missing at $SDK_DIR; rerun 'make seeed-setup'."
    verify_usp_ref
}

print_udev_guidance() {
    cat <<'EOF'
seeed-usp: udev guidance (manual administrator action only):
  If pyOCD reports permission denied, install pyOCD's current CMSIS-DAP rules
  and the pinned XIAO support/99-xiao-nrf54l15.rules using your OS procedure,
  then replug the device. This helper never runs sudo or writes /etc/udev.
  Upstream: https://github.com/pyocd/pyOCD/tree/main/udev
EOF
}

setup() {
    validate_ref
    local cmd
    for cmd in git python3 cmake ninja cc gperf dtc; do
        command -v "$cmd" >/dev/null 2>&1 ||
            die "Missing host prerequisite '$cmd'. Install Zephyr's documented host prerequisites with your OS package manager, then retry; the helper does not install them."
    done

    prepare_local_environment
    log "Workspace: $WORKSPACE"
    log "Pinned USP source: $USP_ZEPHYR_REF"

    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        python3 -m venv "$VENV_DIR" ||
            die "Could not create $VENV_DIR. Install your OS Python venv support (often python3-venv), then retry; no sudo command is attempted here."
    fi
    "$VENV_DIR/bin/python" -m pip install --disable-pip-version-check \
        'west>=1.3,<2' 'pyocd>=0.38.0' pyserial

    if [[ ! -e "$USP_DIR" ]]; then
        if ! git clone --no-checkout "$USP_ZEPHYR_URL" "$USP_DIR"; then
            die "Could not clone $USP_ZEPHYR_URL. Check network/proxy access. No existing checkout was removed."
        fi
        if ! git -C "$USP_DIR" checkout --detach "$USP_ZEPHYR_REF"; then
            die "Pinned ref $USP_ZEPHYR_REF could not be fetched/checked out. Verify that commit remains available upstream and inspect $USP_DIR; the helper does not float to main."
        fi
    fi
    verify_usp_ref

    if [[ ! -f "$WORKSPACE/.west/config" ]]; then
        (
            cd "$WORKSPACE"
            "$WEST_BIN" init -l usp_zephyr
        )
    fi
    # The pinned west.yml says self.path=application, while its standalone
    # README clones as usp_zephyr. Keep local west configuration aligned with
    # the actual clone used by all sample paths instead of guessing a rename.
    run_west config manifest.path usp_zephyr
    log "Running west update from the pinned manifest (large, multi-repository download)."
    if ! run_west update; then
        die "west update failed. Verify the pinned ref/network and inspect the output; for a manual manifest diagnostic run '$WEST_BIN -z $ZEPHYR_DIR -vv manifest --resolve' from $WORKSPACE. No fallback branch is used."
    fi
    verify_usp_ref

    log "Installing Zephyr Python requirements into $VENV_DIR only."
    run_west packages pip --install

    if [[ ! -f "$SDK_DIR/sdk_version" ]]; then
        log "Installing SDK $ZEPHYR_SDK_VERSION (minimal + ARM GNU only) below $WORKSPACE/sdk."
        if ! run_west sdk install --version "$ZEPHYR_SDK_VERSION" \
            --install-dir "$SDK_DIR" --gnu-toolchains arm-zephyr-eabi --no-hosttools; then
            die "Local Zephyr SDK install failed. Review the download/setup error above. The supported retry is 'make seeed-setup' after fixing it; no system SDK or udev rules are installed."
        fi
    fi

    [[ $(<"$SDK_DIR/sdk_version") == "$ZEPHYR_SDK_VERSION" ]] ||
        die "SDK version mismatch in $SDK_DIR/sdk_version; move/rename that local directory deliberately before retrying."
    [[ -x "$SDK_DIR/gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc" ]] ||
        die "ARM GNU compiler was not installed below $SDK_DIR; SDK setup did not complete."

    run_west list zephyr >/dev/null ||
        die "west cannot resolve Zephyr after setup; inspect the manifest.path/application mismatch in the runbook."
    log "Setup complete (host tools/source only; no board was accessed or validated)."
    log "Next: make seeed-doctor"
}

doctor() {
    local cmd
    printf 'Workspace: %s\n' "$WORKSPACE"
    printf 'USP pin:   %s\n' "$USP_ZEPHYR_REF"
    printf '\nHost commands (setup requires git, python3, cmake and ninja):\n'
    for cmd in git python3 cmake ninja make cc gperf dtc picocom; do
        if command -v "$cmd" >/dev/null 2>&1; then
            printf '  [ok]      %-8s %s\n' "$cmd" "$(command -v "$cmd")"
        else
            printf '  [missing] %-8s\n' "$cmd"
        fi
    done

    printf '\nLocal workspace:\n'
    if [[ -x "$WEST_BIN" ]]; then
        printf '  [ok]      west: '
        HOME="$LOCAL_HOME" "$WEST_BIN" --version
        if [[ -x "$VENV_DIR/bin/pyocd" ]]; then
            printf '  [ok]      pyOCD: '
            "$VENV_DIR/bin/pyocd" --version
        else
            printf '  [missing] local pyOCD\n'
        fi
    else
        printf '  [missing] local venv/west; run make seeed-setup\n'
    fi
    if [[ -f "$SDK_DIR/sdk_version" ]]; then
        printf '  [ok]      SDK %s at %s\n' "$(<"$SDK_DIR/sdk_version")" "$SDK_DIR"
    else
        printf '  [missing] SDK at %s\n' "$SDK_DIR"
    fi
    if [[ -d "$USP_DIR/.git" ]]; then
        printf '  USP HEAD: %s\n' "$(git -C "$USP_DIR" rev-parse HEAD 2>/dev/null || printf unreadable)"
        printf '  USP worktree status (must be empty for an unmodified baseline):\n'
        git -C "$USP_DIR" status --short ||
            printf '  [unknown] could not read USP worktree status\n'
    else
        printf '  [missing] pinned USP checkout\n'
    fi

    printf '\nStable serial paths (USB /dev/ttyACM* numbers are not stable):\n'
    if [[ -d /dev/serial/by-id ]]; then
        ls -l /dev/serial/by-id || true
    else
        printf '  No /dev/serial/by-id directory found; use your OS USB inventory.\n'
    fi

    printf '\nCMSIS-DAP probes (record full unique IDs; no flashing is done):\n'
    if [[ -x "$VENV_DIR/bin/pyocd" ]]; then
        if ! "$VENV_DIR/bin/pyocd" list; then
            print_udev_guidance
        fi
    else
        printf '  pyOCD unavailable until local setup completes.\n'
        print_udev_guidance
    fi

    cat <<'EOF'

Doctor is an inventory, not a build, board, RF, host-throughput or FIPS pass.
A missing host item does not imply a hardware fault. Verify exact SKU/probe/PORT
identity before using any flash or monitor target.
EOF
}

build_role() {
    local role=$1
    role_settings "$role"
    require_workspace
    [[ -f "$APP_DIR/CMakeLists.txt" ]] ||
        die "Pinned sample is missing at $APP_DIR. Do not substitute another sample layout; inspect the pinned checkout and upstream manifest."

    log "Building $role from $APP_DIR"
    log "Build directory: $BUILD_DIR"
    log "EXTRA_CFLAGS: $EXTRA_CFLAGS"
    run_west build --pristine --build-dir "$BUILD_DIR" --board "$BOARD" \
        --shield semtech_loraplus_expansion_board --shield semtech_wio_lr2021 \
        "$APP_DIR" -- "-DEXTRA_CFLAGS=$EXTRA_CFLAGS"
}

flash_role() {
    local role=$1
    require_var PROBE "flashing $role"
    [[ "$PROBE" != *[[:space:]]* ]] ||
        die "PROBE must be one exact unique CMSIS-DAP ID without whitespace; copy it from 'make seeed-doctor'."
    role_settings "$role"
    require_workspace
    [[ -f "$BUILD_DIR/CMakeCache.txt" ]] ||
        die "Build output for $role is missing at $BUILD_DIR; run its matching seeed-*-build target first."

    log "Flashing only $role image $BUILD_DIR to explicit PROBE=$PROBE"
    run_west flash --build-dir "$BUILD_DIR" --runner pyocd --dev-id "$PROBE"
}

monitor() {
    require_var PORT "the UART monitor"
    local baud=${BAUD:-115200}
    [[ "$baud" =~ ^[0-9]+$ ]] || die "BAUD must be numeric (stock console: 115200)."
    [[ "$PORT" == /dev/* ]] || die "PORT must be an explicit absolute /dev path; prefer /dev/serial/by-id/."
    [[ -e "$PORT" ]] || die "PORT $PORT does not exist. Re-identify it; do not guess /dev/ttyACM*."
    command -v picocom >/dev/null 2>&1 ||
        die "picocom is missing. Install it using your OS package manager; no global install is attempted by this helper."
    prepare_local_environment
    log "Opening $PORT at $baud 8N1, no flow control. picocom exit: Ctrl-a Ctrl-x."
    warn "This is the nRF54 UART20 console through SAMD11, not a direct LR2021 SPI link."
    (
        cd "$WORKSPACE"
        exec picocom --baud "$baud" --flow n --databits 8 --parity n --stopbits 1 "$PORT"
    )
}

main() {
    local command=${1:-}
    case "$command" in
        setup)
            [[ $# -eq 1 ]] || die "setup takes no role argument."
            setup
            ;;
        doctor)
            [[ $# -eq 1 ]] || die "doctor takes no role argument."
            doctor
            ;;
        build|flash)
            [[ $# -eq 2 ]] || die "$command requires exactly one role."
            if [[ "$command" == build ]]; then
                build_role "$2"
            else
                flash_role "$2"
            fi
            ;;
        monitor)
            [[ $# -eq 1 ]] || die "monitor takes no role argument; pass PORT explicitly."
            monitor
            ;;
        -h|--help|help)
            usage
            ;;
        *)
            usage >&2
            die "Unknown or missing command '$command'."
            ;;
    esac
}

main "$@"
