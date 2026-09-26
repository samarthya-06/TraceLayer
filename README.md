# TraceLayer

Offline Bitcoin investigation proof-of-concept for Smart India Hackathon 2026.
Requires Python 3.11 or newer.

The planned prototype will correlate P2P/network observations (IP, port, timestamp)
with blockchain metadata (TXID, wallet addresses, transaction amounts):

CSV ingestion → validation → cross-layer graph → feature engineering → Isolation
Forest anomaly detection → Bitcoin-pattern detection → risk and confidence scoring
→ ranked investigative leads → Streamlit visualization.

## Phase 4 scope

The deterministic synthetic data generator is implemented. The Streamlit app
still displays only its title. Dataset ingestion and the cross-layer evidence
graph, wallet features, and Isolation Forest are implemented. Explainable pattern
signals, combined scoring, and the interface remain for later phases.

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

- `pandas`: planned CSV ingestion, validation, and tabular processing.
- `numpy`: planned numerical feature calculations.
- `scikit-learn`: planned Isolation Forest anomaly detection.
- `networkx`: planned cross-layer graph construction.
- `streamlit`: local interactive interface; currently displays only the title.

Version pins are deferred until the analysis pipeline is implemented and tested.
Plotly and Pyvis are omitted because Phase 0 does not need graph visualization.

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

Generator tests are in `tests/test_generate_demo_data.py`. Pipeline tests remain a placeholder.

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

No graph visualization or anomaly detection is implemented in this phase.

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
