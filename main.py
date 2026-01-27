import os
import json
import random
from collections import defaultdict
import networkx as nx
import pandas as pd
import io
import zipfile

# -------------------------
# Constants / fallback
# -------------------------
FALLBACK_JSON_PATH = "data/default_network.json"


# -------------------------
# Graph initialization
# -------------------------
if os.path.exists(FALLBACK_JSON_PATH):
    with open(FALLBACK_JSON_PATH, "r") as f:
        data = json.load(f)
    G = nx.node_link_graph(data, directed=True)
else:
    G = nx.DiGraph()

    # Example nodes
    example_nodes = [
        {"id": 0, "identity_type": "anonymous", "credulity": 0.6, "tendency_to_share": 0.9},
        {"id": 1, "identity_type": "verified",  "credulity": 1, "tendency_to_share": 0.3},
        {"id": 2, "identity_type": "anonymous", "credulity": 0.4, "tendency_to_share": 0.7}
    ]

    for nd in example_nodes:
        G.add_node(
            nd["id"],
            identity_type=nd["identity_type"],
            credulity=nd["credulity"],
            tendency_to_share=nd["tendency_to_share"],
            state="uninfected",
            infection_time=None
        )

    # Example edges
    example_edges = [
        (0, 1, {"trust_weight": 1.0}),
        (0, 2, {"trust_weight": 0.4}),
        (1, 2, {"trust_weight": 0.7})
    ]
    for u, v, attrs in example_edges:
        G.add_edge(u, v, **attrs)


# -------------------------
# Helper functions
# -------------------------
def get_nodes(G: nx.DiGraph):
    return list(G.nodes(data=False))


def get_nodes_with_data(G: nx.DiGraph):
    return list(G.nodes(data=True))


def neighbors(G: nx.DiGraph, n):
    return list(G.neighbors(n))


def get_node_attr(G: nx.DiGraph, n, key, default=None):
    return G.nodes[n].get(key, default)


def set_node_attr(G: nx.DiGraph, n, key, value):
    G.nodes[n][key] = value


def get_edge_attr(G: nx.DiGraph, u, v, key, default=None):
    return G.edges[u, v].get(key, default)


def get_infected_nodes(G: nx.DiGraph):
    return [n for n in get_nodes(G) if get_node_attr(G, n, "state") == "infected"]


# -------------------------
# Simulation
# -------------------------
def simulate(
    G,
    initial_infected_list,
    timesteps=10,
    random_seed=None,
    default_propensity_anonymous=0.8,
    default_propensity_verified=0.3,
    default_trust_from_verified=0.9,
    default_trust_from_anonymous=0.3
):
    
    if random_seed is not None:
        random.seed(random_seed)

    # Reset node states
    for n, data in G.nodes(data=True):
        set_node_attr(G, n, "state", data.get("state", "uninfected"))
        set_node_attr(G, n, "infection_time", data.get("infection_time", None))

    # Seed initial infected
    for s in initial_infected_list:
        if s is not None and not get_node_attr(G, s, "is_fact_checker", False) and get_node_attr(G, s, "state", None) is not None:
            set_node_attr(G, s, "state", "infected")
            set_node_attr(G, s, "infection_time", 0)

    time_series_new = []
    time_series_total = []
    current_infected = set(get_infected_nodes(G))
    infection_history = [set(current_infected)]
    time_series_new.append(len(current_infected))
    time_series_total.append(len(current_infected))

    print(f"[t=0] seeded infected: {sorted(current_infected)}")

    for t in range(1, timesteps + 1):
        exposures = defaultdict(list)

        for u in list(current_infected):
            if get_node_attr(G, u, "is_fact_checker", False):
                continue
            # Determine the node's effective tendency_to_share
            node_data = G.nodes[u]
            u_identity = node_data.get("identity_type", "anonymous")
            u_tendency = node_data.get(
                "tendency_to_share",
                default_propensity_anonymous if u_identity == "anonymous" else default_propensity_verified
            )

            for v in neighbors(G, u):
                if get_node_attr(G, v, "is_fact_checker", False):
                    continue
                v_state = get_node_attr(G, v, "state", "uninfected")
                if v_state == "uninfected":
                    cred_v = get_node_attr(G, v, "credulity", 0.0)
                    
                    # Determine effective trust for this edge
                    trust = get_edge_attr(G, u, v, "trust_weight", None)
                    if trust is None:
                        neighbor_identity = G.nodes[u].get("identity_type", "anonymous")
                        trust = default_trust_from_verified if neighbor_identity == "verified" else default_trust_from_anonymous

                    # Probability of exposure
                    p_exposure = cred_v * u_tendency * trust
                    if p_exposure > 0:
                        exposures[v].append(p_exposure)

        newly_infected = []
        for v, p_list in exposures.items():
            prob_no = 1.0
            for p_i in p_list:
                prob_no *= (1.0 - p_i)
            p_total = 1.0 - prob_no
            if random.random() < p_total:
                newly_infected.append(v)

        for v in newly_infected:
            set_node_attr(G, v, "state", "infected")
            set_node_attr(G, v, "infection_time", t)

        current_infected = set(get_infected_nodes(G))
        infection_history.append(set(current_infected))
        time_series_new.append(len(newly_infected))
        time_series_total.append(len(current_infected))
        print(f"[t={t}] newly infected: {sorted(newly_infected)}; total infected: {len(current_infected)}")

    infection_times = {n: get_node_attr(G, n, "infection_time") for n in get_nodes(G)}

    return {
        "time_series_new": time_series_new,
        "time_series_total": time_series_total,
        "infection_times": infection_times,
        "infection_history": infection_history,
        "final_infected": [n for n, it in infection_times.items() if it is not None]
    }

# -------------------------
# Export simulation metrics
# -------------------------
def export_simulation_metrics(results):
    """
    Export simulation results to a downloadable zip file containing CSVs:
    - time_series.csv: timestep, newly_infected, total_infected
    - infection_times.csv: per-node infection times
    - final_infected.csv: list of nodes infected at the end
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w") as zf:
        # 1. Time series
        df_times = pd.DataFrame({
            "timestep": list(range(len(results["time_series_total"]))),
            "newly_infected": results["time_series_new"],
            "total_infected": results["time_series_total"]
        })
        csv_buffer = io.StringIO()
        df_times.to_csv(csv_buffer, index=False)
        zf.writestr("time_series.csv", csv_buffer.getvalue())

        # 2. Infection times
        df_infection_times = pd.DataFrame.from_dict(
            results["infection_times"], orient="index", columns=["infection_time"]
        ).reset_index().rename(columns={"index": "node"})
        csv_buffer = io.StringIO()
        df_infection_times.to_csv(csv_buffer, index=False)
        zf.writestr("infection_times.csv", csv_buffer.getvalue())

        # 3. Final infected nodes
        df_final = pd.DataFrame({"final_infected": results["final_infected"]})
        csv_buffer = io.StringIO()
        df_final.to_csv(csv_buffer, index=False)
        zf.writestr("final_infected.csv", csv_buffer.getvalue())

    zip_buffer.seek(0)
    return zip_buffer.getvalue()  # bytes ready for download
