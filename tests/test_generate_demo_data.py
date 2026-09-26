"""Check the synthetic generator independently of the future detection pipeline."""

import copy
import csv
import ipaddress
import json
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from scripts.generate_demo_data import COLUMNS, generate_dataset, save_dataset, validate_dataset


class GeneratorTests(unittest.TestCase):
    """Verify reproducibility, serialization, and the injected scenario structure."""

    def setUp(self):
        """Generate the default fixture without writing into the project data."""
        self.records, self.truth = generate_dataset()
        self.by_id = {row['txid']: row for row in self.records}

    def test_reproducible_and_configurable(self):
        """Identical parameters reproduce data; alternate seeds and sizes work."""
        self.assertEqual((self.records, self.truth), generate_dataset())
        self.assertNotEqual(self.records, generate_dataset(seed=7)[0])
        self.assertEqual(len(generate_dataset(rows=100)[0]), 100)
        self.assertEqual(len(generate_dataset(rows=1200)[0]), 1200)
        with self.assertRaises(ValueError):
            generate_dataset(rows=99)

    def test_fields_and_synthetic_entities(self):
        """Require complete balanced records and reserved synthetic identifiers."""
        self.assertEqual(len(self.records), 1000)
        self.assertEqual(len(self.by_id), 1000)
        networks = [ipaddress.ip_network('192.0.2.0/24'), ipaddress.ip_network('198.51.100.0/24')]
        for row in self.records:
            self.assertEqual(list(row), COLUMNS)
            self.assertTrue(all(value is not None and value != '' for value in row.values()))
            self.assertTrue(row['txid'].startswith('tx_demo_'))
            for field in ('src_ip', 'dst_ip'):
                self.assertTrue(any(ipaddress.ip_address(row[field]) in net for net in networks))
            for field in ('src_port', 'dst_port'):
                self.assertTrue(1 <= int(row[field]) <= 65535)
            for field in ('input_addresses', 'output_addresses'):
                self.assertTrue(all(wallet.startswith(('bc1q_demo_', 'wallet_', 'seed_wallet_demo'))
                                    for wallet in json.loads(row[field])))
        for field in ('input_addresses', 'output_addresses'):
            self.assertGreater(len({len(json.loads(row[field])) for row in self.records}), 1)
        validate_dataset(self.records, self.truth)

    def test_scenarios(self):
        """Confirm sequential peel amounts, burst timing, and two-hop seed path."""
        scenarios = self.truth['scenarios']
        self.assertEqual(set(scenarios), {'peeling_chain', 'anomalous_burst', 'seed_risk_path'})
        injected = {txid for scenario in scenarios.values() for txid in scenario['txids']}
        self.assertLess(len(injected), len(self.records) / 2)
        peel = scenarios['peeling_chain']
        for index, txid in enumerate(peel['txids']):
            row = self.by_id[txid]
            self.assertEqual(json.loads(row['input_addresses']), [peel['chain_wallets'][index]])
            self.assertEqual(json.loads(row['output_addresses'])[0], peel['chain_wallets'][index + 1])
            self.assertEqual(json.loads(row['output_amounts'])[0], peel['transferred_btc'][index])
            if index:
                previous = self.by_id[peel['txids'][index - 1]]
                self.assertEqual(json.loads(row['input_amounts'])[0], json.loads(previous['output_amounts'])[0])
                self.assertLess(Decimal(json.loads(row['output_amounts'])[0]),
                                Decimal(json.loads(previous['output_amounts'])[0]))
        burst = scenarios['anomalous_burst']
        times = [datetime.fromisoformat(self.by_id[txid]['timestamp']) for txid in burst['txids']]
        self.assertEqual(len(times), 30)
        self.assertEqual((max(times) - min(times)).total_seconds(), 58)
        for txid in burst['txids']:
            self.assertEqual(json.loads(self.by_id[txid]['input_addresses']), [burst['source_wallet']])
        path = scenarios['seed_risk_path']
        for index, txid in enumerate(path['txids']):
            self.assertEqual(json.loads(self.by_id[txid]['input_addresses']), [path['wallets'][index]])
            self.assertEqual(json.loads(self.by_id[txid]['output_addresses']), [path['wallets'][index + 1]])

    def test_round_trip_and_identical_files(self):
        """Persisted CSV remains valid and repeat generation is byte-for-byte stable."""
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            save_dataset(self.records, self.truth, directory)
            before = {path.name: path.read_bytes() for path in directory.iterdir()}
            with (directory / 'demo_case.csv').open(newline='') as handle:
                loaded = list(csv.DictReader(handle))
            truth = json.loads((directory / 'ground_truth.json').read_text())
            validate_dataset(loaded, truth)
            save_dataset(*generate_dataset(), directory)
            self.assertEqual(before, {path.name: path.read_bytes() for path in directory.iterdir()})

    def test_invalid_generated_data_rejected(self):
        """Reject missing fields, unbalanced amounts, and absent scenario entities."""
        for mutate in (lambda rows: rows[0].pop('src_ip'),
                       lambda rows: rows[0].update(txid=''),
                       lambda rows: rows[0].update(fee='9000')):
            rows = copy.deepcopy(self.records)
            mutate(rows)
            with self.assertRaises(ValueError):
                validate_dataset(rows, self.truth)
        truth = copy.deepcopy(self.truth)
        truth['scenarios']['seed_risk_path']['wallets'].append('missing_wallet_demo')
        with self.assertRaises(ValueError):
            validate_dataset(self.records, truth)


if __name__ == '__main__':
    unittest.main()
