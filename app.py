import os
import tempfile
import random
import json

import streamlit as st
import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network

from main import simulate, get_nodes, export_simulation_metrics
from main import G as default_G


# -------------------------
# Helper function
# -------------------------
def nx_to_pyvis(G, infected_nodes, pos):
    net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="black", notebook=False)
    
    for n, data in G.nodes(data=True):
        x, y = pos[n]
        color = "red" if n in infected_nodes else "#cccccc"
        shape = "dot" if data.get("identity_type") == "anonymous" else "star"
        net.add_node(
            n,
            label=str(n),
            color=color,
            title=f"Node {n}<br>identity: {data.get('identity_type')}<br>credulity: {data.get('credulity')}<br>tendency_to_share: {data.get('tendency_to_share')}",
            x=x*200,
            y=y*200,
            fixed=True,
            font={"size": 1000, "color": "black", "face": "arial"},
            shape=shape
        )

    for u, v, data in G.edges(data=True):
        trust = data.get("trust_weight", 0.0)
        net.add_edge(u, v, value=trust, title=f"trust_weight={trust}", arrows="to")

    return net


# -------------------------
# Session state init
# -------------------------
if "results" not in st.session_state:
    st.session_state.results = None
if "network_html" not in st.session_state:
    st.session_state.network_html = None
if "current_timestep" not in st.session_state:
    st.session_state.current_timestep = 0
if "initial_infected" not in st.session_state:
    st.session_state.initial_infected = []


# -------------------------
# Streamlit page config
# -------------------------
st.set_page_config(layout="wide")
st.title("Misinformation Spread Simulator")


# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Simulation Parameters")

timesteps = st.sidebar.slider("Timesteps", 1, 30, 10)

# Optional: Upload network JSON
uploaded_file = st.sidebar.file_uploader("Upload network JSON", type="json")
if uploaded_file is not None:
    data = json.load(uploaded_file)
    G = nx.node_link_graph(data)
    st.sidebar.write(f"Loaded graph from upload: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
else:
    G = default_G
    st.sidebar.write(f"Using default network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Node layout
undirected_G = G.to_undirected()
st.session_state.pos = nx.spring_layout(undirected_G, seed=46)

# Initial infected nodes selection
all_nodes = get_nodes(G)
if not st.session_state.initial_infected:
    st.session_state.initial_infected = [all_nodes[0]]

st.session_state.initial_infected = st.sidebar.multiselect(
    "Initial infected nodes",
    options=all_nodes,
    default=st.session_state.initial_infected
)

# Random initial infected
num_random = st.sidebar.slider("Number of random initial infected nodes", 1, len(all_nodes), 1)
if st.sidebar.button("Randomize initial infected"):
    st.session_state.initial_infected = random.sample(all_nodes, k=num_random)
    st.sidebar.write(f"Random initial infected nodes: {sorted(st.session_state.initial_infected)}")
st.sidebar.subheader("Anonymity / Accountability Defaults")

default_propensity_anonymous = st.sidebar.slider(
    "Default tendency to share (anonymous node)",
    0.0, 1.0, 0.8, 0.05
)
default_propensity_verified = st.sidebar.slider(
    "Default tendency to share (verified node)",
    0.0, 1.0, 0.3, 0.05
)
default_trust_from_verified = st.sidebar.slider(
    "Default trust if neighbor is verified",
    0.0, 1.0, 0.9, 0.05
)
default_trust_from_anonymous = st.sidebar.slider(
    "Default trust if neighbor is anonymous",
    0.0, 1.0, 0.3, 0.05
)
# Run simulation
run = st.sidebar.button("Run simulation")
if run:
    G_run = G.copy()
    st.session_state.results = simulate(
        G_run,
        initial_infected_list=st.session_state.initial_infected,
        timesteps=timesteps,
        default_propensity_anonymous=default_propensity_anonymous,
        default_propensity_verified=default_propensity_verified,
        default_trust_from_verified=default_trust_from_verified,
        default_trust_from_anonymous=default_trust_from_anonymous
    )
    st.session_state.current_timestep = 0


# -------------------------
# Visualization and metrics
# -------------------------
results = st.session_state.results
if results is not None:
    # Metrics download
    zip_bytes = export_simulation_metrics(results)
    st.download_button(
        label="Download all metrics",
        data=zip_bytes,
        file_name="simulation_metrics.zip",
        mime="application/zip"
    )

    st.subheader("Interactive network view")

    # Step buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Step -1") and st.session_state.current_timestep > 0:
            st.session_state.current_timestep -= 1
    with col2:
        if st.button("Step +1") and st.session_state.current_timestep < len(results["infection_history"]) - 1:
            st.session_state.current_timestep += 1
    with col3:
        if st.button("Go to end"):
            st.session_state.current_timestep = len(results["infection_history"]) - 1

    # Infection at current timestep
    infected_at_t = results["infection_history"][st.session_state.current_timestep]

    G_vis = G.copy()
    net = nx_to_pyvis(G_vis, infected_at_t, st.session_state.pos)

    # Generate HTML once per timestep
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    net.save_graph(tmp_file.name)
    with open(tmp_file.name, "r", encoding="utf-8") as f:
        st.session_state.network_html = f.read()
    os.unlink(tmp_file.name)

    # Render network
    st.components.v1.html(st.session_state.network_html, height=650)
    st.write(f"Current timestep: {st.session_state.current_timestep}")

    # Infection over time plot
    st.subheader("Infection over time")
    fig, ax = plt.subplots()
    ax.plot(results["time_series_total"], label="Total infected")
    ax.plot(results["time_series_new"], label="Newly infected")
    ax.set_xlabel("Timestep")
    ax.set_ylabel("Number of nodes")
    ax.legend()
    st.pyplot(fig)
