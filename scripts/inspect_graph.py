"""Print a local graph summary and a planted path without reading ground truth."""

import json

import networkx as nx

from tracelayer.graph_builder import blockchain_graph, build_evidence_graph, graph_summary, shortest_seed_distance
from tracelayer.ingestion import load_case


def main():
    """Inspect the demonstration seed path using only cleaned CSV evidence."""
    df, report = load_case()
    print('Validation:', json.dumps(report))
    if report['errors'] or report['invalid_rows']:
        raise SystemExit('Resolve validation errors before inspecting the demo graph')
    graph = build_evidence_graph(df)
    print('Graph:', json.dumps(graph_summary(graph)))
    path = nx.shortest_path(blockchain_graph(graph), ('WALLET', 'seed_wallet_demo'),
                            ('WALLET', 'wallet_target'))
    print('Path:', ' → '.join(graph.nodes[node]['id'] for node in path))
    print('Seed distance (blockchain edges):', shortest_seed_distance(graph, 'wallet_target'))


if __name__ == '__main__':
    main()
