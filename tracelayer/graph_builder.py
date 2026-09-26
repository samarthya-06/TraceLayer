"""Build supporting network evidence and directed blockchain transaction links."""

import networkx as nx


def build_evidence_graph(df, seed_wallets=("seed_wallet_demo",)):
    """Build a MultiDiGraph from cleaned ingestion rows, without ground truth."""
    graph = nx.MultiDiGraph()
    seeds = set(seed_wallets)

    def add_entity(node_type, entity_id):
        """Namespace entity keys to prevent collisions between different types."""
        key = (node_type, entity_id)
        graph.add_node(key, id=entity_id, node_type=node_type,
                       risk_seed=node_type == 'WALLET' and entity_id in seeds)
        return key

    for row in df.to_dict('records'):
        tx = add_entity('TXID', row['txid'])
        graph.nodes[tx].update(timestamp=row['timestamp'], fee=row['fee'], script_type=row['script_type'])
        for role in ('src', 'dst'):
            ip = add_entity('IP', row[f'{role}_ip'])
            graph.add_edge(ip, tx, relationship_type='associated_with',
                           timestamp=row['timestamp'], port=row[f'{role}_port'],
                           network_role=role, evidence_only=True)
        for side in ('input', 'output'):
            for index, (address, amount) in enumerate(zip(row[f'{side}_addresses'], row[f'{side}_amounts'])):
                wallet = add_entity('WALLET', address)
                source, target = (wallet, tx) if side == 'input' else (tx, wallet)
                graph.add_edge(source, target, relationship_type=f'{side}_to',
                               timestamp=row['timestamp'], amount=amount, amount_unit='BTC',
                               address_index=index)
    return graph


def resolve_entity(graph, entity_id):
    """Resolve a typed key or an unambiguous raw identifier, raising if absent."""
    if entity_id in graph:
        return entity_id
    matches = [key for key, attrs in graph.nodes(data=True) if attrs['id'] == entity_id]
    if not matches:
        raise KeyError(f'Entity not found: {entity_id}')
    if len(matches) > 1:
        raise ValueError('Ambiguous entity ID; pass (node_type, id)')
    return matches[0]


def get_entity_neighborhood(graph, entity_id, depth=2):
    """Return a copied induced neighborhood using both directions for discovery."""
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
        raise ValueError('depth must be a nonnegative integer')
    entity = resolve_entity(graph, entity_id)
    nodes = nx.single_source_shortest_path_length(graph.to_undirected(as_view=True), entity, cutoff=depth)
    return graph.subgraph(nodes).copy()


def blockchain_graph(graph):
    """Return directed wallet/TXID links, excluding all network correlations."""
    result = nx.DiGraph()
    result.add_nodes_from((node, attrs.copy()) for node, attrs in graph.nodes(data=True)
                          if attrs['node_type'] in ('WALLET', 'TXID'))
    result.add_edges_from((source, target) for source, target, attrs in graph.edges(data=True)
                          if attrs.get('relationship_type') in ('input_to', 'output_to')
                          and source in result and target in result)
    return result


def shortest_seed_distance(graph, wallet_id):
    """Return directed blockchain edge distance from a seed, or None if unreachable."""
    try:
        wallet = resolve_entity(graph, wallet_id)
    except KeyError:
        return None
    if graph.nodes[wallet]['node_type'] != 'WALLET':
        raise ValueError('Seed distance requires a WALLET entity')
    chain = blockchain_graph(graph)
    distances = []
    for seed, attrs in chain.nodes(data=True):
        if attrs['node_type'] == 'WALLET' and attrs.get('risk_seed', False):
            try:
                distances.append(nx.shortest_path_length(chain, seed, wallet))
            except nx.NetworkXNoPath:
                pass
    return min(distances) if distances else None


def graph_summary(graph):
    """Count entities and evidence edges by type."""
    types = [attrs['node_type'] for _, attrs in graph.nodes(data=True)]
    return dict(total_nodes=graph.number_of_nodes(), total_edges=graph.number_of_edges(),
                wallet_nodes=types.count('WALLET'), txid_nodes=types.count('TXID'),
                ip_nodes=types.count('IP'))
