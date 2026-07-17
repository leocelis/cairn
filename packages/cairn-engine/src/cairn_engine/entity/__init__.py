"""The entity subsystem: model, resolution, ontology authoring, traversal.

Module map:
  model.py     — the immutable Entity value record + Ref/Relation/ResolvedEntity (M1.1)
  resolve.py   — deterministic resolution cascade (OP-28, TH-1)          [M1.2]
  ontology.py  — build-time alias-table authoring + dedup (OP-35, TH-1)  [M1.3]
  traverse.py  — bounded relation closure (OP-34, TH-4)                  [M1.4]

model.py is real (schema is specified by OP-35). The three algorithm modules are
scaffolded stubs — their logic is authored in the core/entity module intent
(tech-spec phase), per IVD Rule 1 (intent before implementation).
"""
