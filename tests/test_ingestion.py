"""Exercise valid and malformed input without changing demonstration files."""

import csv
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.generate_demo_data import generate_dataset
from tracelayer.ingestion import REQUIRED_COLUMNS, load_case


class IngestionTests(unittest.TestCase):
    """Check cleanup and auditable row rejection."""

    def load_rows(self, rows, columns=REQUIRED_COLUMNS):
        """Load a temporary CSV fixture through the public API."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'case.csv'
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(rows)
            return load_case(path)

    def test_successful_load(self):
        """Parse default demo records into UTC times, lists, and exact amounts."""
        df, report = load_case()
        self.assertEqual((report['total_rows'], report['valid_rows'], report['invalid_rows']), (1000, 1000, 0))
        self.assertEqual(report['missing_required_values'], 0)
        self.assertEqual(str(df.timestamp.dt.tz), 'UTC')
        self.assertIsInstance(df.iloc[0].input_addresses, list)
        self.assertIsInstance(df.iloc[0].input_amounts[0], Decimal)

    def test_missing_column(self):
        """Reject a structurally incomplete file with an explicit report."""
        rows = generate_dataset(100)[0][:2]
        df, report = self.load_rows(rows, [name for name in REQUIRED_COLUMNS if name != 'fee'])
        self.assertTrue(df.empty)
        self.assertEqual(report['missing_columns'], ['fee'])
        self.assertEqual(report['invalid_rows'], 2)
        self.assertEqual(report['missing_required_values'], 2)

    def test_invalid_timestamp(self):
        """Keep good rows when a timestamp cannot be parsed."""
        rows = generate_dataset(100)[0][:2]
        rows[0]['timestamp'] = 'not-a-date'
        df, report = self.load_rows(rows)
        self.assertEqual(len(df), 1)
        self.assertEqual(report['invalid_rows'], 1)
        self.assertEqual(report['row_errors'][0]['record_number'], 1)

    def test_duplicate_txid(self):
        """Keep only the first valid occurrence and report repeated TXIDs."""
        row = generate_dataset(100)[0][0]
        df, report = self.load_rows([row, row])
        self.assertEqual(len(df), 1)
        self.assertEqual(report['duplicate_txids'], 1)
        self.assertEqual(report['invalid_rows'], 1)
        bad = dict(row, timestamp='invalid')
        df, report = self.load_rows([bad, row, row])
        self.assertEqual(len(df), 1)
        self.assertEqual(report['duplicate_txids'], 2)
        self.assertEqual(report['invalid_rows'], 2)

    def test_malformed_values(self):
        """Reject bad JSON, lists, amounts, ports, IPs, blanks, and imbalance."""
        row = generate_dataset(100)[0][0]
        for field, value in [('input_addresses', 'wallet_a|wallet_b'), ('input_addresses', '[]'),
                             ('output_amounts', '["NaN"]'), ('fee', 'Infinity'),
                             ('src_port', '70000'), ('src_ip', 'invalid'), ('txid', ' '),
                             ('output_amounts', '["1", "2"]'), ('fee', '999')]:
            with self.subTest(field=field, value=value):
                df, report = self.load_rows([dict(row, **{field: value}), row])
                self.assertEqual(len(df), 1)
                self.assertEqual(report['invalid_rows'], 1)
                self.assertTrue(report['row_errors'])

    def test_file_error(self):
        """File access failures return an empty frame and explicit error."""
        df, report = load_case('/nonexistent/tracelayer-case.csv')
        self.assertTrue(df.empty)
        self.assertTrue(report['errors'])


class CsvLayoutTests(unittest.TestCase):
    """Prevent malformed layouts from being silently accepted or skipped."""

    def test_extra_leading_field(self):
        """Reject pandas implicit-index inference for an overwide CSV record."""
        from io import StringIO
        rows = generate_dataset(100)[0][:1]
        handle = StringIO()
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        header, row = handle.getvalue().splitlines()
        df, report = load_case(StringIO(header + '\nEXTRA,' + row + '\n'))
        self.assertTrue(df.empty)
        self.assertEqual(report['invalid_rows'], 1)
        self.assertTrue(report['errors'])

    def test_blank_record_reported(self):
        """Count a blank data record as invalid instead of silently deleting it."""
        from io import StringIO
        handle = StringIO()
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerow(generate_dataset(100)[0][0])
        df, report = load_case(StringIO(handle.getvalue() + '\n'))
        self.assertEqual(report['total_rows'], 2)
        self.assertEqual(report['invalid_rows'], 1)
        self.assertEqual(len(df), 1)
