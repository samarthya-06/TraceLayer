# TraceLayer

Offline Bitcoin investigation proof-of-concept for Smart India Hackathon 2026.
Requires Python 3.11 or newer.

The planned prototype will correlate P2P/network observations (IP, port, timestamp)
with blockchain metadata (TXID, wallet addresses, transaction amounts):

CSV ingestion → validation → cross-layer graph → feature engineering → Isolation
Forest anomaly detection → Bitcoin-pattern detection → risk and confidence scoring
→ ranked investigative leads → Streamlit visualization.

## Phase 3 scope

The deterministic synthetic data generator is implemented. The Streamlit app
still displays only its title. Dataset ingestion and the cross-layer evidence
graph are implemented; detection, scoring, and ML remain unimplemented placeholders.

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
