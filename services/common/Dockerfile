FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Aggregate requirements
COPY services/service_registry/requirements.txt /tmp/req1.txt
COPY services/autoscaler/requirements.txt /tmp/req2.txt
COPY services/docker_service/requirements.txt /tmp/req3.txt
COPY services/ui/requirements.txt /tmp/req4.txt
RUN pip install --no-cache-dir -r /tmp/req1.txt -r /tmp/req2.txt -r /tmp/req3.txt -r /tmp/req4.txt

# Copy all service code and common entrypoint
COPY services /app/services
COPY services/common/entrypoint.py /app/entrypoint.py

VOLUME ["/data"]

CMD ["python", "/app/entrypoint.py"]
