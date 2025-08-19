# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered Telegram TODO bot that helps users manage tasks through natural language interactions in Russian. The bot uses Google Gemini AI to understand user intents and can handle task creation, completion, rescheduling, and searching.

### Key Features
- Natural language processing for task management in Russian
- Scheduled reminders using APScheduler  
- PostgreSQL database with SQLAlchemy ORM
- Multi-timezone support with Pendulum
- Docker containerization for easy deployment
- Database migrations with Alembic

## Architecture

### Core Components
- **Bot Entry Point**: `src/bot.py` - Main application with aiogram dispatcher
- **Configuration**: `src/config.py` - Pydantic settings with environment variable loading
- **Database**: `src/database/` - SQLAlchemy models, CRUD operations, session management
- **LLM Integration**: `src/llm/` - Google Gemini client and prompt templates
- **Telegram Handlers**: `src/tgbot/handlers/` - Message routing and intent processing
- **Scheduler**: `src/scheduler/` - APScheduler for reminder notifications
- **Utilities**: `src/utils/` - Date parsing, formatting, task management helpers

### Database Models
- **User**: Stores Telegram user info with timezone settings (primary key: telegram_id)
- **Task**: Task records with due dates, descriptions, status, and recurrence rules

### Intent Handling
The bot processes natural language through multiple AI prompts:
- Intent detection (add_task, find_tasks, complete_task, etc.)
- Task parsing and date/time extraction
- Timezone detection and search query processing

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL database
docker-compose up -d postgres

# Run database migrations
alembic upgrade head
```

### Running the Bot
```bash
# Start the bot (requires .env file with tokens)
python src/bot.py
```

### Database Operations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check migration history
alembic history
```

### Environment Variables Required
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from @BotFather
- `GOOGLE_API_KEY`: Google Gemini API key
- `POSTGRES_*`: Database connection parameters
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR)

## Code Patterns

### Handler Structure
- Handlers are organized by functionality in `src/tgbot/handlers/`
- Intent-specific handlers in `src/tgbot/handlers/intent_handlers/`
- Database sessions are injected via middleware
- All handlers use async/await patterns

### LLM Integration
- Prompts are stored as templates in `src/llm/prompts.py`
- Gemini client handles AI requests with retry logic
- Intent detection prioritizes context (replies vs new messages)

### Database Access
- Use dependency injection for database sessions
- Models use SQLAlchemy 2.0+ style with Mapped annotations
- CRUD operations are centralized in `src/database/crud.py`

### Date/Time Handling
- All dates stored in UTC in database
- User timezones handled with Pendulum library
- Smart defaults for time parsing (morning=09:00, evening=18:00)

## Testing
Tests should be placed in a `tests/` directory (not yet implemented in this codebase). When adding tests, follow these patterns:
- Use pytest for test framework
- Mock external API calls (Telegram, Gemini)
- Test database operations with transaction rollback
- Test timezone handling thoroughly