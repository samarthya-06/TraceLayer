# TraceLayer

Offline Bitcoin investigation proof-of-concept for Smart India Hackathon 2026.
Requires Python 3.11 or newer.

The planned prototype will correlate P2P/network observations (IP, port, timestamp)
with blockchain metadata (TXID, wallet addresses, transaction amounts):

CSV ingestion → validation → cross-layer graph → feature engineering → Isolation
Forest anomaly detection → Bitcoin-pattern detection → risk and confidence scoring
→ ranked investigative leads → Streamlit visualization.

## Phase 1 scope

The deterministic synthetic data generator is implemented. The Streamlit app
still displays only its title; ingestion, graphs, detection, scoring, and ML
remain unimplemented placeholders.

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
