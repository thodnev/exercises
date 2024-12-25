#!/usr/bin/env python3
"""Applies changes from the changeset and builds project."""

import argparse
from dataclasses import dataclass
import logging
import pathlib as pth
import re
import runpy
import shutil
import sys
import tempfile
import types
import typing as t

DEFS = {
    'build_dir': 'build',
    'changeset_dir': 'changeset',
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BUILD' if __name__ == '__main__' else __name__)


def is_empty_dir(path: pth.Path):
    _, dirs, files = next(path.walk())
    return not dirs and not files


@dataclass
class Change:
    priority: int
    id: str
    name: str
    file: pth.Path

    FNAME_RE = re.compile(r'(\d+)_(.*?)[.]py')

    @classmethod
    def path_match(cls, filepath: pth.Path | str):
        filepath = pth.Path(filepath)

        return (filepath.suffix.lower() == '.py' and filepath.exists()
                and cls.FNAME_RE.fullmatch(filepath.name) or None)

    @classmethod
    def collect_dir(cls, dir: pth.Path | str) -> list[t.Self]:
        dir = pth.Path(dir)

        return [cls(file) for file in dir.iterdir()
                if cls.FNAME_RE.fullmatch(file.name)]

    def __init__(self, filepath: pth.Path | str, dir: t.Optional[pth.Path | str] = None):
        if dir is not None:
            dir = pth.Path(dir)
            filepath = dir.joinpath(filepath)
        else:
            filepath = pth.Path(filepath)

        match = self.path_match(filepath)
        assert match, 'Wrong file path'

        priority, id = match.groups()

        tmp = '\0TEMP\0'
        name = id.replace('__', tmp)
        name = name.replace('_', ' ')
        name = name.replace(tmp, '_')

        self.id = id
        self.name = name.capitalize()
        self.priority = int(priority)
        self.file = filepath

    def apply(self, env, *extra_args, **extra_kwargs):
        globs = runpy.run_path(str(self.file), run_name=self.id)
        build = globs['build']
        res = build(env, *extra_args, **extra_kwargs)
        return res


class BuildError(Exception):
    pass


class Build:
    # Buildvars defaults
    builddir = 'build'
    changesetdir = 'changeset'
    # changeset: list
    # tmpdir: ...
    log = logger

    def __init__(self, **buildvars):
        for k, v in buildvars.items():
            setattr(self, k, v)
        self.changeset = []

    def tmpdir_mount(self, move_files: bool = True):
        tmp = getattr(self, 'tmpdir', None)
        if tmp:
            raise BuildError(f'tmpdir already mounted as "{tmp.name}"')

        prefix = pth.Path(self.builddir).stem + '_'
        self.tmpdir = tempfile.TemporaryDirectory(prefix=prefix)
        self.builddir, self.builddir_orig = [pth.Path(self.tmpdir.name),
                                             pth.Path(self.builddir)]

        if move_files and not is_empty_dir(self.builddir_orig):
            self.log.info(f'Moving files from builddir "{self.builddir_orig}"' +
                          f' to tmpdir "{self.builddir}"')
            # NOTE: Python bug - without dirs_exitst_ok it tries
            #       to recreate the dst dir itself
            shutil.copytree(src=self.builddir_orig, dst=self.builddir, dirs_exist_ok=True)

        self.log.info(f'Mounted tmpdir "{self.builddir}" as builddir')

    def tmpdir_umount(self, move_files: bool = True):
        curdir = self.builddir
        self.builddir = getattr(self, 'builddir_orig', self.builddir)  # restore ASAP
        tmp = getattr(self, 'tmpdir', None)

        if not tmp:
            self.log.warning('Trying to umount tmpdir that was not mounted')
            return

        assert curdir == pth.Path(tmp.name), 'tmpdir handle changed during build'
        if move_files and not is_empty_dir(pth.Path(curdir)):
            self.log.info('Moving files from tmpdir ' +
                          f'"{curdir}" to builddir "{self.builddir}"')
            shutil.copytree(src=curdir, dst=self.builddir, dirs_exist_ok=True)

        tmp.cleanup()
        self.log.info(f'Unmounted tmpdir "{curdir}"')

    def changeset_load(self, changeset_dir=None):
        ...

    def parse_args(self, argv=sys.argv):
        progname, *args = argv
        parser = argparse.ArgumentParser(prog=progname,
                                         description=__doc__,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        parser.add_argument('--build-dir',
                            default=DEFS.build_dir,
                            type=pth.Path,
                            help='Build directory')

        parser.add_argument('--changeset-dir',
                            default=DEFS.changeset_dir,
                            type=pth.Path,
                            help='Directory with patches')

        parser.add_argument('-s', '--skip', help='Changeset to skip [i.e. 1,2-3,5]')

        res = parser.parse_args()
        return res

    def _changeset_collect(self):
        pat = Change.FNAME_RE
        cdir = pth.Path(self.changesetdir)

        chgs = [name.relative_to(cdir) for name in cdir.glob('*.py')]
        chgs = [name for name in chgs if pat.fullmatch(str(name))]
        chgs = [name.stem for name in chgs]

        chgs.sort()
        #res = {int(el.split('_')[0]): el for el in chgs}
        return chgs

    def apply_change(self, change_entry):
        cdir = pth.Path(self.changesetdir)
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
    build_dir.mkdir(exist_ok=False)  # must not exist before


if __name__ == '__main__':
    bld = Build()
    chgs = bld._changeset_collect()
    bld.changeset.extend(chgs)
