FROM python:3.13-alpine

# Install uv (fast Python package manager)
RUN apk add --no-cache curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install dependencies with uv using system site-packages
COPY requirements.txt /requirements.txt
RUN uv pip install --system -r /requirements.txt

# App code
COPY src/*.py /app/
WORKDIR /app
CMD ["gunicorn", "-w", "2", "-k", "gthread", "--threads", "4", "-b", "0.0.0.0:80", "main:App"]