ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    chromium \
    chromium-chromedriver \
    bash

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application files
COPY run.sh /
COPY scraper.py /app/

RUN chmod a+x /run.sh

# Set environment
ENV PYTHONUNBUFFERED=1

CMD [ "/run.sh" ]
