from . import base
import functools
import pathlib as pth
import pydantic_core
import pydantic as pd
import shutil

class Exercise(base.Model):
    path: pth.Path = pd.Field(exclude=True)

    @classmethod
    def from_json_file(cls, file: pth.Path | str, *, strict=True):
        file = pth.Path(file)
        with open(file, 'rb') as f:
            raw = f.read()

        b_exc = base.Model.model_validate_json(raw, strict=strict)
        b_exc.id = file.parent.name 
        exc = cls(**b_exc.model_dump(), path=file.parent)
        return exc
    
    def rename(self, new_name: str):
        assert self.path is not None, 'Exercise base dir unset'
        new_dir = self.path.with_name(new_name)
        shutil.move(self.path, new_dir)
        self.path = new_dir
        return self


if __name__ == '__main__':
    import pathlib as pth
    import pydantic_core
    print('DEV', str(pth.Path('.').absolute()))

    exc_json = pth.Path('build/exercises/machine_bicep_curl/data.json')
    exc = Exercise.from_json_file(exc_json)