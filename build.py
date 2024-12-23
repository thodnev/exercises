#!/usr/bin/env python3

"""Applies changes from the changeset and builds project."""

import argparse
from dataclasses import dataclass
import logging
import pathlib as pth
import re
import runpy
import sys
import tempfile
import types

DEFS = {
    'build_dir': 'build',
    'changeset_dir': 'changeset',
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BUILD' if __name__ == '__main__' else __name__)

@dataclass
class Change:
    priority: int
    name: str
    file: pth.Path

    FNAME_RE = re.compile(r'(\d+)_(.*?)[.]py')

    @classmethod
    def path_match(cls, filepath: pth.Path | str):
        filepath = pth.Path(filepath)

        return (filepath.suffix.lower() == '.py'
                and filepath.exists()
                and cls.FNAME_RE.fullmatch(filepath.name))

    def __init__(self, filepath: pth.Path | str, dir: pth.Path | str | None = None):
        if dir is not None:
            dir = pth.Path(dir)
            filepath = dir.joinpath(filepath)
        else:
            filepath = pth.Path(filepath)
        
        match = self.path_match(filepath)
        assert match, 'Wrong file path'
        
        priority, name = match.groups()

        tmp = '\0TEMP\0'
        name = name.replace('__', tmp)
        name = name.replace('_', ' ')
        name = name.replace(tmp, '_')

        self.name = name.capitalize()
        self.priority = int(priority)
        self.file = filepath


    def apply(self, env):
        ...

class Build:
    # Buildvars defaults
    build_dir = 'build'
    changeset_dir = 'changeset'
    # changeset: list
    log = logger

    def __init__(self, **buildvars):
        for k, v in buildvars.items():
            setattr(self, k, v)
        self.changeset = []

    def parse_args(self, argv=sys.argv):
        progname, *args = argv
        parser = argparse.ArgumentParser(
            prog=progname,
            description=__doc__,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        
        parser.add_argument('--build-dir',
            default=DEFS.build_dir, type=pth.Path,
            help='Build directory')
        
        parser.add_argument('--changeset-dir',
            default=DEFS.changeset_dir, type=pth.Path,
            help='Directory with patches')
        
        parser.add_argument('-s', '--skip',
            help='Changeset to skip [i.e. 1,2-3,5]')

        res = parser.parse_args()
        return res

    def _changeset_collect(self):
        pat = Change.FNAME_RE
        cdir = pth.Path(self.changeset_dir)

        chgs = [name.relative_to(cdir) for name in cdir.glob('*.py')]
        chgs = [name for name in chgs if pat.fullmatch(str(name))]
        chgs = [name.stem for name in chgs]

        chgs.sort()
        #res = {int(el.split('_')[0]): el for el in chgs}
        return chgs
    
    def apply_change(self, change_entry):
        cdir = pth.Path(self.changeset_dir)
        file = cdir.joinpath(f'{change_entry}.py')

        globs = runpy.run_path(file, run_name=change_entry)
        build = globs['build']
        res = build(self)
        return res


def clean(build_dir: pth.Path):
    ...

def build(build_dir: pth.Path, changeset_dir: pth.Path, *, env):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = pth.Path(tmp_dir)
        env.out_dir = ...
    build_dir = pth.Path(build_dir)
    build_dir.mkdir(exist_ok=False)      # must not exist before

if __name__ == '__main__':
    bld = Build()
    chgs = bld._changeset_collect()
    bld.changeset.extend(chgs)
