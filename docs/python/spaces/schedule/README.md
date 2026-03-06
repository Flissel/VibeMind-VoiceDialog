# Schedule Space

The Schedule space handles time-based operations including reminders, calendar events, and scheduling. It includes a natural language time parser for interpreting voice-spoken time references.

## Directory Structure

```
python/spaces/schedule/
├── __init__.py
├── config.py                   # SCHEDULE_* configuration settings
├── agents/                     # Backend agents
│   ├── __init__.py
│   └── schedule_agent.py       # ScheduleBackendAgent (schedule.* events)
├── nlp/                        # Natural language processing
│   ├── __init__.py
│   └── time_parser.py          # Natural language time parsing
├── tools/                      # Tool implementations
│   ├── __init__.py
│   └── schedule_tools.py       # Schedule tool functions
└── workers/                    # Background workers
    ├── __init__.py
    └── schedule_worker.py      # Schedule monitoring worker
```

## Agent

### ScheduleBackendAgent (`agents/schedule_agent.py`)

Handles all `schedule.*` events (6 event types):

- `schedule.create` -- Create a new scheduled event or reminder
- `schedule.list` -- List upcoming events
- `schedule.cancel` -- Cancel a scheduled event
- `schedule.modify` -- Modify an existing event
- `schedule.status` -- Check schedule status
- `schedule.snooze` -- Snooze a reminder or event

Stream: `events:tasks:schedule`

## NLP

### Time Parser (`nlp/time_parser.py`)

Parses natural language time expressions from voice input into structured datetime objects. Handles:

- Relative times: "in 5 minutes", "in einer Stunde" (in one hour)
- Absolute times: "um 15 Uhr" (at 3 PM), "morgen um 10" (tomorrow at 10)
- Named references: "heute Abend" (this evening), "naechste Woche" (next week)
- Recurring patterns: "jeden Montag" (every Monday), "taeglich um 9" (daily at 9)

Supports both German and English time expressions.

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `schedule_tools.py` | `create_event`, `list_events`, `cancel_event`, `modify_event`, `get_status`, `snooze_event` | Core scheduling operations |

## Workers

`schedule_worker.py` -- Background worker that:

- Monitors upcoming events and triggers reminders
- Checks for due events on a periodic interval
- Sends notification broadcasts to the Electron UI

## Configuration

`config.py` contains `SCHEDULE_*` settings.

Relevant `.env` settings:

```bash
SCHEDULE_ENABLED=true          # Enable the Schedule space
```

When `SCHEDULE_ENABLED` is not set or is `false`, the Schedule space is inactive and schedule events will not be processed.
