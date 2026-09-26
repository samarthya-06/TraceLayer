"""Check graph evidence semantics and directed seed reachability."""

import unittest
from decimal import Decimal

import networkx as nx
import pandas as pd

from tracelayer.graph_builder import (blockchain_graph, build_evidence_graph,
                                     get_entity_neighborhood, graph_summary, shortest_seed_distance)
from tracelayer.ingestion import load_case


class GraphTests(unittest.TestCase):
    """Test graph behavior using CSV evidence rather than ground-truth labels."""

    @classmethod
    def setUpClass(cls):
        """Build the demo graph once for read-only assertions."""
        cls.df, _ = load_case()
        cls.graph = build_evidence_graph(cls.df)

    def test_edges_and_evidence(self):
        """Preserve wallet amounts and separate source/destination IP evidence."""
        row = self.df.iloc[0]
        tx = ('TXID', row.txid)
        for wallet in row.input_addresses:
            self.assertTrue(self.graph.has_edge(('WALLET', wallet), tx))
        for wallet in row.output_addresses:
            self.assertTrue(self.graph.has_edge(tx, ('WALLET', wallet)))
        for role in ('src', 'dst'):
            edges = self.graph.get_edge_data(('IP', row[f'{role}_ip']), tx)
            evidence = next(attrs for attrs in edges.values() if attrs['network_role'] == role)
            self.assertEqual(evidence['port'], row[f'{role}_port'])
            self.assertEqual(evidence['timestamp'], row.timestamp)
            self.assertTrue(evidence['evidence_only'])
        amount_edge = next(iter(self.graph.get_edge_data(tx, ('WALLET', row.output_addresses[0])).values()))
        self.assertEqual(amount_edge['amount'], row.output_amounts[0])
        self.assertEqual(amount_edge['relationship_type'], 'output_to')
        for _, attrs in self.graph.nodes(data=True):
            self.assertIn('id', attrs)
            self.assertIn('node_type', attrs)

    def test_seed_path(self):
        """The target is four directed edges from the configured seed."""
        chain = blockchain_graph(self.graph)
        path = nx.shortest_path(chain, ('WALLET', 'seed_wallet_demo'), ('WALLET', 'wallet_target'))
        wallets = [node[1] for node in path if node[0] == 'WALLET']
        self.assertEqual(wallets, ['seed_wallet_demo', 'wallet_intermediate', 'wallet_target'])
        self.assertEqual(shortest_seed_distance(self.graph, 'wallet_target'), 4)
        self.assertEqual(shortest_seed_distance(self.graph, 'seed_wallet_demo'), 0)
        self.assertIsNone(shortest_seed_distance(self.graph, 'wallet_burst_demo'))
        self.assertIsNone(shortest_seed_distance(self.graph, 'absent'))
        self.assertFalse(nx.has_path(chain, ('WALLET', 'wallet_target'), ('WALLET', 'seed_wallet_demo')))

    def test_network_cannot_shortcut_seed_path(self):
        """Even an added directed IP shortcut is ignored for seed distance."""
        graph = self.graph.copy()
        ip = next(node for node in graph if node[0] == 'IP')
        graph.add_edge(('WALLET', 'seed_wallet_demo'), ip, relationship_type='associated_with')
        graph.add_edge(ip, ('WALLET', 'wallet_target'), relationship_type='associated_with')
        self.assertEqual(shortest_seed_distance(graph, 'wallet_target'), 4)

    def test_neighborhood_and_summary(self):
        """Report correct counts and retain edge directions in local neighborhoods."""
        summary = graph_summary(self.graph)
        self.assertEqual(summary['wallet_nodes'], 645)
        self.assertEqual(summary['txid_nodes'], 1000)
        self.assertEqual(summary['total_nodes'], sum(summary[key] for key in ('wallet_nodes', 'txid_nodes', 'ip_nodes')))
        expected_edges = sum(2 + len(row.input_addresses) + len(row.output_addresses)
                             for row in self.df.itertuples())
        self.assertEqual(summary['total_edges'], expected_edges)
        local = get_entity_neighborhood(self.graph, 'wallet_target', depth=2)
        self.assertIn(('WALLET', 'wallet_intermediate'), local)
        self.assertTrue(local.is_directed())
        self.assertEqual(len(get_entity_neighborhood(self.graph, 'wallet_target', 0)), 1)
        with self.assertRaises(ValueError):
            get_entity_neighborhood(self.graph, 'wallet_target', -1)
        with self.assertRaises(KeyError):
            get_entity_neighborhood(self.graph, 'missing')
        self.assertEqual(graph_summary(build_evidence_graph(self.df.iloc[:0]))['total_nodes'], 0)

    def test_parallel_evidence_and_namespaces(self):
        """Repeated wallets and identical IP endpoints retain distinct evidence."""
        row = self.df.iloc[0].to_dict()
        row.update(txid='same_id', input_addresses=['same_id', 'same_id'],
                   input_amounts=[Decimal('1'), Decimal('2')], dst_ip=row['src_ip'])
        graph = build_evidence_graph(pd.DataFrame([row]))
        self.assertEqual(graph.number_of_edges(('WALLET', 'same_id'), ('TXID', 'same_id')), 2)
        self.assertEqual(graph.number_of_edges(('IP', row['src_ip']), ('TXID', 'same_id')), 2)
        with self.assertRaises(ValueError):
            get_entity_neighborhood(graph, 'same_id')
        self.assertEqual(len(get_entity_neighborhood(graph, ('TXID', 'same_id'), 0)), 1)
        self.assertIsNone(shortest_seed_distance(build_evidence_graph(self.df, seed_wallets=()), 'wallet_target'))
