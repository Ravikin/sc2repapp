import sc2reader
from sc2reader.events import UnitBornEvent, UnitInitEvent, UnitDiedEvent, UpgradeCompleteEvent, PlayerStatsEvent
from sc2reader.events.game import CommandEvent
from sc2reader.events.tracker import UnitPositionsEvent
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

COSMETIC_PREFIXES = ('Reward', 'Spray', 'GameHeart', 'Skin')


def _is_cosmetic_upgrade(name):
    return any(name.startswith(p) for p in COSMETIC_PREFIXES)


def _unit_type(unit):
    if unit.is_building:
        return 'building'
    if unit.is_worker:
        return 'worker'
    return 'army'


def parse_replay_bytes(replay_bytes):
    """Parse SC2 replay from bytes, return text log and structured data."""
    replay_io = BytesIO(replay_bytes)
    replay = sc2reader.load_replay(replay_io, load_level=4)

    events_log = []
    duration = replay.length
    duration_seconds = int(duration.total_seconds())
    duration_str = f"{duration_seconds // 60} minutes and {duration_seconds % 60} seconds"

    # === SUMMARY ===
    summary = {
        'map': replay.map_name,
        'date': str(replay.date) if replay.date else None,
        'duration_seconds': duration_seconds,
        'duration_str': duration_str,
        'players': [],
    }

    chart_data = {
        'players': [],
        'economy': {},
        'supply': {},
        'army_value': {},
        'resources_lost_killed': {},
        'resource_bank': {},
        'apm': {},
    }

    # Player info
    players = {player.pid: player.name for player in replay.players}
    player_colors = {}

    for player in replay.players:
        color = [player.color.r, player.color.g, player.color.b]
        player_colors[player.pid] = color

        result = 'Unknown'
        if player.team:
            result = 'Win' if player.team.result == 'Win' else 'Loss'

        summary['players'].append({
            'name': player.name,
            'race': player.play_race,
            'pick_race': getattr(player, 'pick_race', player.play_race),
            'result': result,
            'color': color,
            'clan_tag': getattr(player, 'clan_tag', ''),
            'highest_league': getattr(player, 'highest_league', 0),
        })

        chart_data['players'].append({
            'name': player.name,
            'race': player.play_race,
            'pid': player.pid,
            'color': color,
        })
        for key in ('economy', 'supply', 'army_value', 'resources_lost_killed', 'resource_bank'):
            chart_data[key][player.name] = []
        chart_data['apm'][player.name] = []

    # Introductory log
    events_log.append(f"Map: {replay.map_name}")
    events_log.append("Players:")
    for player in replay.players:
        events_log.append(f"- {player.name} ({player.play_race})")
    events_log.append(f"Duration: {duration_str}")
    if replay.date:
        events_log.append(f"Date: {replay.date}")
    events_log.append("=" * 40)

    # === DATA COLLECTION ===
    unit_deaths = []
    player_populations = defaultdict(lambda: (0, 0))

    # Minimap: track unit lifecycle
    unit_tracker = {}  # unit_id -> {name, pid, x, y, type, born_second, died_second}
    all_coords = []    # for computing bounds

    # Build order
    build_orders = {name: [] for name in players.values()}

    # APM
    apm_counts = {name: defaultdict(int) for name in players.values()}

    for event in replay.events:
        time = f"{event.second // 60:02d}:{event.second % 60:02d}"

        # --- APM tracking ---
        if isinstance(event, CommandEvent) and event.player and event.player.pid in players:
            player_name = players[event.player.pid]
            minute = event.second // 60
            apm_counts[player_name][minute] += 1

        # --- PlayerStatsEvent ---
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

        # --- Building constructed ---
        if isinstance(event, (UnitBornEvent, UnitInitEvent)) and event.unit.is_building:
            player_name = players.get(event.control_pid, 'Unknown')
            building_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Building Constructed] {building_name}{pop_info}")

            # Minimap tracking
            if event.x is not None and event.y is not None:
                unit_tracker[event.unit.id] = {
                    'pid': event.control_pid,
                    'x': int(event.x), 'y': int(event.y),
                    'type': 'building',
                    'born_second': event.second, 'died_second': None,
                }
                all_coords.append((event.x, event.y))

            # Build order
            if player_name in build_orders:
                used, _ = player_populations.get(event.control_pid, (0, 0))
                build_orders[player_name].append({
                    'second': event.second,
                    'name': building_name,
                    'type': 'building',
                    'supply': used,
                })

        # --- Unit produced ---
        elif isinstance(event, UnitBornEvent) and event.unit.is_army:
            player_name = players.get(event.control_pid, 'Unknown')
            unit_name = event.unit.name
            events_log.append(f"[{time}] [{player_name}] [Unit Produced] {unit_name}{pop_info}")

            # Minimap tracking
            if event.x is not None and event.y is not None:
                unit_tracker[event.unit.id] = {
                    'pid': event.control_pid,
                    'x': int(event.x), 'y': int(event.y),
                    'type': 'army',
                    'born_second': event.second, 'died_second': None,
                }
                all_coords.append((event.x, event.y))

            # Build order
            if player_name in build_orders:
                used, _ = player_populations.get(event.control_pid, (0, 0))
                build_orders[player_name].append({
                    'second': event.second,
                    'name': unit_name,
                    'type': 'unit',
                    'supply': used,
                })

        # --- Worker born (minimap only) ---
        elif isinstance(event, UnitBornEvent) and event.unit.is_worker:
            if event.x is not None and event.y is not None:
                unit_tracker[event.unit.id] = {
                    'pid': event.control_pid,
                    'x': int(event.x), 'y': int(event.y),
                    'type': 'worker',
                    'born_second': event.second, 'died_second': None,
                }
                all_coords.append((event.x, event.y))

        # --- Unit lost ---
        elif isinstance(event, UnitDiedEvent) and event.unit.is_army:
            owner_name = players.get(event.unit.owner.pid, 'Unknown') if event.unit.owner else 'Neutral'
            unit_name = event.unit.name
            unit_deaths.append((event.second, owner_name, unit_name))
            events_log.append(f"[{time}] [{owner_name}] [Unit Lost] {unit_name}{pop_info}")

        # --- Any unit died (minimap) ---
        if isinstance(event, UnitDiedEvent):
            uid = event.unit.id
            if uid in unit_tracker:
                unit_tracker[uid]['died_second'] = event.second
                if event.x is not None and event.y is not None:
                    unit_tracker[uid]['x'] = int(event.x)
                    unit_tracker[uid]['y'] = int(event.y)

        # --- UnitPositionsEvent (update positions for minimap) ---
        if isinstance(event, UnitPositionsEvent):
            for unit_index, (ux, uy) in event.positions:
                if unit_index in unit_tracker:
                    unit_tracker[unit_index]['x'] = int(ux)
                    unit_tracker[unit_index]['y'] = int(uy)

        # --- Upgrade completed ---
        if isinstance(event, UpgradeCompleteEvent):
            player_name = players.get(event.pid, 'Unknown')
            upgrade_name = event.upgrade_type_name
            events_log.append(f"[{time}] [{player_name}] [Upgrade Completed] {upgrade_name}{pop_info}")

            # Build order (non-cosmetic only)
            if player_name in build_orders and not _is_cosmetic_upgrade(upgrade_name):
                used, _ = player_populations.get(event.pid, (0, 0))
                build_orders[player_name].append({
                    'second': event.second,
                    'name': upgrade_name,
                    'type': 'upgrade',
                    'supply': used,
                })

        # --- Economy stats (every 60s) ---
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
                # Army value from engine
                chart_data['army_value'][player_name].append({
                    'minute': minute,
                    'value': event.minerals_used_active_forces + event.vespene_used_active_forces,
                })
                # Resources lost vs killed
                chart_data['resources_lost_killed'][player_name].append({
                    'minute': minute,
                    'lost': event.minerals_lost_army + event.vespene_lost_army,
                    'killed': event.minerals_killed_army + event.vespene_killed_army,
                })
                # Resource bank
                chart_data['resource_bank'][player_name].append({
                    'minute': minute,
                    'minerals': event.minerals_current,
                    'vespene': event.vespene_current,
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

    # === MINIMAP SNAPSHOTS ===
    minimap_data = None
    if all_coords:
        xs = [c[0] for c in all_coords]
        ys = [c[1] for c in all_coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad_x = (max_x - min_x) * 0.05 or 5
        pad_y = (max_y - min_y) * 0.05 or 5

        snapshot_interval = 10 if duration_seconds <= 900 else 15
        snapshots = []
        for t in range(0, duration_seconds + 1, snapshot_interval):
            units = []
            for uid, u in unit_tracker.items():
                if u['born_second'] <= t and (u['died_second'] is None or u['died_second'] > t):
                    if u['pid'] in players:
                        units.append({
                            'x': u['x'], 'y': u['y'],
                            'pid': u['pid'], 'type': u['type'],
                        })
            snapshots.append({'second': t, 'units': units})

        minimap_players = {}
        for pid, name in players.items():
            minimap_players[str(pid)] = {
                'name': name,
                'color': player_colors.get(pid, [255, 255, 255]),
            }

        minimap_data = {
            'bounds': {
                'min_x': min_x - pad_x, 'max_x': max_x + pad_x,
                'min_y': min_y - pad_y, 'max_y': max_y + pad_y,
            },
            'duration_seconds': duration_seconds,
            'snapshots': snapshots,
            'players': minimap_players,
        }

    # === APM DATA ===
    for pname, minute_counts in apm_counts.items():
        chart_data['apm'][pname] = [
            {'minute': m, 'actions': count}
            for m, count in sorted(minute_counts.items())
        ]

    return json.dumps({
        'log': '\n'.join(events_log),
        'summary': summary,
        'charts': chart_data,
        'build_order': build_orders,
        'minimap': minimap_data,
    })
