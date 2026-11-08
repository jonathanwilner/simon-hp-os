#!/usr/bin/env python3
"""Build a client activation only after checking its complete GPU dependency graph.

Public installer/updater clients need no private builder credentials. Generic
closures build locally. NVIDIA-dependent closures are currently allowed only on
Goran. Evaluation cannot build through import-from-derivation, and builds cannot
be delegated through a machine's pre-existing remote builder configuration.
"""
import argparse
import json
import re
import socket
import subprocess
import sys

import build_router

NO_IFD = ['--option', 'allow-import-from-derivation', 'false']


def authorize(graph, derivation, hostname):
    marked = build_router.classify(graph, [derivation])
    if marked[derivation] and hostname.split('.')[0] != 'goran':
        raise ValueError('This activation depends on NVIDIA/CUDA packages. NVIDIA builds are currently Goran-only; no build was started.')
    return marked[derivation]


def build(installable, out_link):
    if not installable or '#' not in installable or installable.endswith('.drvPath'):
        raise ValueError('Pass a flake activation package installable, not a derivation attribute')
    derivation = subprocess.check_output(
        ['nix', 'eval', '--raw', '--no-update-lock-file', *NO_IFD,
         installable + '.drvPath'], text=True).strip()
    if not re.fullmatch(r'/nix/store/[a-z0-9]{32}-[^/\n]+\.drv', derivation):
        raise ValueError('Evaluation did not return a valid derivation path')
    graph = json.loads(subprocess.check_output(
        ['nix', 'derivation', 'show', '--recursive', *NO_IFD, derivation], text=True))
    authorize(graph, derivation, socket.gethostname())
    # Build the exact inspected derivation, avoiding a second flake evaluation
    # and keeping a change between evaluation and build from bypassing the gate.
    subprocess.run(['nix', 'build', '--no-update-lock-file', *NO_IFD,
                    '--option', 'builders', '', '--out-link', out_link,
                    derivation + '^*'], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installable')
    parser.add_argument('--out-link', required=True)
    args = parser.parse_args()
    try:
        build(args.installable, args.out_link)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'fleet-client-build: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
