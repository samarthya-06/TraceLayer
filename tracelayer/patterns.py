"""Conservative structural indicators, never conclusions about criminality."""

from collections import defaultdict

import pandas as pd


def detect_peeling_chains(df, min_steps=3, dominance=0.8, max_relative_drop=0.2):
    """Find unambiguous chronological single-input, two-output continuation chains."""
    if min_steps < 2 or not 0.5 < dominance <= 1 or not 0 < max_relative_drop < 1:
        raise ValueError('Require min_steps >= 2, dominance > 0.5, and drop in (0, 1)')
    candidates = []
    by_source = defaultdict(list)
    wallets = set()
    for row in df.to_dict('records'):
        wallets.update(row['input_addresses'] + row['output_addresses'])
        if len(row['input_addresses']) != 1 or len(row['output_addresses']) != 2:
            continue
        amounts = row['output_amounts']
        largest = max(range(2), key=lambda index: amounts[index])
        source, target = row['input_addresses'][0], row['output_addresses'][largest]
        if source == target or len(set(row['output_addresses'])) != 2:
            continue
        if float(amounts[largest] / sum(amounts)) < dominance:
            continue
        item = dict(source=source, target=target, amount=amounts[largest],
                    input_amount=row['input_amounts'][0], txid=row['txid'], timestamp=row['timestamp'])
        candidates.append(item)
        by_source[source].append(item)
    found = {wallet: dict(entity_id=wallet, peeling_signal=0.0, peeling_reason='', peeling_txids=[])
             for wallet in sorted(wallets)}
    for start in candidates:
        path, visited = [start], {start['source'], start['target']}
        while True:
            last = path[-1]
            possible = [item for item in by_source[last['target']]
                        if item['timestamp'] > last['timestamp']
                        and item['input_amount'] == last['amount']
                        and 0 < float((last['amount'] - item['amount']) / last['amount']) <= max_relative_drop]
            if len(possible) != 1 or possible[0]['target'] in visited:
                break
            path.append(possible[0])
            visited.add(possible[0]['target'])
        if len(path) >= min_steps:
            for wallet in visited:
                if len(path) > len(found[wallet]['peeling_txids']):
                    found[wallet].update(peeling_signal=1.0,
                        peeling_reason=f'{len(path)}-step decreasing-value transaction chain detected (heuristic indicator).',
                        peeling_txids=[item['txid'] for item in path])
    return pd.DataFrame(found.values(), columns=['entity_id', 'peeling_signal', 'peeling_reason', 'peeling_txids'])
