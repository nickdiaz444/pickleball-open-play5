import streamlit as st
import json
from pathlib import Path
import random
from itertools import combinations

# ────────────────────────────── FILES ──────────────────────────────
DATA_FILE = Path("pickleball_data.json")
CONFIG_FILE = Path("pickleball_config.json")

# ────────────────────────────── DEFAULTS ──────────────────────────────
DEFAULT_MAX_PLAYERS = 20
DEFAULT_NUM_COURTS = 3
MAX_STREAK = 2  # Max consecutive games per player

# ────────────────────────────── HELPERS ──────────────────────────────
def load_json(path, default):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def rerun_app():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# Track past matchups for soft uniqueness
def count_repeat_matches(players, history):
    repeats = 0
    current_pairs = list(combinations(players, 2))
    for match in history:
        past_pairs = list(combinations(match['winners'] + match['losers'], 2))
        for pair in current_pairs:
            if pair in past_pairs or (pair[1], pair[0]) in past_pairs:
                repeats += 1
    return repeats

# ────────────────────────────── LOAD CONFIG & DATA ──────────────────────────────
config = load_json(CONFIG_FILE, {"max_players": DEFAULT_MAX_PLAYERS, "num_courts": DEFAULT_NUM_COURTS})
data = load_json(DATA_FILE, {
    "players": [],
    "queue": [],
    "courts": [[] for _ in range(config["num_courts"])],
    "streaks": {},
    "history": []
})

# ────────────────────────────── LOGIC ──────────────────────────────
def initialize_queue():
    if not data["players"]:
        st.warning("Add players first.")
        return
    data["queue"] = data["players"][:]
    random.shuffle(data["queue"])
    save_json(DATA_FILE, data)
    rerun_app()

def assign_all_courts():
    for i in range(config["num_courts"]):
        assign_court(i)
    save_json(DATA_FILE, data)
    rerun_app()

def assign_court(court_index):
    # Keep players with streak < MAX_STREAK
    staying = [p for p in data["courts"][court_index] if data["streaks"].get(p,0) < MAX_STREAK]

    # Fill remaining spots
    while len(staying) < 4 and data["queue"]:
        # Choose next player that minimizes repeat matches
        best_candidate = data["queue"][0]
        min_repeats = count_repeat_matches(staying + [best_candidate], data["history"])
        for candidate in data["queue"]:
            repeats = count_repeat_matches(staying + [candidate], data["history"])
            if repeats < min_repeats:
                min_repeats = repeats
                best_candidate = candidate
        staying.append(best_candidate)
        data["queue"].remove(best_candidate)

    data["courts"][court_index] = staying

def process_court_result(court_index, winning_team, rerun=True):
    court = data["courts"][court_index]
    if len(court) < 4:
        st.warning("Not enough players on this court.")
        return

    winners = court[:2] if winning_team == "Team 1" else court[2:]
    losers = court[2:] if winning_team == "Team 1" else court[:2]

    new_court = []

    # Handle winners
    for w in winners:
        streak = data["streaks"].get(w, 0)
        if streak < MAX_STREAK:
            new_court.append(w)
            data["streaks"][w] = streak + 1
        else:
            data["streaks"][w] = 0
            data["queue"].append(w)

    # Handle losers
    for l in losers:
        data["streaks"][l] = 0
        data["queue"].append(l)

    # Fill remaining spots
    while len(new_court) < 4 and data["queue"]:
        # minimize repeat matches
        best_candidate = data["queue"][0]
        min_repeats = count_repeat_matches(new_court + [best_candidate], data["history"])
        for candidate in data["queue"]:
            repeats = count_repeat_matches(new_court + [candidate], data["history"])
            if repeats < min_repeats:
                min_repeats = repeats
                best_candidate = candidate
        new_court.append(best_candidate)
        data["queue"].remove(best_candidate)

    data["courts"][court_index] = new_court
    data["history"].append({
        "court": court_index + 1,
        "winners": winners,
        "losers": losers
    })

    save_json(DATA_FILE, data)
    if rerun:
        rerun_app()

def reset_all_data():
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    st.session_state.clear()
    rerun_app()

def reset_streaks():
    for p in data["streaks"]:
        data["streaks"][p] = 0
    save_json(DATA_FILE, data)
    st.success("All player streaks reset to 0")
    rerun_app()

# ────────────────────────────── UI ──────────────────────────────
st.set_page_config(page_title="🏓 Pickleball Scheduler", layout="wide")
st.title("🏓 Pickleball Open Play Scheduler")

# Sidebar configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    max_players = st.slider("Max Players", 8, 30, config["max_players"], 1)
    num_courts = st.slider("Number of Courts", 1, 5, config["num_courts"], 1)

    if st.button("💾 Save Config"):
        config["max_players"] = max_players
        config["num_courts"] = num_courts
        save_json(CONFIG_FILE, config)
        data["courts"] = [[] for _ in range(config["num_courts"])]
        save_json(DATA_FILE, data)
        rerun_app()

    st.divider()
    st.write("### Add Players (one per line)")
    new_players_text = st.text_area("Enter player names:", height=150)
    if st.button("Add / Update Players"):
        new_players = [p.strip() for p in new_players_text.splitlines() if p.strip()]
        for p in new_players:
            if p not in data["players"]:
                data["players"].append(p)
                data["queue"].append(p)
                data["streaks"][p] = 0
        save_json(DATA_FILE, data)
        rerun_app()

    st.write("### Active Players")
    active_cols = st.columns(2)
    for i, p in enumerate(data["players"]):
        col = active_cols[i % 2]
        active = col.checkbox(f"{p}", value=(p in data["queue"]))
        if active and p not in data["queue"]:
            data["queue"].append(p)
        elif not active and p in data["queue"]:
            data["queue"].remove(p)
    save_json(DATA_FILE, data)

    st.divider()
    if st.button("Initialize Queue"):
        initialize_queue()
    if st.button("Assign all courts"):
        assign_all_courts()
    if st.button("Reset everything"):
        reset_all_data()
    if st.button("🔄 Reset All Player Streaks"):
        reset_streaks()

# Display player queue
st.subheader("🎯 Player Queue")
st.write(", ".join(data["queue"]) if data["queue"] else "Queue is empty — add players or initialize.")

# Display courts
st.subheader("🏟️ Courts")
cols = st.columns(config["num_courts"])

for i, col in enumerate(cols):
    with col:
        st.markdown(f"### Court {i+1}")
        court = data["courts"][i]
        if not court or len(court) < 4:
            st.info("No game assigned or incomplete court.")
        else:
            st.write(f"**Team 1:** {court[0]} & {court[1]}")
            st.write(f"**Team 2:** {court[2]} & {court[3]}")

            key_name = f"winner_{i}"
            if key_name not in st.session_state:
                st.session_state[key_name] = "None"

            st.session_state[key_name] = st.radio(
                f"Select winner for Court {i+1}",
                ["None", "Team 1", "Team 2"],
                index=["None", "Team 1", "Team 2"].index(st.session_state[key_name]),
                key=f"radio_{i}"
            )

            if st.button(f"Submit result for Court {i+1}", key=f"submit_{i}"):
                if st.session_state[key_name] != "None":
                    process_court_result(i, st.session_state[key_name])
                    st.session_state[key_name] = "None"

# Submit all winners at once
if st.button("Submit All Court Winners"):
    any_selected = False
    for i in range(config["num_courts"]):
        winner = st.session_state.get(f"winner_{i}", "None")
        if winner in ["Team 1", "Team 2"]:
            process_court_result(i, winner, rerun=False)
            st.session_state[f"winner_{i}"] = "None"
            any_selected = True
    if any_selected:
        save_json(DATA_FILE, data)
        st.success("All court winners processed!")
        rerun_app()

# Display match history
st.subheader("📜 Match History")
if data["history"]:
    for match in reversed(data["history"][-10:]):
        st.write(
            f"**Court {match['court']}** — Winners: {', '.join(match['winners'])} | "
            f"Losers: {', '.join(match['losers'])}"
        )
else:
    st.write("No matches played yet.")
