"""Three-view local interface for the TraceLayer investigation prototype."""

from io import BytesIO

import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tracelayer.graph_builder import get_entity_neighborhood, graph_summary
from tracelayer.ingestion import DEFAULT_CASE
from tracelayer.pipeline import run_pipeline

st.set_page_config(page_title='TraceLayer | Operation Meridian', page_icon='◈', layout='wide')


@st.cache_data(show_spinner='Correlating local evidence…')
def analyze_case(case_bytes):
    """Cache pipeline results by file contents, so dataset changes invalidate them."""
    return run_pipeline(BytesIO(case_bytes))


def show_lead(lead):
    """Present independent scores and the explanations supplied by the pipeline."""
    with st.container(border=True):
        st.subheader(lead.entity_id)
        left, right = st.columns(2)
        left.metric('Risk Score', f'{lead.risk_score:.1f}/100')
        right.metric('Confidence Score', f'{lead.confidence_score:.1f}/100')
        st.markdown('**Why flagged / supporting evidence**')
        for reason in lead.reasons:
            st.write('• ' + reason)


def neighborhood_figure(graph, selected):
    """Render local evidence with typed nodes and directed edge arrows."""
    positions = nx.spring_layout(graph, seed=42, iterations=45)
    traces, arrows = [], []
    for source, target in set(graph.edges()):
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        arrows.append(dict(x=x1 * 0.88 + x0 * 0.12, y=y1 * 0.88 + y0 * 0.12,
                           ax=x0 * 0.75 + x1 * 0.25, ay=y0 * 0.75 + y1 * 0.25,
                           xref='x', yref='y', axref='x', ayref='y', showarrow=True,
                           arrowhead=2, arrowsize=0.7, arrowwidth=1, arrowcolor='#64748b'))
    for category, color, symbol in [('IP', '#60a5fa', 'square'), ('TXID', '#fbbf24', 'diamond'),
                                     ('WALLET', '#2dd4bf', 'circle')]:
        nodes = [node for node in graph if node[0] == category]
        traces.append(go.Scatter(x=[positions[node][0] for node in nodes],
            y=[positions[node][1] for node in nodes], mode='markers', name=category,
            marker=dict(color=color, symbol=symbol, size=[21 if node == selected else 11 for node in nodes],
                        line=dict(color='#e2e8f0', width=1)),
            text=[f'{category}: {node[1]}' for node in nodes], hovertemplate='%{text}<extra></extra>'))
    figure = go.Figure(traces)
    figure.update_layout(height=510, margin=dict(l=10, r=10, t=10, b=10), annotations=arrows,
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          legend=dict(orientation='h', x=0, y=1.05),
                          xaxis=dict(visible=False), yaxis=dict(visible=False), hovermode='closest')
    return figure


st.title('TraceLayer')
st.caption('Offline Bitcoin Investigation Prototype')
header_left, header_right = st.columns([3, 1])
header_left.subheader('Operation Meridian')
header_right.markdown('**:orange[SYNTHETIC DATASET]**')
st.caption('Ingest → Correlate → Detect → Explain → Prioritize')
try:
    result = analyze_case(DEFAULT_CASE.read_bytes())
except (OSError, ValueError) as error:
    st.error(f'Unable to load the local case: {error}')
    st.stop()

leads, graph, report = result['leads'], result['graph'], result['validation']
summary = graph_summary(graph)
overview, ranked, evidence = st.tabs(['Case Overview', 'Ranked Leads', 'Evidence Graph / Lead Details'])

with overview:
    st.subheader('Case at a glance')
    metrics = [('Records Processed', report['total_rows']), ('Unique Wallets', summary['wallet_nodes']),
               ('Unique Transactions', summary['txid_nodes']), ('Graph Nodes', summary['total_nodes']),
               ('Graph Edges', summary['total_edges']), ('Ranked Leads', len(leads))]
    for column, (label, value) in zip(st.columns(3), metrics[:3]):
        column.metric(label, f'{value:,}')
    for column, (label, value) in zip(st.columns(3), metrics[3:]):
        column.metric(label, f'{value:,}')
    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown('**Environment:** Offline / Local')
        st.markdown('**Cloud Dependency:** None')
        st.info('Synthetic observations for demonstrating investigative review. No live Bitcoin traffic or external APIs.')
    with right:
        st.markdown('**Validation summary**')
        st.dataframe(pd.DataFrame([{'Total Rows': report['total_rows'], 'Valid Rows': report['valid_rows'],
            'Invalid Rows': report['invalid_rows'], 'Duplicate TXIDs': report['duplicate_txids'],
            'Missing Values': report['missing_required_values']}]), hide_index=True, width='stretch')
        if report['invalid_rows']:
            st.warning('Rejected records are excluded from analysis. Inspect the validation details.')
        else:
            st.success('All records passed validation.')
        with st.expander('Validation details'):
            st.json(report)
    st.caption('Risk weights: 50% anomaly · 30% peeling indicator · 20% seed proximity. Demo parameters, not calibrated probabilities.')

with ranked:
    st.subheader('Prioritized investigative leads')
    left, right = st.columns(2)
    minimum = left.slider('Minimum risk score', 0, 100, 0)
    search = right.text_input('Search entity ID', placeholder='Enter part of a wallet identifier')
    filtered = leads[(leads.risk_score >= minimum) & leads.entity_id.str.contains(search.strip(), case=False, regex=False)]
    st.caption(f'{len(filtered)} of {len(leads)} leads · scores out of 100; individual signals range from 0 to 1')
    display = filtered[['rank', 'entity_id', 'risk_score', 'confidence_score', 'anomaly_score',
                        'peeling_signal', 'seed_proximity_score', 'reasons']].copy()
    display['reasons'] = display.reasons.map(lambda reasons: ' '.join(reasons))
    display.columns = ['Rank', 'Entity', 'Risk', 'Confidence', 'Anomaly', 'Peeling', 'Seed Proximity', 'Reasons']
    st.dataframe(display, hide_index=True, width='stretch', height=360,
        column_config={'Risk': st.column_config.ProgressColumn(min_value=0, max_value=100, format='%.1f'),
                       'Confidence': st.column_config.NumberColumn(format='%.1f'),
                       'Anomaly': st.column_config.NumberColumn(format='%.3f'),
                       'Seed Proximity': st.column_config.NumberColumn(format='%.3f')})
    if filtered.empty:
        st.info('No leads match these filters. Lower the minimum risk or clear the search.')
    else:
        selected_lead = st.selectbox('Select a lead', filtered.entity_id.tolist(), key='ranked_entity')
        show_lead(leads.set_index('entity_id', drop=False).loc[selected_lead])
    st.warning('Risk scores prioritize investigative review and do not establish criminality.')
    st.info('Confidence reflects supporting evidence strength and is not a probability of guilt.')

with evidence:
    st.subheader('Cross-layer evidence')
    st.warning('Network evidence is supporting evidence and does not independently prove wallet ownership.')
    selected_id = st.selectbox('Choose a ranked entity', leads.entity_id.tolist(), key='graph_entity')
    selected = ('WALLET', selected_id)
    depth = st.select_slider('Neighborhood depth', options=[1, 2], value=2)
    neighborhood = get_entity_neighborhood(graph, selected, depth)
    # Bound drawing cost only; the underlying graph and lead evidence stay complete.
    full_count = len(neighborhood)
    if full_count > 180:
        distances = nx.single_source_shortest_path_length(neighborhood.to_undirected(as_view=True), selected)
        kept = sorted(neighborhood, key=lambda node: (distances[node], node))[:180]
        neighborhood = neighborhood.subgraph(kept).copy()
        st.caption(f'Drawing 180 of {full_count} neighborhood nodes for readability; evidence tables remain complete.')
    st.plotly_chart(neighborhood_figure(neighborhood, selected), width='stretch')
    st.caption('Blue squares: IP · Gold diamonds: TXID · Teal circles: WALLET. Arrows show evidence direction; the selected wallet is enlarged. Parallel edges overlap visually.')
    lead = leads.set_index('entity_id').loc[selected_id]
    neighbors = sorted(set(graph.predecessors(selected)) | set(graph.successors(selected)))
    txids = {node[1] for node in neighbors if node[0] == 'TXID'}
    transactions = result['data'][result['data'].txid.isin(txids)].copy()
    observations = transactions[['timestamp', 'txid', 'src_ip', 'src_port', 'dst_ip', 'dst_port']]
    left, right, third = st.columns(3)
    left.metric('Relevant Transactions', len(txids))
    right.metric('Graph Neighbours', len(neighbors))
    third.metric('Seed Distance (edges)', 'Unreachable' if pd.isna(lead.seed_distance) else str(int(lead.seed_distance)))
    node = st.selectbox('Inspect node details', sorted(neighborhood), format_func=lambda item: f'{item[0]} · {item[1]}',
                        index=sorted(neighborhood).index(selected))
    st.json({key: str(value) if isinstance(value, pd.Timestamp) else value for key, value in graph.nodes[node].items()}, expanded=False)
    with st.expander('Relevant transactions and supporting IP observations', expanded=True):
        st.dataframe(observations, hide_index=True, width='stretch')
        st.caption('These are synthetic CSV associations, not independent captures or verified ownership.')
    with st.expander('Blockchain transaction details'):
        for column in ('input_addresses', 'output_addresses', 'input_amounts', 'output_amounts', 'fee'):
            transactions[column] = transactions[column].map(str)
        st.dataframe(transactions, hide_index=True, width='stretch')
    with st.expander('Direct graph neighbours'):
        st.dataframe(pd.DataFrame(neighbors, columns=['Node Type', 'Entity']), hide_index=True, width='stretch')

st.caption('TraceLayer · Small offline proof-of-concept · Synthetic evidence only')
