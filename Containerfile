FROM python:3.12-slim

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

EXPOSE 10000

CMD ["python", "-m", "app"]