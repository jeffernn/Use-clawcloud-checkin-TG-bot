# Base image with timezone support
FROM python:3.9-slim

# Set Beijing timezone (Asia/Shanghai)
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai' > /etc/timezone

# Environment variables for Clawcloud log collection
# 1. Force Python to disable output buffering (critical for real-time logs)
# 2. Set UTF-8 encoding to avoid garbled Chinese characters in logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

# Install required Python packages
RUN pip install --no-cache-dir telethon pytz

# Set working directory
WORKDIR /app

# Copy application files to the image
COPY checkin.py .
COPY chat_name.session .

# Run script with unbuffered mode (JSON format to fix Docker warnings)
# -u parameter: Double guarantee for unbuffered output
CMD ["python", "-u", "checkin.py"]
