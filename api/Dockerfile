# The API as the local daily driver (Phase B3-local).
#
# Deliberately the SAME shape as the Render service in ../render.yaml — pip from
# the exported requirements.txt, migrations then uvicorn, ONE worker — so that
# when hosting does happen, it is a change of venue and not a change of runtime.
# Read render.yaml's header for why each of those is what it is; the worker count
# in particular is a correctness constraint, not a tuning knob
# (services/ai_grade_queue.py serialises with a per-PROCESS lock).
#
# This image is for RUNNING the app, not developing it: there is no bind mount of
# the source and no --reload. Editing code is still `uvicorn --reload` on the
# host, on :8000, which this stack deliberately does not occupy.

FROM python:3.13-slim

# Unbuffered so `docker compose logs` shows a crash as it happens rather than
# after the buffer flushes — which matters most on the migration step below.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# Dependencies first, so a source edit does not re-resolve the whole tree.
# Every wheel here is manylinux (psycopg2-BINARY bundles libpq, pillow and
# asyncpg ship wheels), so no compiler and no apt layer is needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# `python -c` rather than curl: the slim image has no curl, and adding one just
# for a health check is a whole apt layer.
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=6 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=4).status==200 else 1)"

# Migrations run on every start. They are idempotent, and a failure here fails
# the container loudly instead of serving an app against a stale schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
