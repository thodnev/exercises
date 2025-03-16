from datamodel_code_generator import (
    InputFileType,
    DataModelType,
    PythonVersion,
    generate as datamodel_codegen)
from dataclasses import dataclass
import functools
import pathlib as pth
import re
import tempfile

def get_model(schema_file: pth.Path, **kwargs):
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

        ret = open(tmp.name).read().lstrip()
    finally:
        tmp.close()

    return ret

@dataclass
class SchemaModel:
    schema_file: pth.Path
    model_file: pth.Path

    def __post_init__(self):
        self.schema_file = pth.Path(self.schema_file)
        self.model_file = pth.Path(self.model_file)

    def generate(self):
        data = get_model(self.schema_file,
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
