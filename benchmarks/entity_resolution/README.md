# Entity-resolution grounding benchmark

**Does feeding a consumer Cairn's deterministic resolution raise the rate at
which it acts on the *correct* canonical entity id?**

**Result (deterministic, reproducible): correct-id accuracy `59% → 100%` — every
error eliminated.** With a model in the loop (single run, `gpt-4o-mini`, temp 0):
`54% → 90%`, 80% of errors eliminated. Full method, dataset, and reproduction below.

> Scope, up front: this measures the **entity-resolution step** — producing the
> right stored id for a referenced entity. It is *not* a claim about end-to-end
> RAG answer quality (that is the separate OP-31 eval, still pending — see the
> repo `ROADMAP.md`). The dataset is **fully synthetic and public**; no real,
> private, or personal data is used.

---

## Motivation — derive vs. look up

An agent, pipeline, or tool that must act on an entity referenced by name needs
its **stored canonical id** (a slug, a ticker, a key). Without a resolver, the
only option is to **derive** the id from the name — `slugify(name)`, or an LLM
guessing it. Derivation works right up until the stored id isn't a clean function
of the current name, which every real datastore accumulates:

- **legacy / abbreviated / renamed ids** — `"Hooli Networks"` stored as `hooli-net`,
  `"Stark Industries LLC"` as `stark`. `slugify` produces `hooli-networks` / `stark-industries-llc` → **miss**.
- **punctuation / accents** — `"Renée Dubois"` → naive slug keeps the accent
  (`renée-dubois`); an LLM often drops the apostrophe in `"Sam O'Brien"` (`sam-obrien`) → **miss**.
- **hallucination** — asked to resolve an unfamiliar ticker with no grounding, a
  model may invent an id outright (we observed `"HOOL" → "12345"`).

A **lookup** — `resolve(name) → id` over a frozen alias table — is immune to all
three: every surface form of an entity maps to the one stored id, or to an
explicit "unresolved" (closed world), never a wrong or invented id.

## Task & metric

For each item: given the reference (a name or ticker), output the **stored
canonical id**. Ground truth is known (we built the dataset), so scoring is
**exact match**. Metric: correct-id accuracy, and errors eliminated
(`errors_baseline − errors_cairn`).

## Dataset

`benchmark.py :: DATASET` — 22 items, fully synthetic and public (classic
fictional companies — Contoso-style — and generic names), across five categories
chosen to mirror real datastore conditions:

| category | n | what it tests |
|---|---|---|
| company: clean id | 5 | stored id **is** a clean slugify of the name (control) |
| company: irregular id | 7 | stored id is legacy/abbreviated — **not** re-derivable |
| person: clean id | 4 | `first-last` slug matches the name (control) |
| person: punctuation/accents | 3 | apostrophes / accented characters |
| stock: ticker | 3 | referenced by ticker (control) |

The controls exist to prove the benchmark is not rigged: on cases the baseline
already gets right, Cairn must not regress.

## Method

Two resolvers, same items, exact-match scoring:

- **Baseline** — derive the id: `slugify(name)` (the standard non-resolver
  approach; mirrors what application code and agents do today). With `--llm`, a
  real model produces the id instead.
- **Cairn** — `resolve(name)` over an `InMemoryAliasTable` built from a small
  human-approved ontology (canonical id + the surface forms that mean it). With
  `--llm`, the model is handed Cairn's resolved candidate(s) and picks one.

Same items and same model on both arms. The deterministic mode makes **zero LLM
and zero network calls** and is byte-stable — reproducible by anyone.

## Reproduce

```bash
pip install cairn-engine
cd benchmarks/entity_resolution

python benchmark.py            # deterministic, no API key, byte-stable
python benchmark.py --llm      # optional: model in the loop (needs OPENAI_API_KEY)
```

## Results

### Deterministic (canonical, byte-stable)

```
category                        n    baseline     + Cairn
company: clean id               5  5/5 = 100%  5/5 = 100%
company: irregular id           7  0/7 =   0%  7/7 = 100%
person: clean id                4  4/4 = 100%  4/4 = 100%
person: punctuation/accents     3  1/3 =  33%  3/3 = 100%
stock: ticker                   3  3/3 = 100%  3/3 = 100%
--------------------------------------------------------
OVERALL                        22  13/22 = 59%  22/22 = 100%
```
**59% → 100% correct-id accuracy; 9 → 0 errors (100% eliminated).**

### Model in the loop — `gpt-4o-mini`, temp 0 (single run, indicative)

```
category                        n    baseline     + Cairn
company: clean id               5  5/5 = 100%  5/5 = 100%
company: irregular id           7  0/7 =   0%  5/7 =  71%
person: clean id                4  4/4 = 100%  4/4 = 100%
person: punctuation/accents     3  2/3 =  66%  3/3 = 100%
stock: ticker                   3  1/3 =  33%  3/3 = 100%
--------------------------------------------------------
OVERALL                        22 12/22 =  54%  20/22 =  90%
```
**54% → 90%; 10 → 2 errors (80% eliminated).** Honestly, not 100%: even handed the
right candidate, the model occasionally ignored it (2 misses) — a reminder that
Cairn removes the *resolution* error, not the model's own disobedience.

## Interpretation

- The gain is **concentrated where a resolver is required** — irregular/legacy
  ids (`0% → 100%`), accents/punctuation, and (with a model) hallucinated ids.
- **Controls tie** (clean ids, tickers): Cairn adds nothing where derivation
  already works, and never regresses. That is the fairness check.
- The headline is **error elimination**, not a raw multiplier: the deterministic
  resolver produces the correct id every time; a naive derivation cannot, by
  construction, on non-derivable ids.

## Caveats

- Measures the **resolution step**, not full downstream answer quality.
- The overall percentage depends on the clean:irregular ratio in the dataset;
  the per-category table is the honest signal, not the single headline number.
- The `--llm` numbers are a **single run** of one small model (temp 0) —
  indicative, not byte-stable. The deterministic result is the reproducible one.

## Files

- [`benchmark.py`](benchmark.py) — the harness (dataset, both resolvers, scoring).
