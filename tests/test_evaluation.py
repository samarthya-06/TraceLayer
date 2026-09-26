"""Verify evaluation denominators, rounding, missing targets, and read order."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.evaluate_demo import evaluate_predictions, ranking_metrics


class EvaluationTests(unittest.TestCase):
    """Use tiny independent rankings with hand-calculable results."""

    def test_cutoffs_and_missing_targets(self):
        """Ceiling cutoffs and absent targets cannot inflate recall."""
        ranking = {f'e{i}': i for i in range(1, 22)}
        result = ranking_metrics(ranking, ['e1', 'e3', 'absent', 'e1'])
        self.assertEqual(result['target_count'], 3)
        self.assertEqual(result['top_5_percent'], {'cutoff': 2, 'found': 1, 'recall': 1 / 3})
        self.assertEqual(result['top_10_percent'], {'cutoff': 3, 'found': 2, 'recall': 2 / 3})
        self.assertEqual(result['mean_rank_found_targets'], 2)
        self.assertEqual(result['missing_targets'], ['absent'])

    def test_evaluation_and_invalid_predictions(self):
        """Check target semantics and reject bad predictions before label access."""
        with tempfile.TemporaryDirectory() as folder:
            predictions, truth = Path(folder) / 'ranked.csv', Path(folder) / 'truth.json'
            frame = pd.DataFrame({'rank': list(range(1, 21)), 'entity_id': [f'e{i}' for i in range(1, 21)],
                                  'risk_score': list(range(99, 79, -1))})
            frame.to_csv(predictions, index=False)
            truth.write_text(json.dumps({'scenarios': {
                'peeling_chain': {'chain_wallets': ['e1'], 'wallets': ['e1', 'e20']},
                'anomalous_burst': {'source_wallet': 'e2', 'wallets': ['e2']},
                'seed_risk_path': {'target_wallet': 'missing', 'wallets': ['e3', 'missing']}}}))
            report = evaluate_predictions(predictions, truth)
            self.assertEqual(report['primary_targets']['target_count'], 3)
            self.assertEqual(report['primary_targets']['top_5_percent']['found'], 1)
            self.assertEqual(report['all_scenario_participants']['target_count'], 5)
            self.assertEqual(report['scenario_ranks']['seed_risk_target'], {'missing': None})
            for broken in (frame.assign(rank=1), frame.assign(entity_id='same'), frame.assign(risk_score=float('nan'))):
                broken.to_csv(predictions, index=False)
                with patch.object(Path, 'read_text', side_effect=AssertionError('Labels accessed too early')):
                    with self.assertRaises(ValueError):
                        evaluate_predictions(predictions, truth)
