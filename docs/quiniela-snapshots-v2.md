# Structural v2 laboratory and run snapshots

`domain/configurable_laboratories.py` provides strict immutable value codecs.
It exposes **no laboratory persistence or execution endpoint** at Q1.
All mappings require their complete field set and integer `schema_version:2`.
Factories create fresh laboratory UUID4 identities; profile/source identities are
retained. Snapshot round trips detach nested input arrays and dictionaries.

## Definition

`{schema_version,id,name,reference_id,config}` embeds the complete configuration:

- `profile`: the complete immutable v2 profile, including rules and identity.
- `source`: `{schema_version,id,sha256,profile_sha256,origin,raw_sha256,rankings_sha256}`.
  UUID/hash syntax is validated and its profile digest must match the embedded
  profile. Origins are `included`/`imported`; imported sources cannot claim a
  ranking digest. Hash strings alone do **not** establish source provenance.
- `strategy`: `{schema_version,selection,stake,close}`. Each block is
  `{schema_version,role,kind,version,parameters}`, currently block version1.
  Selection kinds: `manual`, `parity`, `archived-ranking`, `archived-mixture`.
  Stake kinds: `fixed`, `flat`, `bold`, `ladder`; close kind: `goal-or-ruin`.
  Parameters are immutable bounded exact JSON: depth<=8, <=2000 nodes,
  <=64 keys/object, <=1000 array elements, <=512 UTF-8 bytes/string,
  signed JavaScript-safe integers, strings/bools/null; no floats/code objects.
- `conditions`: `{schema_version,capital,goal,window}` with exact positive money,
  goal>capital and a validated inclusive UTC v2 window. Initial capital funds at
  least one profile minimum stake; compilation checks actual coverage/exposure.

Known block names do not prove valid parameters, causal selection or compatibility.
The Q3 catalog/compiler must validate each block's exact parameter schema and
source/profile capabilities. The Q5 service must verify stored source ownership,
content hashes and provenance before executable persistence. Structural factories
are deliberately not a shortcut around those admissions.

## Run snapshot

`{schema_version,kind,definition,engine_version,profile_sha256,strategy_sha256,history_sha256}`
uses kind `configurable_quiniela_run`. It contains the entire definition, not just
an ID. Profile/strategy digests cover sorted-key compact UTF-8 JSON of their full
mappings; history digest equals the source reference's canonical content digest.
Readers reject mismatched hashes, unknown fields and unsupported schemas rather
than guessing a missing rule. The engine version is bounded explicit metadata;
Q4 admission additionally selects a supported implementation, never executable
code supplied by a client. Source rows and archived matrices are verified by the
service, not inferred from matching date labels. This does not yet prove that a
run exists, completed, has a full trace or reproduces a historical result.
