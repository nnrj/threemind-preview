"""Immutable, portable body + consciousness candidates; annotations never enter Core."""
from __future__ import annotations

import hashlib
import io
import json
from uuid import uuid4
import zipfile

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from threemind_runtime.codec import ArtifactCodec
from .database import NotFound

MAX_BYTES = 64 * 1024 * 1024
SCHEMA = 'threemind.species-asset/1'


class Manifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_id: str = Field(alias='schema')
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default='', max_length=20000)
    kernel_id: str
    state_hash: str
    adapter: str
    mapping_seed: int
    body: dict
    traits: dict
    environment_protocol: dict
    source: dict
    evidence: list[dict] = Field(default_factory=list, max_length=100)
    qualification: str = 'candidate'
    lineage: list[dict] = Field(default_factory=list, max_length=100)
    reuse: str = 'inherit-structure-and-body; clear-activity; explicit-energy-endowment'


def inspect_bundle(raw: bytes):
    if len(raw) > MAX_BYTES:
        raise ValueError('物种包超过 64 MiB。')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            if len(entries) != 2 or {e.filename for e in entries} != {'manifest.json', 'consciousness.tmind'}:
                raise ValueError('物种包只允许 manifest.json 和 consciousness.tmind。')
            if sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError('解压后的物种包超过 64 MiB。')
            m = Manifest.model_validate_json(z.read('manifest.json'))
            image = ArtifactCodec.decode(z.read('consciousness.tmind'), max_bytes=MAX_BYTES)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError('无效的物种包。') from exc
    if m.schema_id != SCHEMA or m.qualification not in {'candidate', 'replicated'}:
        raise ValueError('未知的物种包协议或证据状态。')
    if not m.name.strip() or m.state_hash != image.digest:
        raise ValueError('名称为空或意识状态与清单不符。')
    json.dumps(m.model_dump(by_alias=True), allow_nan=False)
    if m.reuse != 'inherit-structure-and-body; clear-activity; explicit-energy-endowment':
        raise ValueError('未知的物种复用规则。')
    # Decode validates the versioned state. Never relabel its kernel identity.
    from threemind_runtime import create_engine
    create_engine(state=image, backend='reference')
    if m.kernel_id != image.to_dict()['dynamics']:
        raise ValueError('物种包的内核身份不一致。')
    if m.qualification == 'replicated' and not m.evidence:
        raise ValueError('重复验证状态必须附证据；证据结论仍需研究者审查。')
    return m.model_dump(by_alias=True), image


def pack(manifest: dict, image) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, allow_nan=False))
        z.writestr('consciousness.tmind', ArtifactCodec.encode(image))
    raw = target.getvalue()
    inspect_bundle(raw)
    return raw


def put(database, project, actor, raw):
    manifest, _ = inspect_bundle(raw)
    digest = hashlib.sha256(raw).hexdigest()
    with database.tx(project) as db:
        row = db.execute('SELECT id FROM species_assets WHERE bundle_hash=%s', (digest,)).fetchone()
        if not row:
            identity = uuid4()
            db.execute('INSERT INTO species_assets(id,project_id,actor_id,name,bundle_hash,manifest,bundle) '
                       'VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(project_id,bundle_hash) DO NOTHING',
                       (identity, project, actor, manifest['name'], digest, Jsonb(manifest), raw))
            row = db.execute('SELECT id FROM species_assets WHERE bundle_hash=%s', (digest,)).fetchone()
    return get(database, project, row['id'])


def get(database, project, identity, *, raw=False):
    fields = 'bundle' if raw else 'id,name,manifest,bundle_hash,created_at,octet_length(bundle) AS bytes'
    with database.tx(project) as db:
        row = db.execute(f'SELECT {fields} FROM species_assets WHERE id=%s', (identity,)).fetchone()
    if row is None:
        raise NotFound()
    return bytes(row['bundle']) if raw else row


def listing(database, project, query='', offset=0, limit=30):
    with database.tx(project) as db:
        return db.execute('SELECT id,name,manifest,bundle_hash,created_at,octet_length(bundle) AS bytes '
                          'FROM species_assets WHERE name ILIKE %s ORDER BY created_at DESC,id '
                          'OFFSET %s LIMIT %s', ('%' + query + '%', offset, limit)).fetchall()
