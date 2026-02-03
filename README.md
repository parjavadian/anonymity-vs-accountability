# Misinformation Spread Simulator — Anonymity vs Accountability

A small interactive simulator to explore how misinformation spreads in a social network, and how anonymity, trust, and fact-checking change that spread.  

---

## Quick start

Clone the repo and run the app:

```bash
streamlit run app.py
```
---

## Implementation Overview

- **Nodes**: each node models a user with the following properties:
  - `identity_type` — "anonymous" or "verified"
  - `credulity` — probability to accept misinformation (0..1)
  - `tendency_to_share` — probability to forward once infected (0..1)
  - `is_fact_checker` — if true, node never becomes infected or spreads

- **Edges**: carry `trust_weight` (0..1). If missing, the simulator uses default trust values based on sender identity.

- **Infection model** (implemented in `simulate` in `main.py`):
  - For every infected node, compute exposure probability for each uninfected neighbor:
    ```
    p_exposure = credulity_of_receiver * tendency_of_sender * trust_of_edge
    ```
  - If multiple infected neighbors expose the same node in a timestep, combine exposures into:
    ```
    p_total = 1 - ∏(1 - p_i)
    ```
  - Use random sampling to decide if the node becomes infected that timestep.
  - Record: newly infected per timestep, total infected per timestep, infection time per node, and full infection history.

- **Export**: `export_simulation_metrics(results)` returns ZIP bytes with:
  - `time_series.csv` — timestep, newly_infected, total_infected
  - `infection_times.csv` — node -> infection_time
  - `final_infected.csv` — nodes infected at the end

---

## Input format (for uploads)

The app accepts NetworkX node-link JSON (the format produced by `nx.node_link_data`).

Recommended node fields (when possible):
- `id` (int or str)
- `identity_type` (`"anonymous"` or `"verified"`)
- `credulity` (float 0..1)
- `tendency_to_share` (float 0..1)
- `is_fact_checker` (boolean, optional)

Edge fields:
- `trust_weight` (float 0..1, optional)

If fields are missing, the app uses the default values set in the UI.

---

## UI features

- Upload a network JSON or use the default example.
- Choose initial infected nodes manually or pick random ones.
- Set number of timesteps.
- Set default tendency-to-share and default trust values for anonymous vs verified users.
- Step through timesteps in the UI and watch the network evolve.
- Interactive PyVis graph: infected nodes shown in red, uninfected in gray; shapes mark anonymous / verified / fact-checker.
- Download all metrics as a ZIP file.
