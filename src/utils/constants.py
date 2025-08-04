COMMAND_PREFIXES = ["/", "!", "?", "."]

LOBBY_TIMEOUT = 60
NIGHT_PHASE_DURATION = 60
DISCUSSION_DURATION = 90
VOTING_DURATION = 30

MIN_PLAYERS = 4
MAX_PLAYERS = 20

ROLE_DISTRIBUTION = {
    (4, 8): {"impostors": 1, "detectives": 1, "sheriffs": 0, "engineers": 0},
    (9, 12): {"impostors": 2, "detectives": 1, "sheriffs": 0, "engineers": 0},
    (13, 16): {"impostors": 3, "detectives": 2, "sheriffs": 1, "engineers": 1},
    (17, 20): {"impostors": 4, "detectives": 2, "sheriffs": 1, "engineers": 1}
}

TASK_DISTRIBUTION = {
    (4, 8): 1,
    (9, 12): 2,
    (13, 16): 3,
    (17, 20): 4
}

XP_REWARDS = {
    "win": 25,
    "loss": 5,
    "task_completed": 3,
    "correct_vote": 2,
    "impostor_kill": 5,
    "sheriff_kills_impostor": 10,
    "detective_finds_impostor": 8,
    "engineer_saves_ship": 15
}

XP_PENALTIES = {
    "ship_explodes": 15,
    "friendly_fire": 10,
    "afk": 5
}

STREAK_BONUS = 3