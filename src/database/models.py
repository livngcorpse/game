from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class GameMode(str, Enum):
    RANKED = "ranked"
    UNRANKED = "unranked"

class GamePhase(str, Enum):
    LOBBY = "lobby"
    NIGHT = "night"
    DISCUSSION = "discussion"
    VOTING = "voting"
    ENDED = "ended"

class Role(str, Enum):
    CREWMATE = "crewmate"
    IMPOSTOR = "impostor"
    DETECTIVE = "detective"
    SHERIFF = "sheriff"
    ENGINEER = "engineer"

class User(BaseModel):
    id: int
    xp: int = 0
    is_banned: bool = False
    ban_expiry: Optional[datetime] = None
    streak: int = 0
    achievements: Dict[str, bool] = {}

class Game(BaseModel):
    id: str
    mode: GameMode
    group_id: int
    phase: GamePhase
    start_time: datetime
    end_time: Optional[datetime] = None
    creator_id: int
    failed_task_rounds: int = 0
    settings: Dict[str, Any] = {}

class Player(BaseModel):
    game_id: str
    user_id: int
    role: Role
    is_alive: bool = True
    voted: bool = False
    completed_task: bool = False
    sheriff_used_shot: bool = False
    detective_last_investigation: int = 0
    engineer_used_ability: bool = False

class Ban(BaseModel):
    user_id: int
    start_time: datetime
    duration: Optional[str]
    reason: str