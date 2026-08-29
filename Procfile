# Telemetry (car_data / position_data) loads as an asyncio task on this web
# process after the metadata pack is ready. Do not scale a second dyno.
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
