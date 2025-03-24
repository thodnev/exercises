"""Set environment for all changeset recipes."""

import pathlib as pth
from types import SimpleNamespace
# import logging

# log = logging.getLogger('FreeDB')

def build(env, log):
    #log.parent = env.log

    # transform once for any further use
    env.freedb_dir = pth.Path(env.freedb_dir)
    env.exc_dir = env.builddir.joinpath(env.exc_dir)

    # reformat freedb_model generation
    mdl = SimpleNamespace(env.freedb_model_gen)
    mdl.schema_file = pth.Path(mdl.schema_file.format(env=env))
    mdl.model_file = pth.Path(mdl.model_file)
    env.freedb_model_gen = mdl