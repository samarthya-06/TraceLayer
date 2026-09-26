"""Run the local investigation pipeline without evaluation ground truth."""

import argparse
import json
from pathlib import Path

from tracelayer.anomaly import fit_anomaly_model
from tracelayer.features import build_wallet_features
from tracelayer.graph_builder import build_evidence_graph
from tracelayer.ingestion import DEFAULT_CASE, load_case
from tracelayer.patterns import detect_peeling_chains
from tracelayer.scoring import rank_leads


def run_pipeline(path=DEFAULT_CASE, contamination=0.05):
    """Return evidence, validation, features, and ranked leads for a local case."""
    df, report = load_case(path)
    if report['errors'] or df.empty:
        raise ValueError(f'No usable case: {json.dumps(report)}')
    graph = build_evidence_graph(df)
    features = build_wallet_features(df, graph)
    scored = fit_anomaly_model(features, contamination=contamination)
    patterns = detect_peeling_chains(df)
    leads = rank_leads(scored, patterns, df)
    return dict(data=df, validation=report, graph=graph, features=scored, patterns=patterns, leads=leads)


def save_ranked_leads(leads, path):
    """Save reasons as JSON arrays in an ordinary CSV, without rounding scores."""
    export = leads.copy()
    export['reasons'] = export['reasons'].map(json.dumps)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    export.to_csv(path, index=False)


def main():
    """Run the offline case and print the ten highest-priority review leads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, default=DEFAULT_CASE)
    parser.add_argument('--output', type=Path, default=DEFAULT_CASE.parent / 'ranked_leads.csv')
    parser.add_argument('--contamination', type=float, default=0.05)
    args = parser.parse_args()
    try:
        result = run_pipeline(args.case, args.contamination)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    save_ranked_leads(result['leads'], args.output)
    print('Validation:', json.dumps(result['validation']))
    print(result['leads'][['rank', 'entity_id', 'risk_score', 'confidence_score', 'anomaly_score',
                           'peeling_signal', 'seed_proximity_score']].head(10).to_string(index=False))
    print(f'Saved: {args.output}')
    print('Risk prioritizes review, not criminality. Confidence measures evidence strength, not guilt.')


if __name__ == '__main__':
    main()
