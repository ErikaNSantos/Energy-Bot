# ⚡ Residential Energy Monitoring Bot

A Telegram bot that tracks, calculates, and projects residential electricity consumption in real time. It replaces manual spreadsheets with an event-based Start/Stop system, persists data in SQLite, and applies appliance-specific engineering rules to estimate the monthly invoice.

## Architecture

The project separates pure calculation logic from the interface layer, so the energy math can be reused if the front end changes (e.g. a future mobile app).

```
energy-bot/
├── core/
│   └── energia.py        # pure energy math (no DB, no Telegram)
├── interface/
│   └── telegram_bot.py   # Telegram handlers + watchdog thread
├── data/
│   ├── config.json       # tariff, appliances, alert limits, base load
│   └── logs.db           # SQLite (created by setup)
├── database_setup.py
└── requirements.txt
```

## Monitored hardware

| Nickname    | Appliance       | Model                      | Calculation logic                                  |
| ----------- | --------------- | -------------------------- | -------------------------------------------------- |
| ❄️ Artolfo  | Air Conditioner | Gree G-Top (Inverter)      | Power per set point (non-linear, ACEEE rule)       |
| 🚿 Shauna   | Electric Shower | Lorenzetti Advanced Quadra | Fixed power per selector position × time           |
| 🧺 Morrisse | Washing Machine | Electrolux LES11 (11kg)    | Fixed cost per cycle (INMETRO label, motor energy) |
| 🌀 Versares | Fan             | Ultra 30cm                 | Nominal power × time                               |

Base load (refrigerator + standby) is modeled separately as a continuous draw, since it runs 24/7 regardless of sessions.

## Features

- **Session tracking** — Start/Stop per appliance with elapsed-time energy calculation.
- **Forgot-to-turn-off alerts** — a background watchdog thread monitors active sessions and warns the user when an appliance stays on past a configurable limit (e.g. shower over 20 min), even with no interaction.
- **`/invoice`** — partial monthly bill: per-appliance breakdown, base load, full-month projection, and comparison against the previous month.
- **`/grafico`** — bar chart of kWh per appliance for the current month.
- **`/reset`** — clears orphaned active sessions (e.g. after a restart) without touching history.
- **Configurable tariff** — kWh cost and tariff flags (Green/Yellow/Red) set in `config.json`, reflecting local utility rates (Coelba — Bahia, Brazil).

## Tech stack

- **Language:** Python 3.12
- **Interface:** pyTelegramBotAPI (Telebot)
- **Database:** SQLite3 (WAL mode for concurrent read/write between the bot and the watchdog thread)
- **Charts:** matplotlib
- **Config:** python-dotenv for the token

## How to run

1. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Create the database:

   ```
   python database_setup.py
   ```

3. Create a `.env` file in the project root:

   ```
   TELEGRAM_TOKEN=your_token_here
   ```

4. Run the bot:

   ```
   python interface/telegram_bot.py
   ```

## Database structure

- **sessoes_ativas** — current running timers (one row per active appliance per user). Includes `ja_alertado` so the watchdog does not repeat alerts.
- **historico_uso** — definitive log with cost (BRL), consumption (kWh), and duration, written when an appliance is turned off or a cycle is registered.

## Notes

Timestamps are stored in UTC (`CURRENT_TIMESTAMP`) and all duration math uses UTC to stay consistent. Base-load defaults assume a frost-free refrigerator (~35 kWh/month) plus ~20 W of standby; adjust in `config.json` against the appliance's INMETRO label.
