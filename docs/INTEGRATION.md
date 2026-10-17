# Project integration

This full project archive already includes the incident database integration:

- `backend/app/main.py` registers the incident API router.
- `backend/app/jobs.py` persists completed job events and publishes JSON Lines/optional MQTT events.
- `backend/app/db.py`, `backend/app/persist.py`, and `backend/app/api/incidents.py` provide the incident store and API.
- `backend/tests/test_incidents.py` contains incident-store/API tests.

`files.zip` is a set of these source and documentation files, not a complete runnable project by itself. The complete project is this archive, which also supplies the backend core, model, frontend package files, and launch scripts.

For setup and run commands, see the Ubuntu instructions in `README.md`.