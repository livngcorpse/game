from typing import List, Dict, Any
from src.database.models import GameMode, Role

class Messages:
    @staticmethod
    def get_lobby_message(players: List[int], mode: GameMode, creator_id: int) -> str:
        return f"🎭 {mode.value.title()} Game Lobby is forming...\n\nCreator: Player {creator_id}\n\nCurrent Players ({len(players)}/20):\n" + \
               "\n".join([f"• Player {player_id}" for player_id in players]) + \
               f"\n\nStill waiting for {max(0, 4 - len(players))} more brave souls to join the chaos..."

    @staticmethod
    def get_game_started_message() -> str:
        return "🎭 The sus begins! Roles have been assigned. Check your DM to discover your fate..."

    @staticmethod
    def get_night_phase_message() -> str:
        return "🌙 Night falls... Everyone close your eyes (or pretend to). Roles, perform your secret deeds!"

    @staticmethod
    def get_day_phase_message(alive_players: List[int], night_summary: Dict[str, Any]) -> str:
        msg = f"☀️ Day {night_summary['round_number']} - Time to point fingers and blame each other!\n\n"
        msg += f"Survivors ({len(alive_players)}):\n"
        msg += "\n".join([f"• Player {player_id}" for player_id in alive_players])
        
        if night_summary['deaths']:
            msg += "\n\n💀 Casualties of the night:\n"
            for death in night_summary['deaths']:
                msg += f"• Player {death['user_id']} ({death['role']}) - {death['cause']}\n"
        else:
            msg += "\n\n✅ Somehow, everyone survived the night. Suspicious..."
        
        task_status = "✅ Tasks completed" if night_summary['task_success'] else "❌ Tasks failed"
        msg += f"\n🔧 Task Status: {task_status}"
        
        return msg

    @staticmethod
    def get_voting_phase_message() -> str:
        return "🗳️ Voting phase has begun! Choose wisely... or just point at someone random. Your call."

    @staticmethod
    def get_voting_result_message(ejected_player: int, player_role: str) -> str:
        if ejected_player:
            return f"⚖️ Player {ejected_player} ({player_role}) has been ejected! Was it the right choice? 😏"
        else:
            return "⚖️ No one was ejected. Either you're all innocent or all terrible at voting."

    @staticmethod
    def get_game_end_message(win_condition: str, winners: List[int]) -> str:
        if win_condition == "crewmates":
            return f"🎉 Crewmates Win!\nThe good guys somehow managed to not kill each other.\nWinners: {', '.join(map(str, winners))}"
        elif win_condition == "impostors":
            return f"🔪 Impostors Win!\nChaos reigns supreme as usual.\nWinners: {', '.join(map(str, winners))}"
        else:
            return "💥 Ship exploded! Well, that's what happens when you don't do your tasks. Everyone loses!"

    @staticmethod
    def get_role_assignment_message(role_name: str, role_description: str) -> str:
        return f"🎭 Your Secret Identity: {role_name}\n\n{role_description}\n\nShhh... Don't tell anyone!"

    @staticmethod
    def get_user_stats_message(user_id: int, xp: int, streak: int) -> str:
        return f"📊 Player {user_id}'s Sus Profile\n\nXP: {xp} points of questionable behavior\nWin Streak: {streak} consecutive victories (if you're lucky)"

    @staticmethod
    def get_help_message() -> str:
        return "🆘 Among Us Bot Help\n\nFeeling lost in the sus? Use the buttons below to uncover the mysteries."

    @staticmethod
    def get_game_not_found_message() -> str:
        return "❌ No active game detected. Did someone cancel it, or did you just imagine it existed?"

    @staticmethod
    def get_already_in_game_message() -> str:
        return "⚠️ You're already in this game of cat and mouse. Patience, young sus detective."

    @staticmethod
    def get_game_full_message() -> str:
        return "⚠️ Game is full (20 players maximum). The chaos can't handle any more participants!"

    @staticmethod
    def get_banned_message(duration: str) -> str:
        return f"🚫 You've been exiled from ranked games until {duration}. Better luck in the unranked wasteland."

    @staticmethod
    def get_dm_redirect_message() -> str:
        return "📱 Whisper to me first, then click the magical button. Trust me, it works."

    @staticmethod
    def get_role_description(role: Role) -> str:
        """Get detailed role descriptions with a sarcastic twist"""
        descriptions = {
            Role.CREWMATE: "Complete tasks and vote out impostors. Try not to get distracted by shiny objects.",
            Role.IMPOSTOR: "Eliminate crewmates and avoid detection. Blend in or face the consequences.",
            Role.DETECTIVE: "Investigate players to find impostors. Your findings are classified (to you).",
            Role.SHERIFF: "Shoot one player. Hit an impostor = hero. Hit crewmate = oopsie. Choose wisely!",
            Role.ENGINEER: "Fix the ship when tasks fail. You only get one chance to be the hero."
        }
        return descriptions.get(role, "Unknown role. How did you even get this?")

    @staticmethod
    def get_detective_result_message(target_id: int, result: str) -> str:
        """Format detective investigation results"""
        return f"🕵️ Investigation Results:\nPlayer {target_id} is: **{result}**\n\nKeep this to yourself, detective!"

    @staticmethod
    def get_vote_breakdown_message(votes: Dict[int, int]) -> str:
        """Format voting breakdown"""
        if not votes:
            return "📊 No votes were cast. Democracy failed spectacularly."
        
        msg = "📊 Vote Breakdown (AKA finger pointing contest):\n"
        for target_id, vote_count in sorted(votes.items(), key=lambda x: x[1], reverse=True):
            if target_id == -1:  # Skip votes
                msg += f"• Skip: {vote_count} votes (playing it safe, huh?)\n"
            else:
                msg += f"• Player {target_id}: {vote_count} votes\n"
        
        return msg

    @staticmethod
    def get_impostor_chat_message(impostor_id: int, message: str) -> str:
        """Format impostor team chat messages"""
        return f"🔪 Impostor {impostor_id}: {message}"

    @staticmethod
    def get_detective_chat_message(detective_id: int, message: str) -> str:
        """Format detective team chat messages"""
        return f"🕵️ Detective {detective_id}: {message}"

    @staticmethod
    def get_task_completion_message(task_name: str, success: bool) -> str:
        """Format task completion messages"""
        if success:
            return f"✅ Task '{task_name}' completed! You actually did something useful for once."
        else:
            return f"❌ Task '{task_name}' failed! Typical. Can't even do simple tasks."

    @staticmethod
    def get_engineer_fix_message(fixed: bool) -> str:
        """Format engineer ship fix messages"""
        if fixed:
            return "⚙️ Ship systems fixed! Crisis averted... for now."
        else:
            return "⚙️ Engineer chose not to fix the ship. Enjoy the impending doom!"

    @staticmethod
    def get_sheriff_action_message(target_id: int, success: bool) -> str:
        """Format sheriff action messages"""
        if success:
            return f"🔫 You shot Player {target_id} - they were an impostor! Lucky shot or skill? 🤔"
        else:
            return f"💀 You shot Player {target_id} - friendly fire! Oops, there goes your credibility."