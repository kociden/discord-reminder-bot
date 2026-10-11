FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Tokyo \
    DB_PATH=/data/reminder.db

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install .

VOLUME /data
CMD ["python", "-m", "reminder_bot.main"]
