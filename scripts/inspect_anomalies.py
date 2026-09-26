"""Predict first, then optionally compare completed results with evaluation labels."""

import json
from pathlib import Path

from tracelayer.anomaly import fit_anomaly_model
from tracelayer.features import build_wallet_features
from tracelayer.graph_builder import build_evidence_graph
from tracelayer.ingestion import load_case


def main():
    """Print predictions before opening the evaluation-only ground truth file."""
    df, report = load_case()
    if report['errors'] or report['invalid_rows']:
        raise SystemExit(report)
    scored = fit_anomaly_model(build_wallet_features(df, build_evidence_graph(df)))
    ranked = scored.sort_values(['anomaly_score', 'entity_id'], ascending=[False, True]).reset_index(drop=True)
    print(ranked[['entity_id', 'anomaly_score', 'transaction_count', 'transaction_frequency']].head(10).to_string(index=False))
    # Evaluation starts here, after all predictions have been computed.
    truth = json.loads((Path(__file__).resolve().parents[1] / 'data/ground_truth.json').read_text())
    wallet = truth['scenarios']['anomalous_burst']['source_wallet']
    match = ranked.index[ranked.entity_id == wallet]
    print(f'Evaluation only: burst wallet rank {int(match[0]) + 1} / {len(ranked)}' if len(match) else 'Burst wallet absent')


if __name__ == '__main__':
    main()
