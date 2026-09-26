"""Load local CSV observations without consulting evaluation ground truth."""

import ipaddress
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "src_ip", "dst_ip", "src_port", "dst_port", "txid",
                    "input_addresses", "output_addresses", "input_amounts", "output_amounts",
                    "fee", "script_type"]
DEFAULT_CASE = Path(__file__).resolve().parents[1] / "data" / "demo_case.csv"


def parse_list(value, amounts=False):
    """Parse a nonempty JSON list of wallet strings or exact numeric BTC values."""
    values = json.loads(value)
    if not isinstance(values, list) or not values:
        raise ValueError("must be a nonempty JSON list")
    if amounts:
        result = []
        for item in values:
            if isinstance(item, (bool, list, dict)) or item is None:
                raise ValueError("amounts must be numeric")
            number = Decimal(str(item))
            if not number.is_finite() or number <= 0:
                raise ValueError("amounts must be finite and positive")
            result.append(number)
        return result
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError("addresses must be nonempty strings")
    return [item.strip() for item in values]


def load_case(path=DEFAULT_CASE):
    """Return cleaned observations and a report; reject bad rows with reasons."""
    report = dict(total_rows=0, valid_rows=0, invalid_rows=0, duplicate_txids=0,
                  missing_required_values=0, missing_columns=[], row_errors=[], errors=[])
    empty = pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        report['errors'].append(str(error))
        return empty, report
    report['total_rows'] = len(raw)
    missing = [name for name in REQUIRED_COLUMNS if name not in raw.columns]
    report['missing_columns'] = missing
    raw = raw.reindex(columns=REQUIRED_COLUMNS, fill_value='')
    missing_values = raw.apply(lambda column: column.str.strip().eq(''))
    report['missing_required_values'] = int(missing_values.sum().sum())
    txids = raw['txid'].str.strip()
    report['duplicate_txids'] = int(txids[txids.ne('')].duplicated().sum())
    if missing:
        report['errors'].append('Missing required columns: ' + ', '.join(missing))
    cleaned, seen = [], set()
    for index, source in raw.iterrows():
        row = source.str.strip().to_dict()
        reasons = [f'{name}: missing required value' for name in REQUIRED_COLUMNS if not row[name]]
        if not reasons:
            for name in REQUIRED_COLUMNS:
                try:
                    if name == 'timestamp':
                        row[name] = pd.to_datetime(row[name], utc=True, errors='raise')
                        if pd.isna(row[name]):
                            raise ValueError('invalid timestamp')
                    elif name in ('src_ip', 'dst_ip'):
                        row[name] = str(ipaddress.ip_address(row[name]))
                    elif name in ('src_port', 'dst_port'):
                        row[name] = int(row[name])
                        if not 1 <= row[name] <= 65535:
                            raise ValueError('port must be between 1 and 65535')
                    elif name.endswith('_addresses') or name.endswith('_amounts'):
                        row[name] = parse_list(row[name], amounts=name.endswith('_amounts'))
                    elif name == 'fee':
                        row[name] = Decimal(row[name])
                        if not row[name].is_finite() or row[name] < 0:
                            raise ValueError('fee must be finite and nonnegative')
                except (ValueError, TypeError, InvalidOperation, OverflowError) as error:
                    reasons.append(f'{name}: {error}')
            if not reasons:
                for side in ('input', 'output'):
                    if len(row[f'{side}_addresses']) != len(row[f'{side}_amounts']):
                        reasons.append(f'{side}: address and amount counts differ')
                if sum(row['input_amounts']) != sum(row['output_amounts']) + row['fee']:
                    reasons.append('amounts: inputs must equal outputs plus fee')
        if row['txid'] in seen:
            reasons.append('txid: duplicate of an earlier valid row')
        if reasons:
            report['row_errors'].append({'record_number': int(index) + 1,
                                         'txid': source['txid'], 'reasons': reasons})
        else:
            seen.add(row['txid'])
            cleaned.append(row)
    report['valid_rows'] = len(cleaned)
    report['invalid_rows'] = len(raw) - len(cleaned)
    return pd.DataFrame(cleaned, columns=REQUIRED_COLUMNS), report
