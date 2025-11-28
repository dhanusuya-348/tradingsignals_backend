FROM python:3.10-slim

WORKDIR /app

# Install dependencies.
COPY requirements.txt .

RUN pip install -r requirements.txt

# Copy the source code into the container.
COPY . .

# Expose the port that the application listens on.
EXPOSE 8080

# Run the application.
CMD gunicorn 'algo.server:app' --bind=0.0.0.0:8080
