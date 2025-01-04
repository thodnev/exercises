"""Execute command batch in parallel processes."""

from collections.abc import Callable, Iterable, Mapping
from concurrent import futures
import os
import shutil
import subprocess
from typing import Optional, Any


def is_iter_not_str(val: Any) -> bool:
    return isinstance(val, Iterable) and not isinstance(val, str)


class CommandBatch:
    nproc = os.cpu_count() or 1  # use 1 when undetermined
    arg_fmt = {
        'short': '-{key}',
        'long': ['--{key}={value}'],
        'optshort': ['-{opt}', '{optkey}={optvalue}'],
        'optlong': ['--{opt}', '{optkey}={optvalue}'],
    }

    type ArgFmt = Mapping[str, str | list[str]] | Callable[[str, Optional[str]], Iterable[str]]
    type AnyItem = Any

    def __init__(self, *,
        nproc: Optional[int] = None,
        fmt: ArgFmt = {},
        cmd_item: Optional[Callable[[AnyItem, list[str]], list[str]]] = None,
    ):
        if callable(fmt):                   # it's a function to process each arg entry
            self.format_arg = fmt           # type: ignore
        else:                               # it's a pair of (arg_fmt, kwarg_fmt)
            self.arg_fmt = dict(self.arg_fmt)
            self.arg_fmt.update(fmt)

        if cmd_item is not None:
            self.cmd_item = cmd_item        # type: ignore

        self.nproc = nproc or self.nproc

    def format_arg(self, key: str, value: Optional[str] = None) -> Iterable[str]:
        """Formats single argument.
        Returns:
            entries to extend the cmd
        """

        def tolst(v):
            return v if is_iter_not_str(v) else [v]

        # select short/long and ensure they're iterables
        fmts = tolst(self.arg_fmt['short'] if len(key) <= 1 else self.arg_fmt['long'])
        opts = tolst(self.arg_fmt['optshort'] if len(key) <= 1 else self.arg_fmt['optlong'])

        if isinstance(value, Mapping):  # that's advanced opts options
            ret = []
            for kk, vv in value.items():
                opt = [o.format(opt=key, optkey=kk, optvalue=vv) for o in opts]
                ret.extend(opt)
            return ret
        # that's single option
        v = value if value is not None else ''
        ret = [f.format(key=key, value=v) for f in fmts]
        if value is None:  # filter empty
            ret = list(filter(len, ret))
        return ret

    def cmd_set(self, prog: str, args: Mapping = {}):
        """Sets the basic command-line.
        Args:
            prog: executable
            args: basic arguments in form of {key: value} or {key: None}
        """
        prog = shutil.which(prog) or prog       # resolve executable
        cmd = [prog]

        args = dict(args)
        for key, value in args.items():
            cmd.extend(self.format_arg(key=key, value=value))

        self.cmd = cmd

    def cmd_item(self, item: AnyItem, cmd_base: list[str]) -> list[str]:
        """Adapts basic command made by `cmd_set` to process `item`"""
        cmd = list(cmd_base)
        ent = list(item) if is_iter_not_str(item) else [str(item)]
        cmd.extend(ent)
        return cmd

    def run_item(self, item: AnyItem):
        cmd = self.cmd_item(item, self.cmd)

        res = subprocess.run(cmd, capture_output=True, text=True)
        return res

    def map(self, items: Iterable[AnyItem], *, isordered: bool = False):
        items = list(items)
        with futures.ProcessPoolExecutor(max_workers=self.nproc) as exec:
            if isordered:
                return zip(items, exec.map(self.run_item, items))

            futs = {exec.submit(self.run_item, item): item for item in items}
            for fut in futures.as_completed(futs):
                exc = fut.exception()
                if exc is not None:
                    raise exc
                res = fut.result()
                yield futs[fut], res
