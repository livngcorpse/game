import asyncpg
import json
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from src.utils.config import DATABASE_URL
from src.database.models import User, Game, Player, Ban, GameMode, GamePhase, Role

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.max_retries = 5
        self.retry_delay = 2  # seconds

    async def connect(self):
        try:
            self.pool = await asyncpg.create_pool(DATABASE_URL)
            await self._create_tables()
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def _reconnect_if_needed(self):
        """Attempt to reconnect to database if connection is lost"""
        if not self.pool:
            return await self.connect()
            
        try:
            # Test connection with a simple query
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except (asyncpg.exceptions.ConnectionDoesNotExistError, 
                asyncpg.exceptions.InterfaceError,
                asyncpg.exceptions.InternalClientError):
            print("Database connection lost. Attempting to reconnect...")
            await self.disconnect()
            await self.connect()

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a database operation with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                await self._reconnect_if_needed()
                return await func(*args, **kwargs)
            except (asyncpg.exceptions.ConnectionDoesNotExistError, 
                    asyncpg.exceptions.InterfaceError,
                    asyncpg.exceptions.InternalClientError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    print(f"Database connection error (attempt {attempt + 1}/{self.max_retries}): {e}")
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    print(f"Max retries reached. Database operation failed: {e}")
                    raise
            except Exception as e:
                # For other exceptions, don't retry
                raise
        
        raise last_exception

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
                    sheriff_used_shot BOOLEAN DEFAULT FALSE,
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
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    game_id TEXT NOT NULL,
                    voter_id BIGINT NOT NULL,
                    target_id BIGINT,
                    round_number INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (game_id, voter_id, round_number)
                )
            """)

    async def get_user(self, user_id: int) -> Optional[User]:
        async def _get_user():
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
        
        try:
            return await self._execute_with_retry(_get_user)
        except Exception as e:
            print(f"Error getting user {user_id}: {e}")
            return None

    async def create_user(self, user_id: int) -> User:
        async def _create_user():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                    user_id
                )
                return await self.get_user(user_id)
        
        return await self._execute_with_retry(_create_user)

    async def update_user_xp(self, user_id: int, xp_change: int):
        async def _update_user_xp():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET xp = xp + $1 WHERE id = $2",
                    xp_change, user_id
                )
        
        await self._execute_with_retry(_update_user_xp)

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
        async def _get_game_by_group():
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
        
        try:
            return await self._execute_with_retry(_get_game_by_group)
        except Exception as e:
            print(f"Error getting game by group {group_id}: {e}")
            return None

    async def get_game_by_id(self, game_id: str) -> Optional[Game]:
        """Get game by its ID instead of group ID"""
        async def _get_game_by_id():
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM games WHERE id = $1",
                    game_id
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
        
        try:
            return await self._execute_with_retry(_get_game_by_id)
        except Exception as e:
            print(f"Error getting game by ID {game_id}: {e}")
            return None

    async def update_game_phase(self, game_id: str, phase: GamePhase):
        async def _update_game_phase():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE games SET phase = $1 WHERE id = $2",
                    phase.value, game_id
                )
        
        await self._execute_with_retry(_update_game_phase)

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
        async def _add_player():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO players (game_id, user_id, role, sheriff_used_shot, detective_last_investigation, engineer_used_ability) VALUES ($1, $2, $3, $4, $5, $6)",
                    player.game_id, player.user_id, player.role.value, player.sheriff_used_shot, player.detective_last_investigation, player.engineer_used_ability
                )
        
        await self._execute_with_retry(_add_player)

    async def get_player(self, game_id: str, user_id: int) -> Optional[Player]:
        async def _get_player():
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
                        sheriff_used_shot=row['sheriff_used_shot'],
                        detective_last_investigation=row['detective_last_investigation'],
                        engineer_used_ability=row['engineer_used_ability']
                    )
                return None
        
        try:
            return await self._execute_with_retry(_get_player)
        except Exception as e:
            print(f"Error getting player {user_id} in game {game_id}: {e}")
            return None

    async def get_players(self, game_id: str) -> List[Player]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM players WHERE game_id = $1",
                game_id
            )
            return [
                Player(
                    game_id=row['game_id'],
                    user_id=row['user_id'],
                    role=Role(row['role']),
                    is_alive=row['is_alive'],
                    voted=row['voted'],
                    completed_task=row['completed_task'],
                    sheriff_used_shot=row['sheriff_used_shot'],
                    detective_last_investigation=row['detective_last_investigation'],
                    engineer_used_ability=row['engineer_used_ability']
                )
                for row in rows
            ]

    async def get_alive_players(self, game_id: str) -> List[Player]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM players WHERE game_id = $1 AND is_alive = TRUE",
                game_id
            )
            return [
                Player(
                    game_id=row['game_id'],
                    user_id=row['user_id'],
                    role=Role(row['role']),
                    is_alive=row['is_alive'],
                    voted=row['voted'],
                    completed_task=row['completed_task'],
                    sheriff_used_shot=row['sheriff_used_shot'],
                    detective_last_investigation=row['detective_last_investigation'],
                    engineer_used_ability=row['engineer_used_ability']
                )
                for row in rows
            ]

    async def get_players_by_role(self, game_id: str, role: Role) -> List[Player]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM players WHERE game_id = $1 AND role = $2",
                game_id, role.value
            )
            return [
                Player(
                    game_id=row['game_id'],
                    user_id=row['user_id'],
                    role=Role(row['role']),
                    is_alive=row['is_alive'],
                    voted=row['voted'],
                    completed_task=row['completed_task'],
                    sheriff_used_shot=row['sheriff_used_shot'],
                    detective_last_investigation=row['detective_last_investigation'],
                    engineer_used_ability=row['engineer_used_ability']
                )
                for row in rows
            ]

    async def update_player_field(self, game_id: str, user_id: int, field: str, value: Any):
        async def _update_player_field():
            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE players SET {field} = $1 WHERE game_id = $2 AND user_id = $3",
                    value, game_id, user_id
                )
        
        await self._execute_with_retry(_update_player_field)

    async def get_player_field(self, game_id: str, user_id: int, field: str) -> Any:
        """Get a specific field value for a player"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {field} FROM players WHERE game_id = $1 AND user_id = $2",
                game_id, user_id
            )
            return row[field] if row else None

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

    async def get_voters_for_target(self, game_id: str, target_id: int) -> List[int]:
        """Get list of users who voted for a specific target"""
        # This would need a votes table to track individual votes
        # For now, this is a placeholder that should be implemented
        # when you add proper vote tracking
        async with self.pool.acquire() as conn:
            # This assumes you'll add a votes table later
            # For now, return empty list
            return []

    async def get_game_round(self, game_id: str) -> int:
        """Get current round number for a game"""
        async with self.pool.acquire() as conn:
            # You might want to add a round_number field to games table
            # For now, calculate based on game duration or add to game settings
            row = await conn.fetchrow(
                "SELECT settings FROM games WHERE id = $1",
                game_id
            )
            if row and row['settings']:
                return row['settings'].get('round_number', 1)
            return 1

    async def update_game_settings(self, game_id: str, settings: Dict[str, Any]):
        """Update game settings JSON field"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE games SET settings = $1 WHERE id = $2",
                json.dumps(settings), game_id
            )

    async def create_votes_table(self):
        """Add this to your _create_tables method"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    game_id TEXT NOT NULL,
                    voter_id BIGINT NOT NULL,
                    target_id BIGINT,
                    round_number INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (game_id, voter_id, round_number)
                )
            """)

    async def record_vote(self, game_id: str, voter_id: int, target_id: Optional[int], round_number: int):
        """Record a player's vote"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO votes (game_id, voter_id, target_id, round_number) VALUES ($1, $2, $3, $4) ON CONFLICT (game_id, voter_id, round_number) DO UPDATE SET target_id = $3",
                game_id, voter_id, target_id, round_number
            )

    async def get_vote_results(self, game_id: str, round_number: int) -> Dict[int, int]:
        """Get vote counts for current round"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT target_id, COUNT(*) as vote_count FROM votes WHERE game_id = $1 AND round_number = $2 GROUP BY target_id",
                game_id, round_number
            )
            return {row['target_id'] or -1: row['vote_count'] for row in rows}  # -1 for skip votes    # For now, return empty list
        return []

db = Database()