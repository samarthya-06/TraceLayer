"""Exercise the local Streamlit interface and its core interactions."""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class AppTests(unittest.TestCase):
    """Verify rendering, filters, and selected evidence without a browser service."""

    def test_three_tabs_and_interactions(self):
        """Render all tabs, filter leads, inspect the burst, and handle empty results."""
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=60)
        self.assertFalse(app.exception)
        self.assertEqual([tab.label for tab in app.tabs], ['Case Overview', 'Ranked Leads', 'Evidence Graph / Lead Details'])
        self.assertEqual(app.title[0].value, 'TraceLayer')
        self.assertEqual(next(metric.value for metric in app.metric if metric.label == 'Records Processed'), '1,000')
        app.text_input[0].set_value('wallet_burst_demo').run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='ranked_entity').value, 'wallet_burst_demo')
        app.selectbox(key='graph_entity').set_value('wallet_burst_demo').run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(next(metric.value for metric in app.metric if metric.label == 'Relevant Transactions'), '30')
        app.slider[0].set_value(100).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(any('No leads match' in info.value for info in app.info))
        app.text_input[0].set_value('').run(timeout=30)
        app.slider[0].set_value(0).run(timeout=30)
        self.assertFalse(app.exception)


    def test_offline_execution(self):
        """Run the pipeline and app with network connections and DNS blocked."""
        from unittest.mock import patch
        from tracelayer.pipeline import run_pipeline
        with patch('socket.socket.connect', side_effect=AssertionError('Unexpected network connection')), \
             patch('socket.getaddrinfo', side_effect=AssertionError('Unexpected DNS lookup')):
            result = run_pipeline()
            self.assertEqual(len(result['leads']), 645)
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run(timeout=60)
            self.assertFalse(app.exception)
