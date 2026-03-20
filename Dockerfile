FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/python

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY python ./python
COPY server.py ./server.py

RUN mkdir -p /app/uploads

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
