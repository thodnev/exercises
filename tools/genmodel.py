from datamodel_code_generator import (
    InputFileType,
    DataModelType,
    PythonVersion,
    generate as datamodel_codegen)
from dataclasses import dataclass, field
import datetime as dt
import functools
import itertools
import pathlib as pth
import re
import tempfile
from typing import Iterable, get_type_hints

type AnyPath = pth.Path | str

class ModelError(Exception):
    pass

def get_model_raw(schema_file: AnyPath, **kwargs) -> str:
    """Creates model from `schema_file` using datamodel_code_generator

    Note:
        datamodel_code_generator originally only outputs to files,
        so we need to wrap its logic with TemporaryFile

    Returns:
        model code as string
    """
    tmp = tempfile.NamedTemporaryFile(prefix='tmp_codegen_')
    opts = dict(
        input_file_type=InputFileType.JsonSchema,
        output_model_type=DataModelType.DataclassesDataclass,
        output=pth.Path(tmp.name),
        target_python_version=PythonVersion.PY_313,
    )
    opts.update(kwargs)

    # Ensure correct types. codegen lib is unable to handle strings
    typemap = get_type_hints(datamodel_codegen)
    for k in opts:
        try:
            cls = typemap[k]
            opts[k] = cls(opts[k])
        except Exception:
            pass
    
    try:
        datamodel_codegen(schema_file, custom_file_header=' ', **opts)

        ret = open(tmp.name).read()
    except Exception as exc:
        raise ModelError('Unable to generate model') from exc
    finally:
        tmp.close()

    ret = ret.lstrip()
    return ret


@dataclass
class FileHeaders:
    PREFIX = '# '
    HDR_RE = re.compile(fr'^([\w-]+):\s*?(\S.+)\s*?$')
    headers: dict[str, str] = field(default_factory=dict)
    comments: list[str] = field(default_factory=list)

    def dump(self, *, extra_headers: dict[str, str] | None = None):
        hdr = dict(self.headers)
        if extra_headers is not None:
            hdr.update(extra_headers)

        items = [f'{key}: {value}' for key, value in hdr.items()]
        items += self.comments
        prefixed = [self.PREFIX + val for val in items] 
        return '\n'.join(prefixed)
    
    def load(self, lines: Iterable[str]):
        for line in lines:
            if not line.startswith(self.PREFIX):
                raise ModelError(f'Line "{line}" must start with "{self.PREFIX}"')
            # strip prefix
            line = line.split(self.PREFIX, maxsplit=1)[-1]

            hdr_match = self.HDR_RE.match(line)
            if hdr_match:
                k, v = hdr_match.groups()
                self.headers[k] = v
            else:
                self.comments.append(line)


@dataclass
class TimedHeaders(FileHeaders):
    updated_at: dt.datetime | None = None
    checked_at: dt.datetime | None = None

    @staticmethod
    def time_format(time: dt.datetime | None = None) -> str:
        time = time or dt.datetime.now()    # current time if empty
        time = time.astimezone(dt.UTC)   # avoid leaking TZ
        return time.isoformat(' ', 'seconds')
    
    @staticmethod
    def time_parse(val: str) -> dt.datetime:
        time = dt.datetime.fromisoformat(val)
        time = time.astimezone(tz=None)     # local timezone
        time = time.replace(tzinfo=None)    # drop timezone info
        return time

    def dump(self, *, extra_headers: dict[str, str] | None = None):
        hdr = dict()
        
        for name in 'updated-at', 'checked-at':
            itm = getattr(self, name.replace('-', '_'))
            if itm is not None:
                hdr[name] = self.time_format(itm)
        
        if extra_headers is not None:
            hdr.update(extra_headers)
        
        return super().dump(extra_headers=hdr)
    
    def load(self, lines: Iterable[str]):
        super().load(lines=lines)

        for name in 'updated-at', 'checked-at':
            itm = self.headers.pop(name, None)
            if itm is not None:
                itm = self.time_parse(itm)
            setattr(self, name.replace('-', '_'), itm)


DEF_COMMENTS_TPL = (
    "This file is autogenerated using {thistool}\n"
    "from {schema_file}\n"
    "\n"
)

class SchemaModel:
    schema_file: pth.Path
    model_file: pth.Path
    model_data: str | None = None
    headers: TimedHeaders

    def __init__(self, schema_file: AnyPath, model_file: AnyPath):
        self.schema_file = pth.Path(schema_file)
        self.model_file = pth.Path(model_file)
        self.headers = TimedHeaders()

    def get_model_data(self, **extra_codegen):
        data = get_model_raw(self.schema_file,
            # capitalise_enum_members=True,
            # class_name='BaseModel',
            **extra_codegen)

        data = re.sub(
            r'^(\s+)None_?Type_None(\s+=)',
            r'\1NONE\2',
            data,
            flags=re.MULTILINE | re.IGNORECASE)

        return data

    def load(self):
        with open(self.model_file) as f:
            text = f.read()
        lines = text.splitlines()
        is_comment = lambda el: el.startswith('#')
        hdrs = list(itertools.takewhile(is_comment, lines))
        lines = lines[len(hdrs):] + ['']

        self.headers = TimedHeaders()
        self.headers.load(hdrs)
        self.model_data = '\n'.join(lines)

    def save(self):
        with open(self.model_file, 'w') as f:
            hdr = self.headers.dump()
            f.write(hdr + '\n')
            f.write(self.model_data or '')

    def _build_comments(self, comments_tpl: str, **extra_fields):
        schema = self.schema_file
        schema = schema.relative_to(schema.parent.parent)

        tool = pth.Path(__file__)
        tool = tool.relative_to(tool.parent.parent)

        res = comments_tpl.format(schema_file=schema, thistool=tool, **extra_fields)
        return res.splitlines()

    # TODO: regenerate on comments change,
    #       detect using comments_tpl = None default  
    def regenerate(self, *,
            comments_tpl: str = DEF_COMMENTS_TPL,
            renew_checked_at: bool = True,
            **extra_codegen):
        tnow = dt.datetime.now()
        needs_regen = False
        try:
            self.load()         # load old model
        except FileNotFoundError:
            pass    # will match needs_regen below anyway
        new_data = self.get_model_data(**extra_codegen)
        needs_regen = self.model_data != new_data
        if needs_regen:
            self.model_data = new_data
            self.headers.updated_at = tnow
            self.headers.checked_at = None if self.headers.checked_at is None else tnow
            self.headers.comments = (self.headers.comments
                or self._build_comments(comments_tpl=comments_tpl))
        if renew_checked_at:
            self.headers.checked_at = tnow
        
        if needs_regen or renew_checked_at:
            self.save()
        
        return needs_regen  # whether was regenerated completely


if __name__ == '__main__':
    schema = 'deps/free-exercise-db/schema.json'
    model = './model.py'

    m = SchemaModel(schema, model)
