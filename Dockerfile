FROM python:3.13-alpine
RUN pip install flask requests docker
COPY src/*.py /app/
WORKDIR /app
ENTRYPOINT ["python","main.py"]