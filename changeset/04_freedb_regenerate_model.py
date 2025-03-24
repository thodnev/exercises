"""Regenerate freedb model file from its JSON schema using tools/genmodel.py"""

from tools.genmodel import SchemaModel
import logging

# log = logging.getLogger('FreeDB')

def build(env, log):
    __log = log
    log = logging.getLogger('genmodel')
    log.parent = __log

    cfg = env.freedb_model_gen
    regen = SchemaModel(schema_file=cfg.schema_file, model_file=cfg.model_file)

    is_regen = regen.regenerate(renew_checked_at=cfg.renew_checked_at,
                                **(cfg.codegen_extras or dict()))
    if is_regen:
        msg  = f'[REGENERATED] model {regen.model_file}'
        msg += f' from schema {regen.schema_file}'
        log.warning(msg)
    elif cfg.renew_checked_at:
        msg = '[NO REGEN NEEDED]'
        msg += f' Updated checked_at for model {regen.model_file}'
        msg += f' (schema {regen.schema_file})'
        log.info(msg)
    else:
        msg = '[NO UPDATE NEEDED]'
        msg += f' Model {regen.model_file} checked '
        msg += f' against schema {regen.schema_file}'
        msg += f'. No changes since checked-at: {regen.headers.checked_at}'
        log.info(msg)
