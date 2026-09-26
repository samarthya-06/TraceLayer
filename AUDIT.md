# TraceLayer — Final SIH Technical Audit

Audit scope: the completed Phase 8 MVP, reviewed after generation, prediction,
evaluation, tests, and local app checks succeeded. This is a source and behavior
review, not a security certification or operational forensic validation.

**PASS** = verified within this scope. **WARNING** = a material limitation to
carry into judging and future work. **FIXED** = a small verified correctness fix.

| # | Review question | Status | Finding / evidence |
|---|---|---|---|
| 1 | Genuine Isolation Forest inference? | PASS | `anomaly.py` fits sklearn IsolationForest on ten measured numerical features, then calls `score_samples` and `predict`. Scores are not predetermined. Fixed seeds provide reproducibility, not expected answers. |
| 2 | Ground truth excluded from analysis/scoring? | PASS | No production analysis module or UI reads ground truth. A test blocks ordinary and pathlib ground-truth opens while the pipeline runs. Evaluation validates completed predictions before opening labels. |
| 3 | Risk and confidence distinct? | PASS | Risk weights anomaly, peeling, and seed proximity. Confidence uses transaction and network support only. Changing all suspiciousness signals leaves confidence unchanged in tests. |
| 4 | Hard-coded suspicious entities? | PASS / WARNING | No peeling or burst IDs occur in feature/model/pattern/scoring code. Renaming entities preserves anomaly scores and structural detection. The explicitly requested `seed_wallet_demo` is a documented, configurable graph seed; seed proximity is prior investigator input, not a discovered ML result. |
| 5 | Both network and blockchain evidence? | PASS | Demo graph contains 500 IP, 1,000 TXID, and 645 wallet nodes; 5,497 edges carry typed relationships and relevant timestamp/port/amount evidence. |
| 6 | Understandable peeling detector? | PASS / WARNING | Documented single-input/two-output, dominance, decreasing-value, chronological, amount-continuity and minimum-length conditions. Tests include renamed wallets and negative examples. Change behavior can match; complex real chains can be missed. |
| 7 | Reasons derived from actual signals? | PASS | Reasons use computed model decisions/scores, detected chain lengths, seed distances, and counted evidence. They are not causal attribution or SHAP explanations. |
| 8 | Offline operation? | PASS | Pipeline and Streamlit AppTest succeed with Python socket connections and DNS blocked. Browser assets are served locally; no external service calls occur in application code. Installation still requires packages from a registry or prepared offline cache. |
| 9 | Unnecessary dependencies? | PASS | Six direct packages, all used: pandas, numpy, scikit-learn, NetworkX, Streamlit, Plotly. Framework transitive dependencies are package-managed; none are separately added as application infrastructure. |
| 10 | Clean reproduction? | PASS / WARNING | An isolated Git clone with a new, non-shared venv installed requirements and reproduced all four data artifacts byte-for-byte. Streamlit imported and served HTTP 200 with healthy status. Tested on macOS/Python 3.14.6; Windows and Python 3.11 were not exercised. Requirements are minimum versions, not a full lock, so future versions can alter exact ranks. |
| 11 | Misleading claims? | PASS | README/UI distinguish prioritization from criminality, support from ownership, and evidence confidence from probability of guilt. Production readiness and real-world accuracy are expressly disclaimed. |
| 12 | Synthetic results labeled? | PASS | Evaluation is labeled Synthetic Demo Evaluation/Results. It reports eight primary targets alongside all 45 scenario participants; neither is called real-world model accuracy. |
| 13 | All tests pass? | PASS | 29 tests pass in both the working project and fresh clone, including feature/model, graph, ingestion, patterns/scoring, evaluation, and UI interactions. |
| 14 | Bugs, leakage, or inconsistent scoring? | FIXED / WARNING | Overwide CSV records could silently become pandas index values and be accepted; ingestion now rejects that layout. Blank CSV records previously disappeared; they are now counted/reported. Regression tests pass. Model, feature definitions, risk weights, and generated predictions are unchanged. Seed distances remain structural rather than chronological, and monetary links are not UTXO provenance. |
| 15 | Explainable by students? | PASS | Small function-based modules, documented formulas, a Mermaid dataflow, CLI examples, and short docstrings on all functions. No new framework or large refactor. |

## Additional repository checks

- **PASS:** All 20 Python source/test files compile; no function lacks a docstring.
- **PASS:** `pip check` reports no broken requirements in the fresh environment.
- **PASS:** Pattern scanning found no machine-specific user-directory paths in
  tracked content and no common credential/private-key patterns in tracked files
  or Git-history patches. This limited scan is not a guarantee that no secret
  could exist; no credentials or user-sensitive data were introduced.
- **PASS:** No placeholder modules, breakpoints, or abandoned debug output remain.
  CLI summaries and inspection output are intentional user-facing diagnostics.
- **PASS:** All retained files have a purpose. Inspection scripts are documented;
  no useful files were removed just to reduce the file count. Venvs/caches/secrets
  are ignored. No new direct dependency was needed for Phases 7 or 8.
- **WARNING:** The evaluator accepts a pre-existing ranked CSV. Fingerprints
  identify the prediction and label inputs but cannot establish their provenance
  or prevent a user from deliberately supplying mismatched cases. Run generation,
  pipeline, and evaluation in sequence as documented.

## Recorded synthetic results

Default seed 42; 1,000 records, 645 wallets, 1,000 unique TXIDs; all rows valid.

| Check | Result |
|---|---:|
| Top 5% cutoff | 33 |
| Primary targets found / Recall@5% | 8/8 / 100% |
| Top 10% cutoff | 65 |
| Primary targets found / Recall@10% | 8/8 / 100% |
| Mean primary target rank | 6.125 |
| Primary missing targets | 0 |
| All-participant Recall@5% and @10% | 10/45 / 22.22% |
| Burst source anomaly rank / combined risk rank | 5 / 7 |
| Seed-path target combined risk rank | 21 |

Peeling continuation ranks, in chain order: **5, 1, 2, 3, 4, 6**.

The primary result is strong on the deliberately planted structures but has only
eight targets. Broader participant recall is low because most incidental
recipients have one ordinary-looking transaction. This evaluation is of combined
risk ranking, including a supplied seed and explicit pattern heuristics—not
isolated model accuracy or independent operational validation. No scoring/model
change was made to improve these results. Legitimate improvements include richer
normal behavior, independent cases, provenance, and larger public/synthetic sets.

## Reproduce the complete demo

After cloning, run from the repository root with Python 3.11+:

```sh
python -m venv .venv
```

Activate on macOS/Linux:

```sh
source .venv/bin/activate
```

Or Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then:

```sh
python -m pip install -r requirements.txt
python scripts/generate_demo_data.py
python -m tracelayer.pipeline
python scripts/evaluate_demo.py
python -m unittest discover -s tests -v
python -m pip check
python -c "import streamlit; print(streamlit.__version__)"
streamlit run app.py
```
