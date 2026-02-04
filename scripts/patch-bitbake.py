#!/usr/bin/env python3
import argparse
from pathlib import Path


def find_line_index(lines, prefix):
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            return i
    return -1


def replace_kv(lines, key, value):
    idx = find_line_index(lines, f"{key} =")
    new_line = f'{key} = "{value}"'
    if idx >= 0:
        lines[idx] = new_line
        return idx
    return -1


def insert_after(lines, anchor_prefix, new_lines):
    idx = find_line_index(lines, anchor_prefix)
    if idx == -1:
        return False
    insert_at = idx + 1
    for offset, line in enumerate(new_lines):
        lines.insert(insert_at + offset, line)
    return True


def ensure_line_after(lines, anchor_prefix, line_text):
    for line in lines:
        if line.strip() == line_text:
            return False
    insert_after(lines, anchor_prefix, [line_text])
    return True


def replace_lic_files(lines, new_block_lines):
    start = -1
    end = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("LIC_FILES_CHKSUM"):
            start = i
            break
    if start == -1:
        return False
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == '"':
            end = j
            break
    if end == -1:
        return False
    lines[start:end + 1] = new_block_lines
    return True


def ensure_inherit(lines, inherit_line):
    for i, line in enumerate(lines):
        if line.strip().startswith("inherit "):
            lines[i] = inherit_line
            return True
    return False


def remove_include_statements(lines):
    """Remove explicit include statements since BitBake auto-includes matching .inc files."""
    # Find and remove lines like:
    # # includes this file if it exists but does not fail
    # include foo-${PV}.inc
    # include foo.inc
    indices_to_remove = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("include ") and stripped.endswith(".inc"):
            indices_to_remove.append(i)
            # Also check for preceding comment
            if i > 0 and "includes this file if it exists" in lines[i - 1]:
                indices_to_remove.append(i - 1)
    # Remove in reverse order to maintain indices
    for idx in sorted(set(indices_to_remove), reverse=True):
        del lines[idx]


def main():
    parser = argparse.ArgumentParser(description="Patch cargo-bitbake output to match meta-iotedge conventions.")
    parser.add_argument("--component", required=True, choices=[
        "aziot-edged", "iotedge", "aziot-keys", "aziotd", "aziotctl"
    ])
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    lines = input_path.read_text().splitlines()

    if args.component in {"aziot-edged", "iotedge"}:
        if args.component == "aziot-edged":
            ensure_inherit(lines, "inherit cargo pkgconfig")
        replace_kv(lines, "S", "${WORKDIR}/git")
        cargo_dir = "edgelet/aziot-edged" if args.component == "aziot-edged" else "edgelet/iotedge"
        cargo_idx = replace_kv(lines, "CARGO_SRC_DIR", cargo_dir)
        if cargo_idx == -1:
            inserted = insert_after(lines, "S =", [f'CARGO_SRC_DIR = "{cargo_dir}"'])
            if not inserted:
                lines.insert(0, f'CARGO_SRC_DIR = "{cargo_dir}"')

        # Cargo.lock is at the workspace level (edgelet/), not in the per-crate subdirectory
        if find_line_index(lines, "CARGO_LOCK_PATH") == -1:
            if not insert_after(lines, "CARGO_SRC_DIR =", ['CARGO_LOCK_PATH = "${S}/edgelet/Cargo.lock"']):
                insert_after(lines, "S =", ['CARGO_LOCK_PATH = "${S}/edgelet/Cargo.lock"'])

        if find_line_index(lines, "do_compile[network]") == -1:
            if not insert_after(lines, "CARGO_SRC_DIR =", ['do_compile[network] = "1"']):
                insert_after(lines, "S =", ['do_compile[network] = "1"'])

        replace_lic_files(
            lines,
            [
                'LIC_FILES_CHKSUM = " \\',
                '    file://LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d \\',
                '    file://THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b \\',
                '"',
            ],
        )
        # Keep the include statements - we need them to load version-specific and common .inc files
        # The cargo-bitbake template adds:
        #   include iotedge-${PV}.inc
        #   include iotedge.inc
        # These are needed to load our DEPENDS, SRC_URI patches, and do_configure:append
    else:
        if args.component in {"aziot-keys", "aziotd"}:
            ensure_inherit(lines, "inherit cargo pkgconfig")
        replace_kv(lines, "S", "${WORKDIR}/git")
        replace_lic_files(
            lines,
            [
                'LIC_FILES_CHKSUM = " \\',
                '    file://LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e \\',
                '"',
            ],
        )
        # Keep the include statements for version-specific .inc files

    output_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
