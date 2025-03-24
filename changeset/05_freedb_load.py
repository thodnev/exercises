from models.freedb import Exercise
from tools.common import IDMap
import pathlib as pth

def build(env, log):
    _, dirs, __ = next(env.exc_dir.walk())
    excjson = [env.exc_dir.joinpath(d, env.freedb_exc_json) for d in dirs]

    # collect exercises here
    exes = IDMap('id')          # .id is the attr for mapping keys 
    for file in excjson:
        ex = Exercise.from_json_file(file)
        exes.add_item(ex)
    
    env.freedb_collection = exes
    log.info(f'Loaded {len(exes)} json files'
             f' ({env.freedb_exc_json}) into collection')