"""Evaluate completed ranked predictions against synthetic labels, never train on them."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def ranking_metrics(rank_by_id, targets):
    """Measure entity recall using ceiling cutoffs; absent targets remain failures."""
    targets = sorted(set(targets))
    ranks = {entity: rank_by_id.get(entity) for entity in targets}
    found = [rank for rank in ranks.values() if rank is not None]
    result = {'target_count': len(targets), 'individual_ranks': ranks,
              'missing_targets': [entity for entity, rank in ranks.items() if rank is None],
              'mean_rank_found_targets': sum(found) / len(found) if found else None}
    for percent in (5, 10):
        cutoff = math.ceil(len(rank_by_id) * percent / 100)
        hits = sum(rank is not None and rank <= cutoff for rank in ranks.values())
        result[f'top_{percent}_percent'] = {'cutoff': cutoff, 'found': hits,
                                          'recall': hits / len(targets) if targets else None}
    return result


def evaluate_predictions(predictions_path, ground_truth_path):
    """Load and validate completed predictions before opening evaluation labels."""
    ranked = pd.read_csv(predictions_path, dtype={'entity_id': str})
    required = {'rank', 'entity_id', 'risk_score'}
    if not required <= set(ranked.columns) or ranked.empty:
        raise ValueError('Predictions must be nonempty and contain rank, entity_id, risk_score')
    if ranked.entity_id.isna().any() or ranked.entity_id.str.strip().eq('').any() or ranked.entity_id.duplicated().any():
        raise ValueError('Prediction entity IDs must be present and unique')
    ranks = pd.to_numeric(ranked['rank'], errors='coerce')
    risk = pd.to_numeric(ranked['risk_score'], errors='coerce')
    if ranks.tolist() != list(range(1, len(ranked) + 1)):
        raise ValueError('Predictions must have consecutive one-based ranks in row order')
    if not risk.between(0, 100).all() or not risk.is_monotonic_decreasing:
        raise ValueError('Predictions must have bounded risk scores sorted descending')
    rank_by_id = dict(zip(ranked.entity_id, ranks.astype(int)))
    # Evaluation boundary: predictions are already loaded and finalized above.
    truth = json.loads(Path(ground_truth_path).read_text(encoding='utf-8'))
    scenarios = truth['scenarios']
    groups = {'peeling_chain': scenarios['peeling_chain']['chain_wallets'],
              'anomalous_burst': [scenarios['anomalous_burst']['source_wallet']],
              'seed_risk_target': [scenarios['seed_risk_path']['target_wallet']]}
    targets = {entity for values in groups.values() for entity in values}
    participants = {entity for scenario in scenarios.values() for entity in scenario['wallets']}
    primary = ranking_metrics(rank_by_id, targets)
    return {'label': 'Synthetic Demo Evaluation', 'total_ranked_entities': len(ranked),
            'target_definition': 'Peeling continuation wallets, burst source, and seed-path target; excludes incidental recipients and the supplied seed.',
            'primary_targets': primary,
            'scenario_ranks': {name: {entity: rank_by_id.get(entity) for entity in entities}
                               for name, entities in groups.items()},
            'all_scenario_participants': ranking_metrics(rank_by_id, participants),
            'prediction_sha256': hashlib.sha256(Path(predictions_path).read_bytes()).hexdigest(),
            'ground_truth_sha256': hashlib.sha256(Path(ground_truth_path).read_bytes()).hexdigest(),
            'limitation': 'The evaluation measures ranking performance on seeded synthetic scenarios. It is not evidence of real-world investigative accuracy.'}


def format_report(result):
    """Format primary metrics, individual ranks, and a broader participant check."""
    primary = result['primary_targets']
    lines = [result['label'], f"Total ranked entities: {result['total_ranked_entities']}",
             f"Ground-truth planted target entities: {primary['target_count']}", result['target_definition']]
    for percent in (5, 10):
        metric = primary[f'top_{percent}_percent']
        lines.extend([f"Top {percent}% cutoff: {metric['cutoff']}",
                      f"Targets found in Top {percent}%: {metric['found']}/{primary['target_count']}",
                      f"Recall@{percent}%: {metric['recall']:.2%}"])
    lines.append(f"Mean rank of found targets: {primary['mean_rank_found_targets']}")
    lines.append('Missing targets: ' + (', '.join(primary['missing_targets']) or 'None'))
    lines.append('Individual scenario ranks:')
    for scenario, ranks in result['scenario_ranks'].items():
        lines.append(f"  {scenario}: " + ', '.join(f'{entity}={rank if rank is not None else "MISSING"}' for entity, rank in ranks.items()))
    participants = result['all_scenario_participants']
    lines.append(f"Broader check — all {participants['target_count']} scenario participants, including incidental recipients:")
    for percent in (5, 10):
        metric = participants[f'top_{percent}_percent']
        lines.append(f"  Recall@{percent}%: {metric['found']}/{participants['target_count']} = {metric['recall']:.2%}")
    lines.append(result['limitation'])
    return '\n'.join(lines)


def main():
    """Evaluate a pre-existing ranked CSV and save a transparent JSON report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, default=ROOT / 'data/ranked_leads.csv')
    parser.add_argument('--ground-truth', type=Path, default=ROOT / 'data/ground_truth.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/evaluation.json')
    args = parser.parse_args()
    try:
        result = evaluate_predictions(args.predictions, args.ground_truth)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Evaluation failed: {error}. Produce ranked predictions first.\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(format_report(result))


if __name__ == '__main__':
    main()
