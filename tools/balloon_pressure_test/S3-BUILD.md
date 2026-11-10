# ESP32-S3 compile milestone

ESP-IDF v5.4.1 (`4c2820d377d1375e787bcef612f0c32c1427d183`),
Xtensa GCC 14.2.0 (`esp-14.2.0_20241119`), Python 3.12.3.

```sh
export IDF_TOOLS_PATH="$HOME/toolchains/espressif-v5.4.1"
. "$HOME/toolchains/esp-idf-v5.4.1/export.sh"
cd tools/balloon_pressure_test
idf.py -G 'Unix Makefiles' set-target esp32s3
idf.py -G 'Unix Makefiles' build
make -C test check
```

The SDK was installed isolated under `~/toolchains` using the v5.4.1 tag
and its pinned submodules, `install.sh esp32s3`, and `idf_tools.py
install-python-env` using system Python outside the agent virtualenv.
Unix Makefiles avoids requiring Ninja on this host.

## Fix and evidence

The initial real S3 build failed on the three undefined
`CONFIG_BALLOON_IL_*` macros. ESP-IDF discovers `Kconfig.projbuild` in
components, not the project root. Move that unchanged file into `main/`;
do not invent fallback safety constants. Reconfigure/build then passed,
producing an app of 0x3bec0 bytes with 77% of the default app partition free.
The existing source at PR #539 head uses the new I2C master API consistently;
no legacy I2C API substitution was needed.

This is compile/link evidence only. Default SDK flash sizing is 2 MB and
console defaults are not a claim of suitability for a particular board.
No flash, serial connection, sensor acquisition, pump/valve actuation, or
hardware test was performed. Measurement-only behavior is unchanged; the
interlock remains a stub, not an operational safety mechanism.
