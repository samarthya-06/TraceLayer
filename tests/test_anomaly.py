"""Test data-derived features and label-independent Isolation Forest scoring."""

import unittest

import numpy as np
import pandas as pd

from tracelayer.anomaly import fit_anomaly_model
from tracelayer.features import MODEL_FEATURES, build_wallet_features
from tracelayer.graph_builder import build_evidence_graph
from tracelayer.ingestion import load_case


class AnomalyTests(unittest.TestCase):
    """Check numerical features, safe edge cases, and identity independence."""

    @classmethod
    def setUpClass(cls):
        """Build one reusable case feature table."""
        cls.df, _ = load_case()
        cls.features = build_wallet_features(cls.df, build_evidence_graph(cls.df))

    def test_features(self):
        """Known fixture activity produces measured counts and time gaps."""
        burst = self.features.set_index('entity_id').loc['wallet_burst_demo']
        self.assertEqual(burst.transaction_count, 30)
        self.assertEqual(burst.mean_time_between_transactions, 2)
        self.assertEqual(burst.unique_counterparties, 30)
        self.assertEqual(burst.transaction_frequency, 1740)
        self.assertEqual(self.features.set_index('entity_id').loc['wallet_target'].seed_distance, 4)
        self.assertTrue((self.features[MODEL_FEATURES].drop(columns='mean_time_between_transactions') >= 0).all().all())

    def test_scores_and_identity_independence(self):
        """Names and seeds cannot affect scores; results are finite and deterministic."""
        scores = fit_anomaly_model(self.features)
        self.assertTrue(scores.anomaly_score.between(0, 1).all())
        self.assertTrue(np.isfinite(scores.anomaly_score).all())
        self.assertEqual(len(scores[scores.entity_id == 'wallet_burst_demo']), 1)
        renamed = self.features.copy()
        renamed.entity_id = [f'opaque_{i}' for i in range(len(renamed))]
        renamed.seed_distance = 999
        np.testing.assert_array_equal(scores.anomaly_score, fit_anomaly_model(renamed).anomaly_score)
        np.testing.assert_array_equal(scores.anomaly_score, fit_anomaly_model(self.features).anomaly_score)

    def test_missing_infinite_and_small_cases(self):
        """Missing/infinite input and tiny/constant cases never produce NaN scores."""
        dirty = self.features.copy()
        dirty['total_sent'] = np.inf
        dirty['total_received'] = np.nan
        self.assertTrue(np.isfinite(fit_anomaly_model(dirty).anomaly_score).all())
        for frame in (self.features.iloc[:0], self.features.iloc[:1],
                      pd.DataFrame({'entity_id': ['a', 'b']})):
            self.assertTrue((fit_anomaly_model(frame).anomaly_score == 0).all())
        with self.assertRaises(ValueError):
            fit_anomaly_model(self.features, contamination=0.9)
