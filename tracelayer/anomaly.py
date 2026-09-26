"""Isolation Forest scores numeric activity, never wallet names or seed labels."""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from tracelayer.features import MODEL_FEATURES


def fit_anomaly_model(feature_df, contamination=0.05, random_state=42):
    """Fit the case and return scores; higher min-max normalized scores are rarer."""
    if contamination != 'auto' and not 0 < contamination <= 0.5:
        raise ValueError('contamination must be auto or a number in (0, 0.5]')
    result = feature_df.copy()
    numeric = result.reindex(columns=MODEL_FEATURES).apply(pd.to_numeric, errors='coerce')
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    numeric = numeric.fillna(numeric.median()).fillna(0.0)
    # seed_distance is intentionally excluded: known seeds are a separate signal.
    if len(numeric) < 2 or (numeric.nunique() <= 1).all():
        result['raw_anomaly_score'] = 0.0
        result['anomaly_score'] = 0.0
        result['is_anomaly'] = False
        return result
    model = IsolationForest(n_estimators=200, contamination=contamination,
                            random_state=random_state, n_jobs=1)
    model.fit(numeric)
    # sklearn score_samples is LOWER for anomalies. Negate, then min-max per case.
    raw = -model.score_samples(numeric)
    spread = raw.max() - raw.min()
    result['raw_anomaly_score'] = raw
    result['anomaly_score'] = (raw - raw.min()) / spread if spread > 0 else np.zeros(len(raw))
    result['is_anomaly'] = model.predict(numeric) == -1
    return result
