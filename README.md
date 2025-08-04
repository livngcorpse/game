# 🧠 Telegram Among Us Bot

A feature-complete Telegram bot implementation of Among Us game mechanics for group chats.

## 🚀 Features

- **Full Game Logic**: Lobby, Night, Day, and Voting phases
- **5 Unique Roles**: Crewmate, Impostor, Detective, Sheriff, Engineer
- **Ranked/Unranked Modes**: Group-based game modes
- **XP & Achievement System**: Player progression and milestones
- **Task System**: Interactive task completion mechanics
- **Admin Controls**: Ban system and game management
- **Phase Timers**: Automatic game progression
- **Database Persistence**: PostgreSQL with full state management

## 📦 Installation

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and configure
4. Set up PostgreSQL database
5. Run: `python src/main.py`

## ⚙️ Configuration

Edit `.env` file:
```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql://user:pass@localhost:5432/amongus
RANKED_GC_IDS=123456789,987654321
BOT_OWNER_ID=your_user_id
GAME_LOG_CHANNEL_ID=log_channel_id
BOT_LOG_CHANNEL_ID=bot_log_channel_id
```

## 🎮 Game Commands

| Command | Description |
|---------|-------------|
| `/startgame [mode]` | Create new game lobby |
| `/join` | Join active game |
| `/begin` | Force start game (creator only) |
| `/end` | End game (admin/creator) |
| `/help` | Show help menu |

## 🎭 Roles

- **🔧 Crewmate**: Complete tasks, vote out impostors
- **🔪 Impostor**: Eliminate crew, avoid detection  
- **🕵️ Detective**: Investigate players for impostor status
- **🔫 Sheriff**: Eliminate players (risky but powerful)
- **⚙️ Engineer**: Fix ship when tasks fail

## 🏗️ Architecture

```
src/
├── bot/           # Telegram bot handlers
├── game/          # Core game logic
├── roles/         # Role implementations  
├── database/      # Data models & connection
├── systems/       # XP, achievements, bans
├── ui/            # Messages & keyboards
└── utils/         # Configuration & constants
```

## 🔧 Customization

- **Tasks**: Edit `src/game/task_pool.py`
- **Achievements**: Modify `src/systems/achievements.py`
- **XP Values**: Adjust `src/utils/constants.py`
- **Role Balance**: Update role distributions in constants

## 📊 Database Schema

- `users`: Player data, XP, bans, achievements
- `games`: Game instances and state
- `players`: Game participants and roles
- `bans`: Ban records and duration

## 🎯 Game Flow

1. **Lobby Phase** (60s): Players join, 4+ needed
2. **Night Phase** (60s): Roles perform actions via DM
3. **Day Phase** (120s): Discussion + voting
4. **Win/Continue**: Check conditions, repeat or end

## 🚫 Admin Commands

- `/xban <user> <duration>`: Ban from ranked games
- `/xunban <user>`: Remove ban
- `/setxp <user> <amount>`: Adjust player XP

## 📝 Logging

Structured logging with sarcastic Among Us themed messages:
- Game events (start/end/phase transitions)  
- Player actions (kills, votes, investigations)
- Admin actions (bans, XP changes)
- Error tracking

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes (maintain code style)
4. Test thoroughly
5. Submit pull request

## 📄 License

This project is open source. Check the repository for license details.

---

*Ready to find the impostors? Let the sus begin! 🎭*