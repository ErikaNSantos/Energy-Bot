# ⚡ Residential Energy Monitoring Bot

A residential energy monitoring system developed to replace manual spreadsheets and fragmented consumption estimates with a structured, event-driven tracking model.

The project records appliance usage in real time, persists operational history in SQLite, and applies equipment-specific consumption models to estimate electricity costs throughout the month. Rather than relying on static averages, the system treats each activation as an individual event, enabling more realistic projections and granular consumption analysis.

## Project Motivation

Estimating residential electricity costs is deceptively difficult. Most household appliances do not operate continuously, and some — particularly inverter-based air conditioners — exhibit highly variable power consumption depending on operating conditions.

Traditional spreadsheets often reduce this complexity to fixed monthly estimates, sacrificing accuracy and making it difficult to identify the true sources of energy consumption.

This project addresses that limitation by modeling appliance usage as discrete operating sessions. Every activation becomes a measurable event with a defined start, duration, consumption profile, and associated cost.

## System Architecture

The architecture deliberately separates business logic from interface concerns.

All energy calculations are encapsulated within the core layer, allowing the computational model to remain independent from Telegram-specific implementations. This separation enables future migration to alternative interfaces without requiring modifications to the calculation engine.

```text
energy-bot/
├── core/
│   └── energia.py        # Energy calculation engine
├── interface/
│   └── telegram_bot.py   # Telegram interface and watchdog services
├── data/
│   ├── config.json       # Tariffs, appliances and operating parameters
│   └── logs.db           # SQLite database
├── database_setup.py
└── requirements.txt
```

The result is a modular structure in which the energy model, persistence layer, and user interface evolve independently.

## Consumption Models

Different appliances require different approaches to consumption estimation.

| Appliance       | Model                      | Methodology                                                        |
| --------------- | -------------------------- | ------------------------------------------------------------------ |
| Air Conditioner | Gree G-Top Inverter        | Non-linear power estimation based on set-point temperature         |
| Electric Shower | Lorenzetti Advanced Quadra | Fixed power draw according to selector position and operating time |
| Washing Machine | Electrolux LES11           | Consumption per complete cycle derived from INMETRO data           |
| Fan             | Ultra 30 cm                | Nominal power multiplied by operating duration                     |

A separate baseline consumption model accounts for loads that operate continuously, such as refrigerators and standby devices. This prevents always-on equipment from distorting appliance-level analyses while preserving realistic monthly projections.

## Core Features

### Session-Based Monitoring

Appliances are activated through Start/Stop events. The system records operating duration and calculates consumption only for the period in which the equipment was effectively running.

### Autonomous Safety Monitoring

A background watchdog process continuously monitors active sessions.

When an appliance exceeds a predefined operating threshold, the system automatically notifies the user, helping prevent situations such as forgotten showers, fans, or air conditioners remaining active for extended periods.

### Monthly Cost Projection

The `/invoice` command provides:

* Current accumulated consumption
* Appliance-level breakdown
* Baseline consumption estimate
* End-of-month projection
* Comparison with the previous billing cycle

This transforms raw operational data into actionable information for decision-making.

### Consumption Visualization

The `/grafico` command generates graphical summaries of monthly energy distribution, facilitating identification of dominant consumption sources.

### Operational Recovery

The `/reset` command resolves orphaned active sessions caused by interruptions or unexpected shutdowns without affecting historical records.

## Technology Stack

* **Python 3.12**
* **SQLite3**
* **pyTelegramBotAPI**
* **Matplotlib**
* **python-dotenv**

SQLite operates in WAL (Write-Ahead Logging) mode, allowing concurrent database access between Telegram handlers and background monitoring services while preserving consistency.

## Execution

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize the database

```bash
python database_setup.py
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN=your_token_here
```

### 4. Start the bot

```bash
python interface/telegram_bot.py
```

## Database Design

The persistence layer is intentionally minimal.

### `sessoes_ativas`

Stores currently running appliance sessions.

Each record contains the information required for real-time monitoring, including alert state tracking to prevent duplicate notifications.

### `historico_uso`

Stores finalized operational events.

Each record contains:

* Duration
* Consumption (kWh)
* Monetary cost (BRL)
* Appliance information
* Timestamp metadata

This table serves as the definitive source for historical analysis and billing projections.

## Engineering Considerations

All timestamps are stored in UTC to eliminate ambiguity in duration calculations and maintain consistency across system operations.

Default baseline consumption assumptions are derived from typical frost-free refrigerator demand and residential standby loads. These values can be adjusted through `config.json` to reflect local conditions or appliance-specific INMETRO specifications.

By combining event-driven monitoring, persistent operational history, and appliance-specific consumption models, the project transforms household electricity usage from a rough estimate into a measurable and continuously auditable system.

