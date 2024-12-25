"""Copy required files from Free-Exercise-DB into build directory."""

def build(env):
    print(f'{__name__} got env "{env}"')
    env.log.info(f'Test some logging from {__name__}')