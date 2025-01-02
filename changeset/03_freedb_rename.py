"""Rename FreeDB exercises according to our own scheme."""

from itertools import filterfalse
import logging
import string
import typing as t

IDENT_MAX_LEN = 40
IDENT_ALLOWED_SYM = set(string.ascii_lowercase + string.digits + '_')

def ident_lint(ident: str) -> bool:
    """Checks whether exercise identifier is correctly named."""
    if len(ident) > IDENT_MAX_LEN:
        return False
    if set(ident) - IDENT_ALLOWED_SYM:
        return False
    return True

def ident_fixup(ident: str) -> str:
    # '-' may be unacceptable in further uses elsewhere
    ident = ident.replace('-', '_')
    ident = ident.lower()

    while '__' in ident:
        ident = ident.replace('__', '_')

    return ident

def length_histogram(idents: t.Iterable[str]):
    lens = list(map(len, idents))
    spread = dict()
    for l in lens:
        val = spread.setdefault(l, 0)
        spread[l] = val + 1
    keys = sorted(spread, key=spread.get, reverse=True)
    hist = {l: spread[l] for l in keys}
    return hist, sum(hist.values())

def build(env, log):
    _, dirs, __ = next(env.exc_dir.walk())
    curnames = dirs

    badnames = list(filterfalse(ident_lint, curnames))

    if not badnames:
        log.warning(f'SKIPPING\t- Ident names lint OK')
        return
    
    log.info(f'Lint found {len(badnames)} bad exercise ident names')
    log.debug('\t' + '\n\t'.join(sorted(badnames)))
    log.info(f'Renaming...')

    rest = []
    for name in badnames:
        newname = ident_fixup(name)

        if not ident_lint(newname):
            rest.append(newname)
    rest.sort()
    print(f'REST ({len(rest)}):')
    print('\t' + '\n\t'.join(rest))
    return


    nonstd = check_names([f.stem for f in files])
    if nonstd:
        names = '\n'.join([f'{syms}\t-> {el}' for el, syms in nonstd.items()])
        log.warning(f'Found {len(nonstd)} non-standard names:\n{names}')
    else:
        log.info(f'OK\tCheck json/dir names')


def exc_rename(oldname: str) -> str:

    return ''

...

def check_names(names):
    syms_std = set(string.ascii_letters + string.digits + ' -')

    nonstandard = dict()
    for name in names:
        repl = name.replace('_', ' ')
        syms_used = set(repl)
        syms_nonstd = syms_used - syms_std
        res = sorted(syms_nonstd, key=repl.find)
        res = ''.join(res)
        
        if res:
            nonstandard[name] = res
    
    n = sorted(names, key= lambda x: (len(x), x), reverse=True)
    n = [convert_name(i) for i in n if '-' in i]
    print('\n'.join(n))

    return nonstandard


def convert_name(name: str) -> str:
    # '-' may be unacceptable in further uses elsewhere
    n = name.replace('-', '_')
    n = n.lower()
    return n