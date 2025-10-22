import streamlit as st
import json
from pathlib import Path
import pandas as pd

# ---------------------------
# Constants
# ---------------------------
DATA_FILE = Path("pickleball_data.json")
MAX_COURTS = 3
MAX_PLAYERS = 20
MAX_STREAK = 2  # winners stay for up to 2 consecutive games

# ---------------------------
# Helper Functions
# ---------------------------

def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    else:
        # initialize empty structure
        return {
            "players": [],
            "queue": [],
            "courts": [[] for _ in range(MAX_COURTS)],
            "streaks": {},
            "history": [],
            "auto_fill": False
        }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def reset_everything():
    st.session_state.data = load_data()
    st.session_state.data["players"] = []
    st.session_state.data["queue"] = []
    st.session_state.data["courts"] = [[] for _ in range(MAX_COURTS)]
    st.session_state.data["streaks"] = {}
    st.session_state.data["history"] = []
    save_data(st.session_state.data)
    st.success("All data reset!")

def assign_empty_courts():
    data = st.session_state.data
    for i in range(MAX_COURTS):
        if len(data["courts"][i]) < 4:
            needed = 4 - len(data["courts"][i])
            for _ in range(needed):
                if data["queue"]:
                    data["courts"][i].append(data["queue"].pop(0))
    save_data(data)

def process_court_winner(court_index, winning_team):
    data = st.session_state.data
    court_players = data["courts"][court_index]
    if len(court_players) != 4:
        return  # can't process incomplete court

    team1 = court_players[:2]
    team2 = court_players[2:]
    winners = team1 if winning_team == "Team 1" else team2
    losers = team2 if winning_team == "Team 1" else team1

    # Determine staying winners and leaving winners
    staying_winners = [p for p in winners if data["streaks"].get(p,0) < MAX_STREAK]
    leaving_winners = [p for p in winners if data["streaks"].get(p,0) >= MAX_STREAK]

    # Increment streaks for staying winners
    for p in staying_winners:
        data["streaks"][p] = data["streaks"].get(p,0) + 1

    # Reset streaks for leaving winners and losers, move them to queue
    for p in leaving_winners + losers:
        data["streaks"][p] = 0
        if p not in data["queue"]:
            data["queue"].append(p)

    # Fill court up to 4 players from queue
    needed = 4 - len(staying_winners)
    new_players = []
    for _ in range(needed):
        if data["queue"]:
            new_players.append(data["queue"].pop(0))

    # Rebuild court
    data["courts"][court_index] = staying_winners + new_players

    # Record in history
    data["history"].append({
        "court": court_index + 1,
        "team_won": winning_team,
        "players": court_players.copy()
    })

def update_all_courts():
    data = st.session_state.data
    for i in range(MAX_COURTS):
        winner_key = f"court_winner_{i}"
        winner = st.session_state.get(winner_key, "")
        if winner in ["Team 1", "Team 2"]:
            process_court_winner(i, winner)
            st.session_state[winner_key] = ""  # reset selection after processing
    assign_empty_courts()
    save_data(data)
    st.success("All courts updated!")

def reset_court(court_index):
    data = st.session_state.data
    for p in data["courts"][court_index]:
        data["streaks"][p] = 0
        if p not in data["queue"]:
            data["queue"].append(p)
    data["courts"][court_index] = []
    assign_empty_courts()
    save_data(data)

# ---------------------------
# Initialize session_state
# ---------------------------
if "data" not in st.session_state:
    st.session_state.data = load_data()
for i in range(MAX_COURTS):
    key = f"court_winner_{i}"
    if key not in st.session_state:
        st.session_state[key] = ""

# ---------------------------
# Sidebar Config
# ---------------------------
st.sidebar.header("⚙️ Configuration")
data = st.session_state.data

data["auto_fill"] = st.sidebar.checkbox("Auto-Fill Courts Continuously", value=data.get("auto_fill", False))
if st.sidebar.button("Reset Everything"):
    reset_everything()

with st.sidebar.expander("Add Players"):
    bulk_input = st.text_area("One player per line (max 20 players)")
    if st.button("Add Players", key="add_players"):
        new_players = [p.strip() for p in bulk_input.splitlines() if p.strip()]
        for p in new_players:
            if p not in data["players"] and len(data["players"]) < MAX_PLAYERS:
                data["players"].append(p)
                data["queue"].append(p)
                data["streaks"][p] = 0
        save_data(data)
        st.success(f"Added {len(new_players)} players.")

# ---------------------------
# Main App
# ---------------------------
st.title("🏓 Pickleball Open Play Scheduler")
tabs = st.tabs(["Courts", "Queue", "History"])

# ---------------------------
# Courts Tab
# ---------------------------
with tabs[0]:
    st.subheader("Active Courts")
    if st.button("Assign Empty Courts"):
        assign_empty_courts()
        st.success("Empty courts filled from queue.")

    for i, court_players in enumerate(data["courts"]):
        st.markdown(f"### Court {i+1}")
        if len(court_players) != 4:
            st.info("Court not full")
        else:
            col1, col2 = st.columns(2)
            col1.markdown(f"**Team 1:** {', '.join(court_players[:2])}")
            col2.markdown(f"**Team 2:** {', '.join(court_players[2:])}")

            # Winner selection
            winner_key = f"court_winner_{i}"
            st.session_state[winner_key] = st.selectbox(
                f"Select winner (Court {i+1})",
                ["", "Team 1", "Team 2"],
                index=["", "Team 1", "Team 2"].index(st.session_state[winner_key]),
                key=f"{winner_key}_selectbox"
            )

            if st.button(f"Reset Court {i+1}", key=f"reset_{i}"):
                reset_court(i)
                st.info(f"Court {i+1} reset.")

    if st.button("Update All Courts"):
        update_all_courts()

# ---------------------------
# Queue Tab
# ---------------------------
with tabs[1]:
    st.subheader("Queue")
    st.write(", ".join(data["queue"]))

# ---------------------------
# History Tab
# ---------------------------
with tabs[2]:
    st.subheader("Game History")
    if data["history"]:
        rows = []
        for h in data["history"]:
            rows.append({
                "Court": h["court"],
                "Winner": h["team_won"],
                "Player 1": h["players"][0],
                "Player 2": h["players"][1],
                "Player 3": h["players"][2],
                "Player 4": h["players"][3],
            })
        st.dataframe(pd.DataFrame(rows))
    else:
        st.info("No games played yet.")
