from datamodel_code_generator import (
    InputFileType,
    DataModelType,
    PythonVersion,
    generate as datamodel_codegen)
from dataclasses import dataclass, field
import datetime as dt
import functools
import pathlib as pth
import re
import tempfile
from typing import Iterable

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
    try:
        datamodel_codegen(
            schema_file,
            input_file_type=InputFileType.JsonSchema,
            output_model_type=DataModelType.DataclassesDataclass,
            output=pth.Path(tmp.name),
            custom_file_header=' ',
            target_python_version=PythonVersion.PY_313,
            **kwargs
        )

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


class SchemaModel:
    schema_file: pth.Path
    model_file: pth.Path
    model_data: str
    headers: Iterable

    def __init__(self, schema_file: AnyPath, model_file: AnyPath):
        self.schema_file = pth.Path(schema_file)
        self.model_file = pth.Path(model_file)
    
    def load_model(self):
        with open(self.model_file) as f:
            lines = f.readlines()

    def generate(self):
        data = get_model_raw(self.schema_file,
            capitalise_enum_members=True,
            class_name='BaseModel')

        data = re.sub(
            r'^(\s+)None_?Type_None(\s+=)',
            r'\1NONE\2',
            data,
            flags=re.MULTILINE | re.IGNORECASE)

        with open(self.model_file, 'w') as out:
            out.write(data)

        return data




if __name__ == '__main__':
    schema = 'deps/free-exercise-db/schema.json'
    model = './model.py'

    m = SchemaModel(schema, model)
