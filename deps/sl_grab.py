#!/usr/bin/env python3
"""
We want to compute some metrics based on data, provided openly and 
widely accessible on the [SL] website. Then we would like to incorporate
the evaluated metrics into our dataset.
But script needs to be neat to ensure it is within the legal & ethical field.

Script makes request on behalf of a user to the [SL] website and downloads
the raw dataset file from it. Which is then filtered to remove all unneeded
stuff and used to evaluate the data metrics we need.
"""

# NOTICE:

from collections.abc import Iterable
import codecs
from dataclasses import dataclass
import datetime as dt
import json
import math
import pathlib as pth
from rapidfuzz.distance.DamerauLevenshtein import normalized_similarity
from typing import Self
import urllib.parse
from urllib.request import Request, urlopen

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml import YAML as _YAML
yaml = _YAML()

SCRIPT_ROOT = pth.Path(__file__).parent


class DatasetError(Exception):
    pass


class WebData:
    EULA = __doc__ or ''  # module docstring
    EULA += '\n\nTo accept & confirm downloading dataset, enter YES below.'

    # We can't store website in text form as-is, because the name itself
    # may be copyright-protected. So instead, we compute it on-the-fly
    # algorithmically from a [ROT13 then Base64] form below.
    # See `enc_unwrap` on more details how it is done
    WEBSITE_ENC = 'ZmdlcmF0Z3V5cmlyeS5wYno='

    # This is where request is made to download the file
    PUBLIC_ENDPOINT = (R'https://{WEBSITE}/api/exercises?limit={limit}'
                       R'&exercise.fields={fields}'
                       R'&standard={standard}')

    STANDARD_FIELDS = ('category', 'name_url', 'bodypart', 'count', 'aliases', 'icon_url')
    # There is also 'images' field. We don't want the order and field set
    # to be different from what the website itself uses publically.
    # At the moment, there are known to be ~287 standard exercises
    # and ~1031 non-standard
    # But only the standard ones have data we need for computing the metrics.
    # Also website own public requests are always made as standard.

    # This is how much limit inceases at a time
    # Website accesses its data gradually, computing `limit` as:
    # limit = LIMIT_STEP * ceil(N / LIMIT_STEP)
    LIMIT_STEP = 32
    # thus 288 is maximum request

    HEADERS = {
        # Latest Chrome on Linux
        'User-Agent': (R'Mozilla/5.0 (X11; Linux x86_64) '
                       R'AppleWebKit/537.36 (KHTML, like Gecko) '
                       R'Chrome/128.0.0.0 Safari/537.36'),
        'Accept':   R'application/json, text/plain, */*',
        'Referer':  R'https://{WEBSITE}/strength-standards'
    }

    # Where raw dataset is stored by default
    DEF_RAW_PATH = SCRIPT_ROOT.joinpath('sl_raw_dataset.yml')

    @staticmethod
    def enc_unwrap(encstr: str) -> str:
        """Reconstructs string from its [ROT13 then Base64] form."""
        # our encstr is Base64[ ROT13[ original ] ]
        rot = encstr.encode('ascii')    # str -> bytes
        rot = codecs.decode(rot, 'base64')       # unwrap outer algo
        rot = rot.decode('ascii')       # bytes -> str
        res = codecs.decode(rot, 'rot13')        # unwrap inner algo
        return res

    def __init__(self, raw_path=SCRIPT_ROOT.joinpath('sl_raw_dataset.yml')):
        self.website = self.enc_unwrap(self.WEBSITE_ENC)
        self.HEADERS = {k: v.format(WEBSITE=self.website) for k, v in self.HEADERS.items()}
        self.raw_path = pth.Path(raw_path)

    def get_url(self, limit: int, *,
                fields: Iterable[str] = STANDARD_FIELDS,
                isstandard: bool = True) -> str:
        """Builds url for dataset retreival with the given parameters."""
        assert limit > 0

        limit = self.LIMIT_STEP * math.ceil(limit / self.LIMIT_STEP)

        url = self.PUBLIC_ENDPOINT.format(
            WEBSITE=self.website,
            limit=limit,
            standard='true' if isstandard else 'false',
            fields=','.join(fields)
        )
        return url

    def request(self, limit: int, **kwargs):
        """Makes request to website, retreiving dataset."""
        url = self.get_url(limit=limit, **kwargs)
        req = Request(url, headers=self.HEADERS)
        with urlopen(req) as resp:
            assert resp.getcode() == 200
            data = json.load(resp)
            return data

    def get_data(self, limit: int = 287):
        """Acquires raw dataset from website."""
        assert limit >= 0
        getfull = (limit == 0)
        if getfull:  # try finding how much there is available
            data = self.request(limit=64)  # as much as website asks
            limit = data['meta']['count']

        data = self.request(limit=limit)
        res = self._data_transform(data)
        if getfull:
            assert len(res) == data['meta']['count']
        return res

    @staticmethod
    def relative_url(url: str) -> str:
        """Makes relative url from absolute."""
        parts = urllib.parse.urlparse(url)
        relparts = parts._replace(scheme='', netloc='')
        relurl = urllib.parse.urlunparse(relparts)
        return relurl

    @classmethod
    def _entry_reconstruct(cls, entry: dict) -> tuple[str, dict]:
        """Transforms individual entry of raw dataset."""
        res = {}
        res['name'] = entry['name']
        if entry['aliases']:
            res['altnames'] = list(entry['aliases'])
        res['number'] = entry['count']
        res['category'] = entry['category']
        res['muscles'] = entry['bodypart']
        res['icon_url_rel'] = cls.relative_url(entry['icon_url'])

        slid = entry['name_url']
        return slid, res

    @classmethod
    def _data_transform(cls, data: dict) -> dict:
        """Transforms raw dataset into stored form."""
        res = dict()
        entries = data['data']
        for entry in entries:
            slid, ent = cls._entry_reconstruct(entry)
            res[slid] = ent

        # now sort it by slid
        res = {k: res[k] for k in sorted(res)}
        return res

    def ensure_raw_exists(self, *,
        force: bool = False, eula_autoaccept: bool = False):
        """Downloads raw dataset (as needed), storing it on disk."""
        file = self.raw_path
        if file.exists() and not force:
            print(f'Using existing raw dataset from {file}')
            return True

        if not eula_autoaccept:  # show request to the user
            print(self.EULA)
            resp = input('Begin download? [YES/NO]: ')
            resp = resp.lower()
            if resp not in ['yes', 'no']:
                raise DatasetError('Only YES/NO are accepted')
            if resp != 'yes':
                raise DatasetError('EULA rejected')
        else:
            print('EULA accepted explicitly')

        # file needs downloading
        data = self.get_data(limit=0)  # get everything
        data = CommentedMap(data)

        tnow = dt.datetime.now(dt.UTC)
        tnow = tnow.isoformat(' ', timespec='minutes')
        msg = f'updated-at: {tnow}'
        msg += f'\nexercises: {len(data)}'
        data.yaml_set_start_comment(msg)

        with open(file, 'w') as f:
            yaml.dump(data, stream=f)
        print(f'Raw dataset written to {file}')
        return False


@dataclass
class ExerciseCmp:
    """Abstraction over exercise compared between datasets."""
    id: str
    name: str
    altnames: tuple[str] = tuple()

    @property
    def names(self):
        yield self.name
        yield from self.altnames

    def find_matching(self, others: Iterable[Self], *, limit=None):
        """Finds similar entries in other dataset.
        Uses Damerau-Levenshtein string distance as similarity index.
        """
        cmp = normalized_similarity
        pairs = []
        for other in others:
            sim = [[cmp(str(my).lower(), str(oth).lower()), oth] for my in self.names for oth in other.names]
            bestsim, othname = max(sim)
            pair = bestsim, other, othname
            if bestsim >= 1:        # a perfect match
                return (pair, )     # no need for more
            pairs.append(pair)
        
        pairs.sort(key=lambda p: p[0], reverse=True)
        pairs = pairs[:limit]       # strip unneeded
        return tuple(pairs)


if __name__ == '__main__':
    site = WebData()
    site.ensure_raw_exists()
    with open(site.raw_path) as rawf:
        data = yaml.load(rawf)
        data = dict(data)

    sldb = [ExerciseCmp(id=k, name=v['name'], altnames=v.get('altnames', tuple()))
            for k, v in data.items()]

    import json
    freedb = SCRIPT_ROOT.joinpath('free-exercise-db/dist/exercises.json')
    with open(freedb) as file:
        freedb = json.load(file)

    freedb = [ExerciseCmp(id=e['id'], name=e['name'])
              for e in freedb]
    print('FreeDB transformed')


    res = []
    for item in sldb:
        matches = item.find_matching(freedb, limit=3)
        m = [item]
        for k, itm, name in matches:
            m.append([k, itm])
        res.append(m)
    res.sort(reverse=True, key=lambda v: v[1][0])


    with open('dataset.csv', 'w') as outf:
        for item, *matches in res:
            ent = f'{item.id}'
            for k, itm in matches:
                ent += f'\t{k}\t{itm.id}'
            outf.write(ent + '\n')
            print(ent)
            

