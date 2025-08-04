import asyncpg
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.utils.config import DATABASE_URL
from src.database.models import User, Game, Player, Ban, GameMode, GamePhase, Role

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)
        await self._create_tables()

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def _create_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    is_banned BOOLEAN DEFAULT FALSE,
                    ban_expiry TIMESTAMP,
                    streak INTEGER DEFAULT 0,
                    achievements JSONB DEFAULT '{}'
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    group_id BIGINT NOT NULL,
                    phase TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    creator_id BIGINT NOT NULL,
                    failed_task_rounds INTEGER DEFAULT 0,
                    settings JSONB DEFAULT '{}'
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    game_id TEXT NOT NULL,
                    user_id BIGINT NOT NULL,
                    role TEXT NOT NULL,
                    is_alive BOOLEAN DEFAULT TRUE,
                    voted BOOLEAN DEFAULT FALSE,
                    completed_task BOOLEAN DEFAULT FALSE,
                    sheriff_shots_used INTEGER DEFAULT 0,
                    detective_last_investigation INTEGER DEFAULT 0,
                    engineer_used_ability BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (game_id, user_id)
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bans (
                    user_id BIGINT PRIMARY KEY,
                    start_time TIMESTAMP NOT NULL,
                    duration TEXT,
                    reason TEXT NOT NULL
                )
            """)

    async def get_user(self, user_id: int) -> Optional[User]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            if row:
                return User(
                    id=row['id'],
                    xp=row['xp'],
                    is_banned=row['is_banned'],
                    ban_expiry=row['ban_expiry'],
                    streak=row['streak'],
                    achievements=row['achievements'] or {}
                )
            return None

    async def create_user(self, user_id: int) -> User:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            return await self.get_user(user_id)

    async def update_user_xp(self, user_id: int, xp_change: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET xp = xp + $1 WHERE id = $2",
                xp_change, user_id
            )

    async def update_user_streak(self, user_id: int, streak: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET streak = $1 WHERE id = $2",
                streak, user_id
            )

    async def set_user_xp(self, user_id: int, xp: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET xp = $1 WHERE id = $2",
                xp, user_id
            )

    async def ban_user(self, user_id: int, duration: Optional[str], reason: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO bans (user_id, start_time, duration, reason) VALUES ($1, $2, $3, $4) ON CONFLICT (user_id) DO UPDATE SET start_time = $2, duration = $3, reason = $4",
                user_id, datetime.now(), duration, reason
            )
            await conn.execute(
                "UPDATE users SET is_banned = TRUE WHERE id = $1",
                user_id
            )

    async def unban_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM bans WHERE user_id = $1", user_id)
            await conn.execute(
                "UPDATE users SET is_banned = FALSE, ban_expiry = NULL WHERE id = $1",
                user_id
            )

    async def create_game(self, game: Game) -> Game:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO games (id, mode, group_id, phase, start_time, creator_id, failed_task_rounds, settings) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                game.id, game.mode.value, game.group_id, game.phase.value, game.start_time, game.creator_id, game.failed_task_rounds, json.dumps(game.settings)
            )
            return game

    async def get_game_by_group(self, group_id: int) -> Optional[Game]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM games WHERE group_id = $1 AND phase != 'ended' ORDER BY start_time DESC LIMIT 1",
                group_id
            )
            if row:
                return Game(
                    id=row['id'],
                    mode=GameMode(row['mode']),
                    group_id=row['group_id'],
                    phase=GamePhase(row['phase']),
                    start_time=row['start_time'],
                    end_time=row['end_time'],
                    creator_id=row['creator_id'],
                    failed_task_rounds=row['failed_task_rounds'],
                    settings=row['settings'] or {}
                )
            return None

    async def update_game_phase(self, game_id: str, phase: GamePhase):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE games SET phase = $1 WHERE id = $2",
                phase.value, game_id
            )

    async def end_game(self, game_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE games SET phase = 'ended', end_time = $1 WHERE id = $2",
                datetime.now(), game_id
            )

    async def increment_failed_rounds(self, game_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE games SET failed_task_rounds = failed_task_rounds + 1 WHERE id = $1",
                game_id
            )

    async def add_player(self, player: Player):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO players (game_id, user_id, role) VALUES ($1, $2, $3)",
                player.game_id, player.user_id, player.role.value
            )

    async def get_players(self, game_id: str) -> List[Player]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM players WHERE game_id = $1", game_id)
            return [Player(
                game_id=row['game_id'],
                user_id=row['user_id'],
                role=Role(row['role']),
                is_alive=row['is_alive'],
                voted=row['voted'],
                completed_task=row['completed_task'],
                sheriff_shots_used=row['sheriff_shots_used'],
                detective_last_investigation=row['detective_last_investigation'],
                engineer_used_ability=row['engineer_used_ability']
            ) for row in rows]

    async def get_player(self, game_id: str, user_id: int) -> Optional[Player]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM players WHERE game_id = $1 AND user_id = $2",
                game_id, user_id
            )
            if row:
                return Player(
                    game_id=row['game_id'],
                    user_id=row['user_id'],
                    role=Role(row['role']),
                    is_alive=row['is_alive'],
                    voted=row['voted'],
                    completed_task=row['completed_task'],
                    sheriff_shots_used=row['sheriff_shots_used'],
                    detective_last_investigation=row['detective_last_investigation'],
                    engineer_used_ability=row['engineer_used_ability']
                )
            return None

    async def update_player_field(self, game_id: str, user_id: int, field: str, value: Any):
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE players SET {field} = $1 WHERE game_id = $2 AND user_id = $3",
                value, game_id, user_id
            )

    async def kill_player(self, game_id: str, user_id: int):
        await self.update_player_field(game_id, user_id, "is_alive", False)

    async def mark_voted(self, game_id: str, user_id: int):
        await self.update_player_field(game_id, user_id, "voted", True)

    async def reset_votes(self, game_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE players SET voted = FALSE WHERE game_id = $1",
                game_id
            )

    async def reset_tasks(self, game_id: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE players SET completed_task = FALSE WHERE game_id = $1",
                game_id
            )

db = Database()