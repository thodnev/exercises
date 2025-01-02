"""Copy required files from Free-Exercise-DB into build directory."""

import pathlib as pth
import shutil


FREEDB_EXCDIR_NAME = 'exercises'        # freedb directory where exercises are located


def build(env, log):
    try:
        env.exc_dir.mkdir()
    except FileExistsError:
        log.warning(f'SKIPPING\t- Exercise dir {env.exc_dir} exists')
        return
    
    freedb_exc = env.freedb_dir.joinpath(FREEDB_EXCDIR_NAME)
    _, dirs, files = next(freedb_exc.walk())
    #dirs = [exdir.joinpath(d) for d in dirs]
    #files = [exdir.joinpath(f) for f in files if f.endswith('.json')]
    files = [freedb_exc.joinpath(f) for f in files if f.endswith('.json')]

    log.info(f'Found {len(files)} exercises and {len(dirs)} exercise dirs')
    if len(dirs) != len(files):
        log.warning(f'json/dir mismatch by {len(files) - len(dirs)}')

    entries = dict()
    _dirset = set(dirs)
    for file in files:
        name = file.stem
        try:
            _dirset.remove(name)
            dir = freedb_exc.joinpath(name)
        except KeyError:
            log.warning(f'No dir found for {file}')
            dir = None
        entries[file] = dir
    
    for dir in _dirset:
        log.warning(f'No JSON for dir {freedb_exc.joinpath(dir)}')

    log.info(f'Packing freedb exercises into "{env.exc_dir}"')
    for file, dir in entries.items():
        dst = env.exc_dir.joinpath(dir.name)
        log.debug('\tcopy {dir.name}')

        if dir is None:
            dst.mkdir()
        else:
            shutil.copytree(dir, dst)
        
        shutil.copy2(file, dst.joinpath(env.freedb_exc_json))
        
        