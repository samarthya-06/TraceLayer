# TraceLayer

Offline Bitcoin investigation proof-of-concept for Smart India Hackathon 2026.
Requires Python 3.11 or newer.

The planned prototype will correlate P2P/network observations (IP, port, timestamp)
with blockchain metadata (TXID, wallet addresses, transaction amounts):

CSV ingestion → validation → cross-layer graph → feature engineering → Isolation
Forest anomaly detection → Bitcoin-pattern detection → risk and confidence scoring
→ ranked investigative leads → Streamlit visualization.

## Phase 0 scope

Only the project scaffold and a Streamlit title are implemented. Python modules,
the data generator, and the test file are placeholders. `data/demo_case.csv` is
empty and `data/ground_truth.json` contains an empty object; neither contains demo
observations or evaluation results yet. No analysis logic or performance claims
are included. Network observations will be investigative clues, not proof of
wallet ownership or transaction origin.

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

Pipeline tests will be added with the implementation in a later phase.
