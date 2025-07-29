import streamlit as st
import sc2reader
import pandas as pd
from sc2reader.events import UnitBornEvent, UnitInitEvent, UnitDiedEvent, UpgradeCompleteEvent, PlayerStatsEvent
from collections import defaultdict

UNIT_COSTS = {
    'Marine': (50, 0),
    'Zealot': (100, 0),
    'Zergling': (25, 0),
    'Stalker': (125, 50),
    'Marauder': (100, 25),
    # Extend with more units
}

def parse_replay_to_txt(replay):
    events_log = []
    pop_data = []
    income_data = []

    events_log.append(f"Map: {replay.map_name}")
    events_log.append("Players:")
    for player in replay.players:
        events_log.append(f"- {player.name} ({player.play_race})")
    duration = replay.length
    duration_str = f"{int(duration.total_seconds()//60)} minutes and {int(duration.total_seconds()%60)} seconds"
    events_log.append(f"Duration: {duration_str}")
    if replay.date:
        events_log.append(f"Date: {replay.date}")
    events_log.append("="*40)

    players = {player.pid: player.name for player in replay.players}
    unit_deaths = []
    player_populations = defaultdict(lambda: (0, 0))

    for event in replay.events:
        time = f"{event.second // 60:02d}:{event.second % 60:02d}"

        if isinstance(event, PlayerStatsEvent):
            player_populations[event.pid] = (event.food_used, event.food_made)
            name = players.get(event.pid, f"Player {event.pid}")
            pop_data.append({"minute": event.second / 60, "player_metric": f"{name} Used", "value": event.food_used})
            pop_data.append({"minute": event.second / 60, "player_metric": f"{name} Limit", "value": event.food_made})
            income_data.append({"minute": event.second / 60, "player_resource": f"{name} Minerals", "value": event.minerals_collection_rate})
            income_data.append({"minute": event.second / 60, "player_resource": f"{name} Gas", "value": event.vespene_collection_rate})

        pop_info = ""
        if hasattr(event, 'control_pid') and event.control_pid in player_populations:
            used, made = player_populations[event.control_pid]
            pop_info = f" [{used}/{made}]"
        elif hasattr(event, 'pid') and event.pid in player_populations:
            used, made = player_populations[event.pid]
            pop_info = f" [{used}/{made}]"
        elif isinstance(event, UnitDiedEvent) and event.unit.owner and event.unit.owner.pid in player_populations:
            used, made = player_populations[event.unit.owner.pid]
            pop_info = f" [{used}/{made}]"

        if isinstance(event, (UnitBornEvent, UnitInitEvent)) and event.unit.is_building:
            player_name = players.get(event.control_pid, 'Unknown')
            building_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Building Constructed] {building_name}{pop_info}")

        elif isinstance(event, UnitBornEvent) and event.unit.is_army:
            player_name = players.get(event.control_pid, 'Unknown')
            unit_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Unit Produced] {unit_name}{pop_info}")

        elif isinstance(event, UnitDiedEvent) and event.unit.is_army:
            owner_name = players.get(event.unit.owner.pid, 'Unknown') if event.unit.owner else 'Neutral'
            unit_name = event.unit.name
            unit_deaths.append((event.second, owner_name, unit_name))
            events_log.append(f"[{time}] [{owner_name}] [Unit Lost] {unit_name}{pop_info}")

        elif isinstance(event, UpgradeCompleteEvent):
            player_name = players.get(event.pid, 'Unknown')
            upgrade_name = event.upgrade_type_name
            events_log.append(f"[{time}] [{player_name}] [Upgrade Completed] {upgrade_name}{pop_info}")

        if isinstance(event, PlayerStatsEvent) and event.second % 60 == 0:
            player_name = players.get(event.pid, 'Unknown')
            workers = event.workers_active_count
            minerals_income = event.minerals_collection_rate
            gas_income = event.vespene_collection_rate
            events_log.append(f"[{time}] [{player_name}] [Economy] Workers: {workers}, Minerals Income: {minerals_income}/min, Gas Income: {gas_income}/min{pop_info}")

            recent_deaths = [death for death in unit_deaths if event.second - 60 <= death[0] <= event.second]
            if len(recent_deaths) >= 15:
                loss_summary = defaultdict(lambda: {'units': 0, 'minerals': 0, 'gas': 0})
                for _, pname, uname in recent_deaths:
                    minerals, gas = UNIT_COSTS.get(uname, (0, 0))
                    loss_summary[pname]['units'] += 1
                    loss_summary[pname]['minerals'] += minerals
                    loss_summary[pname]['gas'] += gas

                favored = min(loss_summary.items(), key=lambda x: (x[1]['minerals'] + x[1]['gas']))[0]
                summary_str = ', '.join([f"{p}: {v['units']} units ({v['minerals']}M/{v['gas']}G)" for p, v in loss_summary.items()])
                events_log.append(f"[{time}] [Meta] Big fight happened. Losses - {summary_str}. Favored: {favored}")
                unit_deaths.clear()

    winner = next((team for team in replay.teams if team.result == 'Win'), None)
    if winner:
        winner_names = ', '.join(player.name for player in winner.players)
        events_log.append(f"[Game End] Winner: {winner_names}. Game length: {duration_str}.")

    return '\n'.join(events_log), pd.DataFrame(pop_data), pd.DataFrame(income_data)

st.title("Starcraft 2 Replay Parser")
replay_file = st.file_uploader("Upload a replay file", type="SC2Replay")

if replay_file:
    replay = sc2reader.load_replay(replay_file, load_level=4)
    log_output, pop_df, income_df = parse_replay_to_txt(replay)

    st.text_area("Parsed Replay Log:", log_output, height=400)
    st.download_button("Download Log", log_output, "replay_events.txt")

    st.subheader("Population Over Time")
    pop_chart = pop_df.pivot(index="minute", columns="player_metric", values="value")
    st.line_chart(pop_chart)

    st.subheader("Income Over Time")
    income_chart = income_df.pivot(index="minute", columns="player_resource", values="value")
    st.line_chart(income_chart)
