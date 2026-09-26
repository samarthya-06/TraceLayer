"""Verify explainable signals, ranking, and ground-truth-free execution."""

import builtins
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from tracelayer.patterns import detect_peeling_chains
from tracelayer.pipeline import run_pipeline, save_ranked_leads
from tracelayer.scoring import rank_leads


class PipelineTests(unittest.TestCase):
    """Exercise the integrated case and counterexamples for the pattern heuristic."""

    @classmethod
    def setUpClass(cls):
        """Run the complete case once for result assertions."""
        cls.result = run_pipeline()

    def test_bounded_explained_and_sorted(self):
        """Scores stay bounded, risk is explicit, and every lead has reasons."""
        leads = self.result['leads']
        for name in ('risk_score', 'confidence_score'):
            self.assertTrue(leads[name].between(0, 100).all())
        for name in ('anomaly_score', 'peeling_signal', 'seed_proximity_score'):
            self.assertTrue(leads[name].between(0, 1).all())
        self.assertTrue(leads.risk_score.is_monotonic_decreasing)
        self.assertEqual(leads['rank'].tolist(), list(range(1, len(leads) + 1)))
        self.assertTrue(all(isinstance(reasons, list) and reasons for reasons in leads.reasons))
        self.assertFalse(leads.risk_score.equals(leads.confidence_score))
        expected = 50 * leads.anomaly_score + 30 * leads.peeling_signal + 20 * leads.seed_proximity_score
        pd.testing.assert_series_equal(leads.risk_score, expected, check_names=False)

    def test_confidence_independent_of_suspiciousness(self):
        """Changing anomaly/seed/pattern signals cannot change evidence confidence."""
        features = self.result['features'].copy()
        features['anomaly_score'] = 0.0
        features['is_anomaly'] = False
        features['seed_distance'] = float('nan')
        patterns = self.result['patterns'].copy()
        patterns['peeling_signal'] = 0.0
        leads = rank_leads(features, patterns, self.result['data'])
        original = self.result['leads'].set_index('entity_id').confidence_score.sort_index()
        pd.testing.assert_series_equal(original, leads.set_index('entity_id').confidence_score.sort_index())

    def test_pattern_and_counterexamples(self):
        """Recognize the fixture structure, not its names or unordered values."""
        df = self.result['data']
        pattern = self.result['patterns'].set_index('entity_id')
        self.assertEqual(pattern.loc['wallet_peel_03'].peeling_signal, 1)
        txids = pattern.loc['wallet_peel_03'].peeling_txids
        fixture = df[df.txid.isin(txids)].copy(deep=True)
        names = {wallet: f'opaque_{i}' for i, wallet in enumerate(sorted(set(sum(fixture.input_addresses.tolist() + fixture.output_addresses.tolist(), []))))}
        for column in ('input_addresses', 'output_addresses'):
            fixture[column] = fixture[column].map(lambda values: [names[value] for value in values])
        self.assertEqual(detect_peeling_chains(fixture).peeling_signal.max(), 1)
        self.assertEqual(detect_peeling_chains(fixture.iloc[:2]).peeling_signal.max(), 0)
        backwards = fixture.copy()
        backwards['timestamp'] = list(reversed(backwards.timestamp.tolist()))
        self.assertEqual(detect_peeling_chains(backwards).peeling_signal.max(), 0)
        balanced = fixture.copy()
        balanced['output_amounts'] = balanced.output_amounts.map(lambda values: [sum(values) / 2] * 2)
        self.assertEqual(detect_peeling_chains(balanced).peeling_signal.max(), 0)
        broken = fixture.copy()
        broken['input_amounts'] = broken.input_amounts.map(lambda values: [values[0] + 1])
        self.assertEqual(detect_peeling_chains(broken).peeling_signal.max(), 0)

    def test_ground_truth_not_read_and_csv_export(self):
        """Pipeline runs with evaluation-file access forbidden; reasons survive CSV."""
        original_open = builtins.open
        original_path_open = Path.open

        def guarded_open(file, *args, **kwargs):
            """Reject ground-truth file access during prediction."""
            if 'ground_truth' in str(file):
                raise AssertionError('Prediction read evaluation labels')
            return original_open(file, *args, **kwargs)

        def guarded_path_open(path, *args, **kwargs):
            """Guard pathlib reads as well as ordinary file opens."""
            if 'ground_truth' in str(path):
                raise AssertionError('Prediction read evaluation labels')
            return original_path_open(path, *args, **kwargs)

        with patch('builtins.open', guarded_open), patch.object(Path, 'open', guarded_path_open):
            result = run_pipeline()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'leads.csv'
            save_ranked_leads(result['leads'], path)
            exported = pd.read_csv(path)
            self.assertEqual(len(exported), len(result['leads']))
            self.assertTrue(json.loads(exported.iloc[0].reasons))
