import sc2reader
from sc2reader.events import UnitBornEvent, UnitInitEvent, UnitDiedEvent, UpgradeCompleteEvent, PlayerStatsEvent
from collections import defaultdict
from io import BytesIO
import json

UNIT_COSTS = {
    'Marine': (50, 0),
    'Zealot': (100, 0),
    'Zergling': (25, 0),
    'Stalker': (125, 50),
    'Marauder': (100, 25),
    'Roach': (75, 25),
    'Hydralisk': (100, 50),
    'Mutalisk': (100, 100),
    'Baneling': (25, 25),
    'Colossus': (300, 200),
    'Immortal': (275, 100),
    'SiegeTank': (150, 125),
    'Medivac': (100, 100),
    'Viking': (150, 75),
    'Phoenix': (150, 100),
    'VoidRay': (250, 150),
    'Carrier': (350, 250),
    'Battlecruiser': (400, 300),
    'Tempest': (250, 175),
    'Archon': (100, 300),
    'HighTemplar': (50, 150),
    'DarkTemplar': (125, 125),
    'Infestor': (100, 150),
    'Ultralisk': (300, 200),
    'BroodLord': (150, 150),
    'Corruptor': (150, 100),
    'Liberator': (150, 150),
    'Ravager': (75, 75),
    'Adept': (100, 25),
    'Disruptor': (150, 150),
    'Cyclone': (150, 100),
    'Hellion': (100, 0),
    'Hellbat': (100, 0),
    'WidowMine': (75, 25),
    'Thor': (300, 200),
    'Ghost': (150, 125),
    'Reaper': (50, 50),
    'Oracle': (150, 150),
    'WarpPrism': (200, 0),
    'Observer': (25, 75),
    'Sentry': (50, 100),
    'Queen': (150, 0),
    'Overseer': (50, 50),
    'SwarmHost': (100, 75),
    'Viper': (100, 200),
    'Lurker': (150, 150),
}


def parse_replay_bytes(replay_bytes):
    """Parse SC2 replay from bytes, return text log and structured data for charts."""
    replay_io = BytesIO(replay_bytes)
    replay = sc2reader.load_replay(replay_io, load_level=4)

    events_log = []
    chart_data = {
        'players': [],
        'economy': {},
        'supply': {},
        'army_value': {},
    }

    # Introductory log
    events_log.append(f"Map: {replay.map_name}")
    events_log.append("Players:")
    for player in replay.players:
        events_log.append(f"- {player.name} ({player.play_race})")
        chart_data['players'].append({
            'name': player.name,
            'race': player.play_race,
            'pid': player.pid,
        })
        chart_data['economy'][player.name] = []
        chart_data['supply'][player.name] = []
        chart_data['army_value'][player.name] = []

    duration = replay.length
    duration_str = f"{int(duration.total_seconds()//60)} minutes and {int(duration.total_seconds()%60)} seconds"
    events_log.append(f"Duration: {duration_str}")
    if replay.date:
        events_log.append(f"Date: {replay.date}")
    events_log.append("=" * 40)

    # Identify players
    players = {player.pid: player.name for player in replay.players}

    unit_deaths = []
    player_populations = defaultdict(lambda: (0, 0))
    army_values = defaultdict(lambda: {'minerals': 0, 'gas': 0})

    for event in replay.events:
        time = f"{event.second // 60:02d}:{event.second % 60:02d}"

        if isinstance(event, PlayerStatsEvent):
            player_populations[event.pid] = (event.food_used, event.food_made)

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

        # Building constructed
        if isinstance(event, (UnitBornEvent, UnitInitEvent)) and event.unit.is_building:
            player_name = players.get(event.control_pid, 'Unknown')
            building_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Building Constructed] {building_name}{pop_info}")

        # Unit produced
        elif isinstance(event, UnitBornEvent) and event.unit.is_army:
            player_name = players.get(event.control_pid, 'Unknown')
            unit_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Unit Produced] {unit_name}{pop_info}")
            minerals, gas = UNIT_COSTS.get(unit_name, (0, 0))
            if player_name in army_values:
                army_values[player_name]['minerals'] += minerals
                army_values[player_name]['gas'] += gas

        # Unit lost
        elif isinstance(event, UnitDiedEvent) and event.unit.is_army:
            owner_name = players.get(event.unit.owner.pid, 'Unknown') if event.unit.owner else 'Neutral'
            unit_name = event.unit.name
            unit_deaths.append((event.second, owner_name, unit_name))
            events_log.append(f"[{time}] [{owner_name}] [Unit Lost] {unit_name}{pop_info}")
            minerals, gas = UNIT_COSTS.get(unit_name, (0, 0))
            if owner_name in army_values:
                army_values[owner_name]['minerals'] -= minerals
                army_values[owner_name]['gas'] -= gas

        # Upgrade completed
        elif isinstance(event, UpgradeCompleteEvent):
            player_name = players.get(event.pid, 'Unknown')
            upgrade_name = event.upgrade_type_name
            events_log.append(f"[{time}] [{player_name}] [Upgrade Completed] {upgrade_name}{pop_info}")

        # Worker count and income changes
        if isinstance(event, PlayerStatsEvent) and event.second % 60 == 0:
            player_name = players.get(event.pid, 'Unknown')
            workers = event.workers_active_count
            minerals_income = event.minerals_collection_rate
            gas_income = event.vespene_collection_rate
            events_log.append(
                f"[{time}] [{player_name}] [Economy] Workers: {workers}, "
                f"Minerals Income: {minerals_income}/min, Gas Income: {gas_income}/min{pop_info}"
            )

            minute = event.second // 60
            if player_name in chart_data['economy']:
                chart_data['economy'][player_name].append({
                    'minute': minute,
                    'workers': workers,
                    'minerals_income': minerals_income,
                    'gas_income': gas_income,
                })
                used, made = player_populations.get(event.pid, (0, 0))
                chart_data['supply'][player_name].append({
                    'minute': minute,
                    'used': used,
                    'made': made,
                })
                chart_data['army_value'][player_name].append({
                    'minute': minute,
                    'minerals': max(0, army_values[player_name]['minerals']),
                    'gas': max(0, army_values[player_name]['gas']),
                })

            # Big fights detection
            recent_deaths = [death for death in unit_deaths if event.second - 60 <= death[0] <= event.second]
            if len(recent_deaths) >= 15:
                loss_summary = defaultdict(lambda: {'units': 0, 'minerals': 0, 'gas': 0})
                for _, pname, uname in recent_deaths:
                    minerals, gas = UNIT_COSTS.get(uname, (0, 0))
                    loss_summary[pname]['units'] += 1
                    loss_summary[pname]['minerals'] += minerals
                    loss_summary[pname]['gas'] += gas

                favored = min(loss_summary.items(), key=lambda x: (x[1]['minerals'] + x[1]['gas']))[0]
                summary_str = ', '.join(
                    [f"{p}: {v['units']} units ({v['minerals']}M/{v['gas']}G)" for p, v in loss_summary.items()]
                )
                events_log.append(f"[{time}] [Meta] Big fight happened. Losses - {summary_str}. Favored: {favored}")
                unit_deaths.clear()

    # Determine winner
    winner = next((team for team in replay.teams if team.result == 'Win'), None)
    if winner:
        winner_names = ', '.join(player.name for player in winner.players)
        events_log.append(f"[Game End] Winner: {winner_names}. Game length: {duration_str}.")

    return json.dumps({
        'log': '\n'.join(events_log),
        'charts': chart_data,
    })
