#!/usr/bin/env python3
"""Applies changes from the changeset and builds project."""

import argparse
from dataclasses import dataclass
from getpass import getuser
import logging
import pathlib as pth
import re
import runpy
import shutil
import sys
import tempfile
import types
import typing as t

from ruamel.yaml import YAML as _YAML
yaml=_YAML(typ='safe')

DEFS = types.SimpleNamespace(**{
    'build_config': 'build_config.yml',
    'build_dir': 'build',
    'changeset_dir': 'changeset',
})

SCRIPT_DIR = pth.Path(__file__).parent

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
    log = logger
    # Buildvars defaults
    build_config: pth.Path | str = DEFS.build_config
    builddir: pth.Path | str = DEFS.build_dir
    changesetdir: pth.Path | str = DEFS.changeset_dir
    auto_tmpdir: bool = True

    builddir_orig: t.Optional[pth.Path]
    changeset: list[Change]
    change_queue: t.Optional[list[Change]]
    tmpdir: t.Optional[tempfile.TemporaryDirectory] = None
    

    def __init__(self, **buildvars):
        self.changeset = []
        self.configure_vars(**buildvars)  

    def tmpdir_mount(self, move_files: bool = True):
        tmp = getattr(self, 'tmpdir', None)
        if tmp:
            raise BuildError(f'tmpdir already mounted as "{tmp.name}"')

        prefix = pth.Path(self.builddir).stem + '_'
        self.tmpdir = tempfile.TemporaryDirectory(prefix=prefix)
        self.builddir, self.builddir_orig = [pth.Path(self.tmpdir.name),
                                             pth.Path(self.builddir)]

        self.builddir_orig.mkdir(exist_ok=True)
        if move_files and not is_empty_dir(self.builddir_orig):
            self.log.info(f'Copying files from builddir "{self.builddir_orig}"' +
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
        self.tmpdir = None
        self.log.info(f'Unmounted tmpdir "{curdir}"')

    def changeset_add_dir(self, dir: pth.Path | str):
        chgs = Change.collect_dir(dir)
        chgs = sorted(chgs, key=lambda c: [c.priority, c.id])
        self.changeset.extend(chgs)
    
    def build(self):
        changes = list(self.changeset)
        if not changes:
            raise BuildError('Changeset is empty, nothing to build')
        
        self.log.info(f"Let's cook some stuff, {getuser()}...")
        if self.auto_tmpdir:
            self.tmpdir_mount()

        sublog = logging.getLogger('...')
        sublog.parent = self.log

        self.change_queue = changes
        i = 0
        ntotal = len(self.change_queue)
        decim = len(str(ntotal))
        while self.change_queue:
            i += 1
            chg = self.change_queue.pop(0)

            msg = fr'[{i:>{decim}}\{ntotal}] Applying #{chg.priority} {chg.name}...'
            self.log.info(msg)

            sublog.name = chg.name
            chg.apply(env=self, log=sublog)
        
        if self.tmpdir:
            self.tmpdir_umount()

        self.log.info(f'[ALL DONE]')

    def configure(self, **buildvars):
        """Use available sources to configure build.

        Sources are tested in particular order and priority (higher to lower):
        - buildvars passed as kwargs
        - command-line arguments
        - YML config file
        - instance & class defaults
        """
        #cfg = self.parse_args()
        build_config = buildvars.get('build_config', self.build_config)
        
        try:
            self.configure_yaml(build_config)
        except FileNotFoundError:
            pass

        self.configure_vars(**buildvars)

        # Assuming everything is set to correctly call it
        if not self.changeset:
            self.changeset_add_dir(self.changesetdir)

    def configure_vars(self, **buildvars):
        for k, v in buildvars.items():
            setattr(self, k, v)

        # ensure dirs are set as Path
        for k in 'builddir', 'changesetdir':
            v = getattr(self, k)
            setattr(self, k, pth.Path(v)) 

    def configure_yaml(self, configfile: t.Optional[pth.Path | str] = None):
        configfile = configfile if configfile is not None else self.build_config
        configfile = pth.Path(configfile)
        # configfile = configfile.relative_to(SCRIPT_DIR)

        try:
            cfg = yaml.load(configfile)
            self.log.debug(f'Loaded config {configfile}:\n{cfg}')
            self.configure_vars(**cfg)
        except FileNotFoundError as exc:
            raise exc
        except Exception:
            raise BuildError(f'Config file "{configfile}" is not valid YML config')

    def parse_args(self, argv=sys.argv):
        # TODO: implement this
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

    def clean(build_dir: pth.Path):
        ...


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    bld = Build()
    bld.configure()
    bld.build()
