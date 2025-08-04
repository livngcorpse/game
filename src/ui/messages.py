from typing import List, Dict, Any
from src.database.models import GameMode

class Messages:
    @staticmethod
    def get_lobby_message(players: List[int], mode: GameMode, creator_id: int) -> str:
        return f"🎮 {mode.value.title()} Game Lobby\nCreated by: {creator_id}\n\nPlayers ({len(players)}/20):\n" + \
               "\n".join([f"• Player {player_id}" for player_id in players]) + \
               f"\n\nWaiting for {max(0, 4 - len(players))} more players..."

    @staticmethod
    def get_game_started_message() -> str:
        return "🎭 Game started! Roles have been assigned. Check your DM for your role."

    @staticmethod
    def get_night_phase_message() -> str:
        return "🌙 Night phase has started! Go to DM to perform your actions."

    @staticmethod
    def get_day_phase_message(alive_players: List[int], night_summary: Dict[str, Any]) -> str:
        msg = f"☀️ Day {night_summary['round_number']} - Discussion Phase\n\n"
        msg += f"Alive Players ({len(alive_players)}):\n"
        msg += "\n".join([f"• Player {player_id}" for player_id in alive_players])
        
        if night_summary['deaths']:
            msg += "\n\n💀 Night Deaths:\n"
            for death in night_summary['deaths']:
                msg += f"• Player {death['user_id']} ({death['role']}) - {death['cause']}\n"
        else:
            msg += "\n\n✅ No deaths during the night."
        
        task_status = "✅ Completed" if night_summary['task_success'] else "❌ Failed"
        msg += f"\n🔧 Tasks: {task_status}"
        
        return msg

    @staticmethod
    def get_voting_phase_message() -> str:
        return "🗳️ Voting phase has begun! Go to DM to cast your vote."

    @staticmethod
    def get_voting_result_message(ejected_player: int, player_role: str) -> str:
        if ejected_player:
            return f"⚖️ Player {ejected_player} ({player_role}) has been ejected!"
        else:
            return "⚖️ No one was ejected (tie vote or no votes)."

    @staticmethod
    def get_game_end_message(win_condition: str, winners: List[int]) -> str:
        if win_condition == "crewmates":
            return f"🎉 Crewmates Win!\nWinners: {', '.join(map(str, winners))}"
        elif win_condition == "impostors":
            return f"🔪 Impostors Win!\nWinners: {', '.join(map(str, winners))}"
        else:
            return "💥 Ship exploded! Everyone loses!"

    @staticmethod
    def get_role_assignment_message(role_name: str, role_description: str) -> str:
        return f"🎭 Your Role: {role_name}\n\n{role_description}"

    @staticmethod
    def get_user_stats_message(user_id: int, xp: int, streak: int) -> str:
        return f"📊 Stats for Player {user_id}\n\nXP: {xp}\nStreak: {streak} wins"

    @staticmethod
    def get_help_message() -> str:
        return "🆘 Among Us Bot Help\n\nUse the buttons below to get specific information."

    @staticmethod
    def get_game_not_found_message() -> str:
        return "❌ No active game found in this group."

    @staticmethod
    def get_already_in_game_message() -> str:
        return "⚠️ You're already in the game!"

    @staticmethod
    def get_game_full_message() -> str:
        return "⚠️ Game is full (20 players maximum)!"

    @staticmethod
    def get_banned_message(duration: str) -> str:
        return f"🚫 You are banned from ranked games until {duration}."

    @staticmethod
    def get_dm_redirect_message() -> str:
        return "📱 Please start a conversation with me in DM first, then use the button below."