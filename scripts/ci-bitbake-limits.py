#!/usr/bin/env python3
"""Apply explicit CI-only BitBake limits to generated config, not templates."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

LIMITS = {'BB_NUMBER_THREADS': '4', 'PARALLEL_MAKE': '-j4', 'BB_NUMBER_PARSE_THREADS': '4'}
BEGIN = '# BEGIN meta-iotedge CI resource limits'
END = '# END meta-iotedge CI resource limits'


def configure(path):
    text = path.read_text()
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
            raise ValueError('Malformed CI resource limits block')
        start = text.index(BEGIN)
        stop = text.index(END) + len(END)
        if text[stop:stop + 1] == '\n':
            stop += 1
        text = text[:start] + text[stop:]
    block = BEGIN + '\n' + ''.join(f'{name} = "{value}"\n' for name, value in LIMITS.items()) + END + '\n'
    path.write_text(text.rstrip('\n') + '\n' + block)


def verify():
    # Never dump bitbake -e: it can contain unrelated environment secrets.
    values = {}
    counts = dict.fromkeys(LIMITS, 0)
    with subprocess.Popen(['bitbake', '-e'], stdout=subprocess.PIPE, text=True) as process:
        assert process.stdout is not None
        for line in process.stdout:
            match = re.fullmatch(r'(?:export )?(BB_NUMBER_THREADS|PARALLEL_MAKE|BB_NUMBER_PARSE_THREADS)="([^"\n]*)"\n?', line)
            if match:
                counts[match[1]] += 1
                values[match[1]] = match[2]
        if process.wait() != 0:
            raise ValueError('bitbake -e failed while checking CI limits')
    if values != LIMITS or any(count != 1 for count in counts.values()):
        raise ValueError('Effective BitBake concurrency does not match CI limits')
    print('Verified CI BitBake limits: ' + json.dumps(values, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['configure', 'verify'])
    parser.add_argument('local_conf', type=Path, nargs='?')
    args = parser.parse_args()
    try:
        if args.operation == 'configure':
            if args.local_conf is None:
                parser.error('configure requires local_conf')
            configure(args.local_conf)
        else:
            verify()
    except (OSError, ValueError) as exc:
        print(f'CI resource limits failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
