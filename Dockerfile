FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
RUN useradd --create-home --uid 10001 saarthi \
    && mkdir -p /data \
    && chown -R saarthi:saarthi /app /data
EXPOSE 5050
ENV PYTHONUNBUFFERED=1
ENV SAARTHI_DB_PATH=/data/saarthi.db
USER saarthi
CMD ["python3", "-m", "backend.server"]
