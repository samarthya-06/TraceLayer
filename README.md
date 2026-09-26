# TraceLayer

Offline Bitcoin investigation proof-of-concept for Smart India Hackathon 2026.
Requires Python 3.11 or newer.

The planned prototype will correlate P2P/network observations (IP, port, timestamp)
with blockchain metadata (TXID, wallet addresses, transaction amounts):

CSV ingestion → validation → cross-layer graph → feature engineering → Isolation
Forest anomaly detection → Bitcoin-pattern detection → risk and confidence scoring
→ ranked investigative leads → Streamlit visualization.

## Phase 6 scope

The synthetic generator, ingestion, evidence graph, wallet features, Isolation
Forest, explainable signals, ranking, and three-tab local interface are implemented.

Generate the dataset and run the standard-library tests:

```sh
python scripts/generate_demo_data.py
python -m unittest discover -s tests -v
```

Optional arguments: `--rows 1000 --seed 42` (the defaults). At least 100 rows are
required so ordinary activity remains the majority. Outputs always go to this
project's `data/` directory, regardless of the current working directory.

The default dataset contains 963 ordinary transactions, five peeling-chain
transactions (six chain wallets, with decreasing continuation amounts), 30 burst
transactions in 58 seconds, and a two-transaction seed-risk path. Timestamps
start at a fixed UTC date and cover seven days. One row represents one synthetic
transaction and its illustrative network observation, not a real P2P capture.

Address and amount columns contain JSON lists. Amount list entries and fees are
exact eight-decimal BTC strings, calculated in integer satoshis; each transaction
balances inputs = outputs + fee. Inputs and outputs have varied counts. This is
not a complete UTXO ledger: ordinary and burst inputs have assumed funding, and
no cryptographic validity, real traffic distribution, or ownership is claimed.

Wallet names and TXIDs are intentionally invalid demo identifiers. IPs are drawn
only from reserved documentation ranges `192.0.2.0/24` and `198.51.100.0/24`.
`data/ground_truth.json` identifies scenario wallets and TXIDs for evaluation
only. Future prediction code must not read it. Generator validation and tests
may use it to check that the intended scenarios were actually written.
Scenario names are transparent fixtures, not features for future detection.
Network observations are investigative clues, not proof of wallet ownership or
transaction origin. No performance metrics or detection claims are made.

This is a small local prototype, not a production system. It uses no cloud APIs,
authentication, external databases, frontend frameworks, orchestration, or workers.
After dependencies are installed, the app is intended to run offline using local
files. The setup step may require internet access or a local package cache.

## Dependencies

- `pandas`: CSV ingestion, validation, and tabular processing.
- `numpy`: numerical calculations and safe missing-value handling.
- `scikit-learn`: Isolation Forest anomaly detection.
- `networkx`: cross-layer graph construction and path queries.
- `streamlit`: three-tab local interactive interface.
- `plotly`: local interactive evidence graph; no hosted plotting service.

Minimum API versions are specified in `requirements.txt`; Pyvis is unnecessary.
Tested on Python 3.14.6 with pandas 3.0.6, numpy 2.5.3, scikit-learn 1.9.1,
NetworkX 3.7, Streamlit 1.64.0, and Plotly 7.1.0. Earlier dependency versions
are not claimed to have been tested; refitting with different versions may alter
the exact anomaly ranking.

## Run (macOS / Linux)

From this project directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --browser.gatherUsageStats=false
```

Use a Python 3.11+ interpreter for `python3`. Open the local URL printed by
Streamlit. Usage statistics are disabled by the launch command above.

## Basic checks

```sh
python -m compileall -q app.py tracelayer scripts tests
python -c "import pandas, numpy, sklearn, networkx, streamlit; import tracelayer.ingestion, tracelayer.graph_builder, tracelayer.features, tracelayer.anomaly, tracelayer.patterns, tracelayer.scoring, tracelayer.pipeline"
```

Tests cover generation, ingestion, graphs, model features, scoring, the pipeline,
and Streamlit rendering and interactions.

## Data Ingestion

`from tracelayer.ingestion import load_case` exposes `load_case(path)`, returning
`(cleaned_dataframe, validation_report)`. The default path is `data/demo_case.csv`.
Addresses and amounts use **JSON arrays**, never pipe-separated strings. Addresses
become Python string lists; amounts and fees become numeric `Decimal` values to
preserve exact BTC arithmetic. Timestamps become UTC datetimes (naive inputs are
interpreted as UTC), and ports become integers. Extra CSV columns are ignored.

Validation checks required fields, IP syntax, port ranges, nonempty aligned lists,
finite positive amounts, nonnegative fees, and transaction balance. Invalid rows
are excluded with reasons and one-based data-record numbers in `row_errors`.
`duplicate_txids` counts occurrences beyond the first nonblank TXID, even in bad
rows. Only the first **valid** occurrence is retained. `missing_required_values`
counts blank required cells, including cells belonging to absent columns.
`total_rows = valid_rows + invalid_rows`; absent required columns reject all rows.
File/parsing failures return an empty frame and `errors` (row counts are unknown
and remain zero); malformed CSV records are not silently skipped.
Ground truth is never read by ingestion.

```sh
python -c "from tracelayer.ingestion import load_case; df, report = load_case(); print(report)"
```

## Cross-layer Evidence Graph

`build_evidence_graph(df)` accepts the cleaned dataframe from `load_case` and
returns a NetworkX `MultiDiGraph`. Node keys are `(node_type, id)` tuples, preventing
IP, TXID, and wallet identifier collisions. Each node has `id`, `node_type`, and
`risk_seed` attributes. Parallel edges preserve repeated addresses and separate
source/destination endpoint observations.

- `IP → TXID`: `associated_with`, with timestamp, port, source/destination role,
  and `evidence_only=True`. This is supporting correlation, never ownership or identity.
- `WALLET → TXID`: `input_to`, with timestamp and exact BTC amount.
- `TXID → WALLET`: `output_to`, with timestamp and exact BTC amount.

`seed_wallet_demo` is a configurable demonstration seed (`seed_wallets` argument),
not a claim about wrongdoing. No graph function reads `ground_truth.json`.
`graph_summary(graph)` counts total nodes/edges and wallet, TXID, and IP nodes.
`get_entity_neighborhood(graph, entity_id, depth=2)` discovers neighbors in either
direction but returns a copy preserving original edge directions. Pass a raw ID
or typed tuple; absent IDs raise `KeyError`, ambiguous raw IDs raise `ValueError`.

`shortest_seed_distance(graph, wallet_id)` follows **only directed blockchain
edges** from seeded wallets. It returns edge count (one wallet-to-wallet transfer
uses two edges), zero for a seed itself, or `None` for absent/unreachable wallets.
IP links never shorten this distance. `blockchain_graph(graph)` exposes that
wallet/TXID-only directed projection for inspection. These paths are structural
transaction associations, not proof that particular coins flowed through a
multi-input transaction; path search does not enforce chronological ordering.

Inspect the planted path from the project directory:

```sh
python -m scripts.inspect_graph
python -m unittest discover -s tests -v
```

This Phase 3 inspection command remains available alongside the later model and UI.

## Wallet features and anomaly detection (Phase 4)

`build_wallet_features(df, graph)` derives one row per wallet. Transaction count
counts distinct TXIDs. Sent/received totals sum that wallet's input/output BTC.
Mean/max transaction amount use the wallet's gross sent + received amount per
transaction (not the whole transaction total or an asserted transfer to one peer).
Counterparties are distinct opposite-side wallets, excluding self; co-occurrence
is not proof of a direct payment. Incoming/outgoing degree count distinct adjacent
transaction nodes, not parallel edges.

Frequency is `(transaction_count - 1) / max(active_span_seconds, 60) * 3600`.
The one-minute floor prevents simultaneous events from causing division by zero.
A singleton has frequency zero and undefined mean inter-transaction gap (`NaN`).
Mean gaps use seconds. Seed distance uses directed blockchain edges and is `NaN`
when unreachable; it is **excluded from the model**, since seed support belongs
to the separate explainable scoring stage.

`fit_anomaly_model(feature_df, contamination=0.05, random_state=42)` fits 200
Isolation Forest trees using only the explicit ten numerical activity features.
IDs, scenario names, and seed metadata are not model inputs. No amount threshold
or scenario-specific rule determines anomaly scores. Non-numeric/nonfinite input
becomes missing, median-imputed per feature (all-missing columns become zero).
Empty, singleton, and entirely identical cases return zero scores and no outliers.

Scikit-learn's `score_samples` is lower for anomalies. We negate it to obtain
`raw_anomaly_score`, then calculate `(raw - min(raw)) / (max(raw) - min(raw))`
within the case. Thus `anomaly_score` ranges from 0 to 1 with higher values more
unusual; a constant range becomes zero. Scores are relative to this case, not
probabilities, and cannot be directly compared across independently fitted cases.
`is_anomaly` uses the model's contamination-based prediction threshold, not a
threshold on the normalized score. The default 0.05 is a demonstration parameter,
not a calibrated real-world anomalous-traffic rate. Fitting and scoring the same
synthetic case demonstrates prioritization, not validated generalization.

```sh
python -m scripts.inspect_anomalies
```

This inspection script prints the top ten predictions **before** opening ground
truth for an evaluation-only rank comparison. The feature/model modules never
read that file. Tests verify unchanged scores after replacing every wallet ID
and seed distance. The generator and model are not tuned to force a planted
wallet into first place.

## Explainable signals and ranked leads (Phase 5)

```sh
python -m tracelayer.pipeline
# Optional: --case path/to/case.csv --output path/to/ranked_leads.csv --contamination 0.05
```

The pipeline loads/validates, builds the graph, derives wallet features, fits
Isolation Forest, finds pattern indicators, scores, and ranks. It writes
`data/ranked_leads.csv` and prints ten leads. CSV `reasons` contain JSON arrays.
Invalid rows remain visible in the validation report; a wholly unusable case
fails with that report. No production module reads ground truth.

The peeling heuristic requires at least three chronological transactions (a
configurable minimum), each with one input and two distinct outputs. One output
must hold at least 80% of output value. Each next input exactly matches the prior
continuation value, and that value decreases by no more than 20% per step.
Ambiguous next steps and cycles stop extension. The longest qualifying chain
provides the reason; its continuation wallets get a binary `peeling_signal` of
1, others 0. This conservative demonstration rule can miss real patterns and
flag ordinary change behavior. It is not a money-laundering conclusion.

Seed support is `1 / (1 + distance / 2)` for reachable wallets, zero otherwise,
where distance counts directed wallet/TXID edges. The seed itself scores 1.
Network paths are excluded. Demo risk is exactly:

`100 * (0.50 * anomaly_score + 0.30 * peeling_signal + 0.20 * seed_proximity_score)`

The constants live in `scoring.py`; they are explanatory demo choices, not fitted
or calibrated probabilities. All wallets remain in the ranking, including low
priority entries. Ties are sorted by entity ID.

Confidence is separate from risk and ignores suspiciousness entirely:
40 points for both network and blockchain evidence, up to 40 points for ten
distinct relevant TXIDs, and up to 20 points for the same IP recurring across
four distinct relevant TXIDs. Specifically, the latter terms are
`40 * min(transaction_count / 10, 1)` and
`20 * min(max_same_ip_distinct_txids_minus_one / 3, 1)`.
`evidence_count` counts distinct relevant transactions. IP/transaction association
counts describe endpoint evidence, not independent packet captures or verified
owners. The synthetic CSV has only one observation row per TXID. Repetition is
therefore across transactions, not independent corroboration of one transaction.

Display confidence as a score out of 100, never as probability of guilt.
Tests check bounds, sorting, counterexamples, identity-independent pattern
matching, confidence independence, and execution with ground-truth reads blocked.

## Local interface (Phase 6)

From a fresh clone, with Python 3.11+ installed:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/generate_demo_data.py
python -m tracelayer.pipeline
streamlit run app.py
```

Dependency installation needs internet access or a preloaded package cache.
After installation, analysis, graph rendering, and UI run locally without cloud
APIs. `.streamlit/config.toml` disables Streamlit usage telemetry and supplies a
simple dark theme. Open the local URL printed by Streamlit; stop with Ctrl+C.

The three tabs are **Case Overview**, **Ranked Leads**, and **Evidence Graph /
Lead Details**. Overview includes case metrics and validation. Ranked Leads has
a minimum-risk filter, literal entity search, selected-lead explanations, and
separate risk/confidence scores. The graph view offers a ranked-wallet selector,
one/two-hop neighborhoods, node inspection, transaction evidence, and IP endpoint
associations. Color/shape distinguishes IP, TXID, and WALLET nodes, with arrows
showing direction. Parallel evidence edges overlap visually but are retained in
the graph. Very large drawings are capped at 180 nearest nodes with an explicit
notice; underlying analysis and evidence tables remain complete.

The UI calls the existing pipeline and caches results by CSV contents. Editing
or regenerating the CSV invalidates the cache. It does not retrain on every
filter change, read ground truth, or duplicate analytics. The UI computes results
in memory; use the pipeline CLI to update `data/ranked_leads.csv` on disk.

## Demonstration result (not a performance benchmark)

On the default seed-42 case, the burst wallet ranks **5th of 645** by Isolation
Forest anomaly score (0.904306), behind four peeling-chain wallets. The model was
not changed to force first place. Predictions were completed before evaluation
labels were opened. The planted peeling amounts are unusual in their own right;
this dataset cannot establish real-world model quality.

Combined demo risk ranks the burst wallet 7th (45.215305/100), with evidence
confidence 86.666667/100. The top wallet is `wallet_peel_02` (risk 80/100,
confidence 48/100). Those different values illustrate evidence strength versus
prioritization, not probabilities of wrongdoing. Future validation would require
more varied ordinary/change-chain activity and independent evaluation cases;
no such performance claim is made here.

## Synthetic evaluation (Phase 7)

Produce predictions first, then run the separate evaluator:

```sh
python -m tracelayer.pipeline
python scripts/evaluate_demo.py
```

The evaluator validates the completed ranked CSV before opening ground truth.
It saves `data/evaluation.json` with input-file SHA-256 fingerprints. Primary
entities are defined as six continuation-chain wallets, the burst source, and
the seed-path target (eight total); supplied seeds and incidental recipients are
not primary targets. A broader all-participant check is reported alongside it.
Cutoffs are `ceil(number_of_ranked_entities * percentage)`. Missing targets stay
in the denominator and are listed; mean rank includes found targets only.

**Synthetic Demo Results:** 645 ranked wallets; top-5% cutoff 33 and top-10%
cutoff 65. Primary Recall@5% and Recall@10% are 8/8 (100%); mean rank is 6.125.
Peeling continuation wallet ranks in chain order: 5, 1, 2, 3, 4, 6. Burst source
rank: 7. Seed-path target rank: 21. No primary targets are missing.
The broader 45-participant check returns 10/45 (22.22%) at both cutoffs.
Incidental one-transaction recipients have little unusual behavior, explaining
why participant-wide recall is much lower. More diverse baselines and independent
cases would be legitimate improvements; copying scenario names into detection
would not be. Neither the model nor weights were changed for these results.

The evaluation measures ranking performance on seeded synthetic scenarios. It is
not evidence of real-world investigative accuracy. This is combined risk-ranking
evaluation, not standalone ML accuracy; the known seed and planted graph/pattern
structure contribute to prioritization. The evaluator cannot independently prove
that an arbitrary supplied prediction CSV matches a ground-truth file; regenerate
the case, pipeline output, and evaluation in order when parameters change.
