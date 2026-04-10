@echo off
REM ============================================
REM Trading Bot - Setup Script for Windows
REM ============================================

echo ============================================
echo Trading Bot - Setup Script
echo ============================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

echo [OK] Docker is installed
echo.

REM Check if .env file exists
if exist .env (
    echo [WARNING] .env file already exists!
    echo Do you want to overwrite it? (Y/N)
    set /p overwrite=
    if /i not "%overwrite%"=="Y" (
        echo Setup cancelled.
        pause
        exit /b 0
    )
)

REM Create .env file from template
echo Creating .env file...
echo.

(
echo # ============================================
echo # Trading Bot Configuration
echo # ============================================
echo.
echo # Bybit API Configuration
echo # Get your API keys from: https://www.bybit.com/app/user/api-management
echo BYBIT_API_KEY=your_api_key_here
echo BYBIT_API_SECRET=your_api_secret_here
echo.
echo # Telegram Bot Configuration
echo # 1. Create bot: Talk to @BotFather on Telegram
echo # 2. Get your chat ID: Talk to @userinfobot on Telegram
echo TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
echo TELEGRAM_CHAT_IDS=your_chat_id_here,another_chat_id_here
echo.
echo # Database Configuration
echo POSTGRES_USER=trading_bot
echo POSTGRES_PASSWORD=secure_password_123
echo POSTGRES_DB=trading_db
echo DATABASE_URL=postgresql://trading_bot:secure_password_123@timescaledb:5432/trading_db
echo.
echo # Application Settings
echo ENVIRONMENT=production
echo LOG_LEVEL=INFO
echo.
echo # Paper Trading Settings
echo PAPER_TRADING=true
echo INITIAL_BALANCE=100
) > .env

echo [OK] .env file created successfully!
echo.
echo ============================================
echo IMPORTANT: Edit .env file with your credentials
echo ============================================
echo.
echo You need to fill in:
echo   1. BYBIT_API_KEY - Your Bybit API key
echo   2. BYBIT_API_SECRET - Your Bybit API secret
echo   3. TELEGRAM_BOT_TOKEN - Your Telegram bot token
echo   4. TELEGRAM_CHAT_IDS - Your Telegram chat ID(s)
echo.
echo After editing .env, run: start.bat
echo.

REM Create logs and reports directories
echo Creating directories...
if not exist logs mkdir logs
if not exist reports mkdir reports
if not exist reports\liquidations mkdir reports\liquidations
if not exist reports\liquidations\wyckoff mkdir reports\liquidations\wyckoff
if not exist reports\liquidations\scalp mkdir reports\liquidations\scalp
if not exist reports\liquidations\scalp_v2 mkdir reports\liquidations\scalp_v2
echo [OK] Directories created
echo.

REM Create start.bat script
echo Creating start.bat script...
(
echo @echo off
echo REM Start Trading Bot
echo echo Starting Trading Bot...
echo docker-compose down
echo docker-compose build
echo docker-compose up -d
echo echo.
echo echo ============================================
echo echo Trading Bot Started Successfully!
echo echo ============================================
echo echo.
echo echo Services:
echo echo   - Trading Bot: Running
echo echo   - Telegram Bot: Running
echo echo   - Dashboard: http://localhost:8501
echo echo   - Database: localhost:5432
echo echo.
echo echo Commands:
echo echo   - View logs: docker logs -f trading_bot_app
echo echo   - Stop bot: docker-compose down
echo echo   - Restart: docker-compose restart
echo echo.
echo pause
) > start.bat
echo [OK] start.bat created
echo.

REM Create stop.bat script
echo Creating stop.bat script...
(
echo @echo off
echo REM Stop Trading Bot
echo echo Stopping Trading Bot...
echo docker-compose down
echo echo.
echo echo Trading Bot stopped successfully!
echo pause
) > stop.bat
echo [OK] stop.bat created
echo.

REM Create logs.bat script
echo Creating logs.bat script...
(
echo @echo off
echo REM View Trading Bot Logs
echo echo Select which logs to view:
echo echo   1. Trading Bot
echo echo   2. Telegram Bot
echo echo   3. Dashboard
echo echo   4. All services
echo echo.
echo set /p choice="Enter choice (1-4): "
echo.
echo if "%%choice%%"=="1" docker logs -f trading_bot_app
echo if "%%choice%%"=="2" docker logs -f trading_bot_telegram
echo if "%%choice%%"=="3" docker logs -f trading_bot_dashboard
echo if "%%choice%%"=="4" docker-compose logs -f
) > logs.bat
echo [OK] logs.bat created
echo.

REM Create restart.bat script
echo Creating restart.bat script...
(
echo @echo off
echo REM Restart Trading Bot
echo echo Restarting Trading Bot...
echo docker-compose restart
echo echo.
echo echo Trading Bot restarted successfully!
echo pause
) > restart.bat
echo [OK] restart.bat created
echo.

REM Create status.bat script
echo Creating status.bat script...
(
echo @echo off
echo REM Check Trading Bot Status
echo echo ============================================
echo echo Trading Bot Status
echo echo ============================================
echo echo.
echo docker-compose ps
echo echo.
echo pause
) > status.bat
echo [OK] status.bat created
echo.

echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Edit .env file with your credentials
echo   2. Run start.bat to start the bot
echo   3. Open Telegram and send /start to your bot
echo.
echo Quick commands:
echo   - start.bat    : Start the bot
echo   - stop.bat     : Stop the bot
echo   - restart.bat  : Restart the bot
echo   - logs.bat     : View logs
echo   - status.bat   : Check status
echo.
pause
