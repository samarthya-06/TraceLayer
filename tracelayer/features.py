"""Wallet-level numerical summaries derived only from case observations and graph."""

from collections import defaultdict

import networkx as nx
import pandas as pd

from tracelayer.graph_builder import blockchain_graph

MODEL_FEATURES = ['transaction_count', 'total_received', 'total_sent',
                  'mean_transaction_amount', 'max_transaction_amount', 'unique_counterparties',
                  'incoming_degree', 'outgoing_degree', 'transaction_frequency',
                  'mean_time_between_transactions']


def build_wallet_features(df, graph):
    """Summarize wallet activity; amounts are gross BTC, frequencies events/hour."""
    activity = defaultdict(dict)
    counterparties = defaultdict(set)
    for row in df.to_dict('records'):
        inputs, outputs = set(row['input_addresses']), set(row['output_addresses'])
        for side in ('input', 'output'):
            for wallet, amount in zip(row[f'{side}_addresses'], row[f'{side}_amounts']):
                event = activity[wallet].setdefault(row['txid'],
                    {'time': row['timestamp'], 'sent': 0.0, 'received': 0.0})
                event['sent' if side == 'input' else 'received'] += float(amount)
                counterparties[wallet].update((outputs if side == 'input' else inputs) - {wallet})
    chain = blockchain_graph(graph)
    seeds = [node for node, attrs in chain.nodes(data=True) if attrs.get('risk_seed')]
    distances = nx.multi_source_dijkstra_path_length(chain, seeds, weight=None) if seeds else {}
    records = []
    for wallet, events in sorted(activity.items()):
        events = list(events.values())
        times = sorted(event['time'] for event in events)
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        span = (times[-1] - times[0]).total_seconds()
        amounts = [event['sent'] + event['received'] for event in events]
        node = ('WALLET', wallet)
        records.append(dict(entity_id=wallet, transaction_count=len(events),
            total_received=sum(event['received'] for event in events),
            total_sent=sum(event['sent'] for event in events),
            mean_transaction_amount=sum(amounts) / len(amounts), max_transaction_amount=max(amounts),
            unique_counterparties=len(counterparties[wallet]),
            incoming_degree=len(set(graph.predecessors(node))),
            outgoing_degree=len(set(graph.successors(node))),
            transaction_frequency=(len(events) - 1) * 3600 / max(span, 60) if gaps else 0.0,
            mean_time_between_transactions=sum(gaps) / len(gaps) if gaps else float('nan'),
            seed_distance=distances.get(node, float('nan'))))
    return pd.DataFrame(records, columns=['entity_id'] + MODEL_FEATURES + ['seed_distance'])
