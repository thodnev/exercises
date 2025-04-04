"""Batch convert images to avif using avifenc"""

import argparse
from collections.abc import Iterable, Mapping
import pathlib as pth
from tools.batch import CommandBatch

DEF_AVIFENC_OPTS = {
    'jobs': '1',
    'yuv': '420',
    'depth': '8',
    'codec': 'aom',
    'ignore-exif': None,
    'ignore-xmp': None,
    'ignore-icc': None,
    # 'autotiling': None,
}

DEF_CODEC_OPTS = {
    'end-usage': 'cq',
    'color:enable-chroma-deltaq': '1',
    'color:enable-qm': '1',
    'color:qm-min': '0',
}

AVIFENC_FMT = {  # passed into tools.CommandBatch
    'long': ['--{key}', '{value}'],
    'optlong': ['--{opt}', '{optkey}={optvalue}']
}


def avifconv(images: Iterable[pth.Path | str],
             *,
             nproc: int = 0,
             speed: int = 4,
             minqual: int = 36,
             qual: int = 68,
             maxqual: int = 94,
             sharpness: int = 4,
             avifenc_bin: pth.Path | str = 'avifenc',
             avifenc_extra: Mapping[str, str] = {},
             codec_extra: Mapping[str, str] = {}):
    images = list(map(pth.Path, images))
    speed = int(speed)
    sharpness = int(sharpness)
    assert 0 <= speed <= 10, 'speed outside of [0, 9] range'
    assert 0 <= sharpness <= 7, 'sharpness outside of [0, 7] range'

    def qual2q(qual):
        ret = round(63 * (1 - (qual / 100)))
        assert 0 <= ret <= 63, 'quality outside of [0, 100] range'
        return ret

    minqual, qual, maxqual = map(qual2q, [minqual, qual, maxqual])
    maxqual, minqual = minqual, maxqual  # they're opposite for avifenc

    opts = dict(DEF_AVIFENC_OPTS)
    opts.update({'speed': str(speed), 'min': str(minqual), 'max': str(maxqual)})
    opts.update(avifenc_extra)

    copts = dict(DEF_CODEC_OPTS)
    copts.update({'cq-level': str(qual), 'sharpness': str(sharpness)})
    copts.update(codec_extra)

    opts.setdefault('a', {}).update(copts)  # nesting will be resolved

    imgout = [i.with_suffix('.avif') for i in images]
    items = tuple(zip(images, imgout))

    batch = CommandBatch(nproc=nproc, fmt=AVIFENC_FMT)
    batch.cmd_set(str(avifenc_bin), opts)
    for [imgin, imgout], res in batch.map(items):
        res.outfile = imgout
        yield imgin, res


def avifconv_args(scriptname, *args):
    scriptname = pth.Path(scriptname).name

    p = argparse.ArgumentParser(
        prog=scriptname,
        description=__doc__,
        usage=None,     # auto-generated by default
        epilog=None,    # Text at the bottom of help
    )

    p.add_argument('-j', '--jobs',
        dest='nproc', default=0, type=int,
        help='Number of parallel jobs to run (0 means auto)')

    p.add_argument('-s', '--speed',
        default=4, type=int,
        help='Processing speed (0 to 10), affects quality')
    
    p.add_argument('-t', '--qual',
        default=68, type=int,
        help='Target quality (0 to 100)')
    
    p.add_argument('-l', '--minqual',
        default=36, type=int,
        help='Lower quality bound for encoder (0 to 100)')
    
    p.add_argument('-u', '--maxqual',
        default=94, type=int,
        help='Upper quality bound for encoder (0 to 100)')
    
    p.add_argument('-p', '--sharpness',
        default=4, type=int,
        help='Bias towards sharpness (0 to 7)')

    multi = '\nCan be used many times for multiple key-value pairs'
    p.add_argument('-E', metavar='EXTRA', dest='avifenc_extra',
        nargs=1, action='append',
        help='"key" or "key=value" for extra avifenc args.' + multi)
    
    p.add_argument('-C', metavar='CODECEXTRA', dest='codec_extra',
        nargs=1, action='append',
        help='"key" or "key=value" for extra codec args (passed with -a).' + multi)
    
    p.add_argument('images',
        nargs='+', metavar='..IMAGES', type=pth.Path,
        help='Input images to be converted')

    parsed = p.parse_args(args)

    def getextra(vals):
        ext = [] if vals is None else [val[0] for val in vals]
        extra = {}
        for v in ext:
            key, *other = v.split('=', maxsplit=1)
            value = other[0] if other else None
            extra[key] = value
        return extra

    parsed.avifenc_extra = getextra(parsed.avifenc_extra)
    parsed.codec_extra = getextra(parsed.codec_extra)

    return parsed


if __name__ == '__main__':
    import shutil
    import sys
    import textwrap
    termw, _ = shutil.get_terminal_size()
    termw = termw - 8 if termw >= 80 else 80 - 8

    cmprs = []
    parsed = avifconv_args(*sys.argv)
    imlen = len(parsed.images)
    decim = len(f'{imlen}')
    for i, (img, res) in enumerate(avifconv(**vars(parsed)), start=1):
        out = res.stdout.rstrip()
        out = textwrap.fill(out, width=termw,
            drop_whitespace=False, replace_whitespace=False)
        print(textwrap.indent(out, '\t'))
        res.check_returncode()
        szorig, sznew = [i.stat().st_size for i in [img, res.outfile]]
        cmpr = 100 * (sznew / szorig)
        cmprs.append(cmpr)
        msg = f'[{i:>{decim}}/{imlen}]'
        msg += f' {img} -> {res.outfile.name} ({sznew} B) [{cmpr:.2f}%]'
        print(msg)

    avgcmpr = sum(cmprs) / len(cmprs)
    print(f'DONE {len(cmprs)} files. AVG SIZE [{avgcmpr:.2f}%] orig')
