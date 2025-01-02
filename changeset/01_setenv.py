"""Set environment for all changeset recipes."""

import pathlib as pth
# import logging

# log = logging.getLogger('FreeDB')

def build(env, log):
    #log.parent = env.log

    # transform once for any further use
    env.freedb_dir = pth.Path(env.freedb_dir)
    env.exc_dir = env.builddir.joinpath(env.exc_dir)