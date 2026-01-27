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

        if data.get("is_fact_checker", False):
            shape = "triangleDown"
        else:
            shape = "dot" if data.get("identity_type") == "anonymous" else "star"

        net.add_node(
            n,
            label=str(n),
            color=color,
            title=f"Node {n}<br>"
                  f"identity: {data.get('identity_type')}<br>"
                  f"credulity: {data.get('credulity')}<br>"
                  f"tendency_to_share: {data.get('tendency_to_share')}",
            x=x * 200,
            y=y * 200,
            fixed=True,
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
if "current_timestep" not in st.session_state:
    st.session_state.current_timestep = 0
if "initial_infected" not in st.session_state:
    st.session_state.initial_infected = []
if "pos" not in st.session_state:
    st.session_state.pos = None


# -------------------------
# Streamlit page config
# -------------------------
st.set_page_config(layout="wide")
st.title("Misinformation Spread Simulator")


# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Simulation Parameters")

timesteps = st.sidebar.number_input(
    "Number of timesteps",
    min_value=1,
    max_value=200,
    value=20,
    step=1
)

uploaded_file = st.sidebar.file_uploader("Upload network JSON", type="json")
if uploaded_file is not None:
    data = json.load(uploaded_file)
    G = nx.node_link_graph(data)
    st.sidebar.write(f"Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
else:
    G = default_G
    st.sidebar.write(f"Using default network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


undirected_G = G.to_undirected()
st.session_state.pos = nx.spring_layout(undirected_G, seed=42)


# -------------------------
# Initial infected selection
# -------------------------
all_nodes = get_nodes(G)

non_fact_checker_nodes = [
    n for n in all_nodes if not G.nodes[n].get("is_fact_checker", False)
]

st.session_state.initial_infected = [
    n for n in st.session_state.initial_infected if n in non_fact_checker_nodes
]

if not st.session_state.initial_infected and non_fact_checker_nodes:
    st.session_state.initial_infected = [non_fact_checker_nodes[0]]

st.session_state.initial_infected = st.sidebar.multiselect(
    "Initial infected nodes (non-fact-checkers only)",
    options=non_fact_checker_nodes,
    default=st.session_state.initial_infected
)

num_random = st.sidebar.number_input(
    "Number of random initial infected nodes",
    min_value=1,
    max_value=len(non_fact_checker_nodes),
    value=1,
    step=1
)

if st.sidebar.button("Randomize initial infected"):
    st.session_state.initial_infected = random.sample(non_fact_checker_nodes, k=num_random)



st.sidebar.subheader("Anonymity / Accountability Defaults")

default_propensity_anonymous = st.sidebar.slider("Default tendency to share (anonymous)", 0.0, 1.0, 0.8, 0.05)
default_propensity_verified = st.sidebar.slider("Default tendency to share (verified)", 0.0, 1.0, 0.3, 0.05)
default_trust_from_verified = st.sidebar.slider("Default trust if neighbor is verified", 0.0, 1.0, 0.9, 0.05)
default_trust_from_anonymous = st.sidebar.slider("Default trust if neighbor is anonymous", 0.0, 1.0, 0.3, 0.05)


# -------------------------
# Run simulation
# -------------------------
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
# Visualization
# -------------------------
results = st.session_state.results

if results is not None:
    st.subheader("Interactive network view")

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

    st.markdown("""
**Legend:**

🔴 infected  
⚪ uninfected  
● anonymous  
⭐ verified  
🔻 fact-checker  
""")

    infected_at_t = results["infection_history"][st.session_state.current_timestep]

    net = nx_to_pyvis(G, infected_at_t, st.session_state.pos)

    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    net.save_graph(tmp_file.name)
    with open(tmp_file.name, "r", encoding="utf-8") as f:
        html = f.read()
    os.unlink(tmp_file.name)

    st.components.v1.html(html, height=650)
    st.write(f"Current timestep: {st.session_state.current_timestep}")

    # Plot
    st.subheader("Infection over time")
    fig, ax = plt.subplots()
    ax.plot(results["time_series_total"], label="Total infected")
    ax.plot(results["time_series_new"], label="Newly infected")
    ax.legend()
    st.pyplot(fig)

    # Download metrics
    zip_bytes = export_simulation_metrics(results)
    st.download_button("Download all metrics", zip_bytes, "simulation_metrics.zip")
