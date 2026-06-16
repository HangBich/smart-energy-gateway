FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway.py rule_engine.py state_store.py .
ENV PYTHONUNBUFFERED=1
CMD ["python", "gateway.py"]
