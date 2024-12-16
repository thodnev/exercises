#!/usr/bin/env python3

"""Applies changes from the changeset and builds project."""

import types
import argparse
import logging
import pathlib as pth
import sys

DEF = types.SimpleNamespace(
    build_dir='build',
    changeset_dir='changeset',
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('BUILD' if __name__ == '__main__' else __name__)

def clean(builddir: pth.Path):
    ...

def build(builddir: pth.Path):
    builddir = pth.Path(builddir)
    builddir.mkdir(exist_ok=False)      # must not exist before

def parse_args(argv=sys.argv):
    progname, *args = argv
    parser = argparse.ArgumentParser(
        prog=progname,
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('--build-dir',
        default=DEF.build_dir, type=pth.Path,
        help='Build directory')
    
    parser.add_argument('--changeset-dir',
        default=DEF.changeset_dir, type=pth.Path,
        help='Directory with patches')

    res = parser.parse_args()
    return res


if __name__ == '__main__':
    ...