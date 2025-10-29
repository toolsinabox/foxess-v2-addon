ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    bash

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Playwright and browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium --with-deps

# Copy application files
COPY run.sh /
COPY scraper.py /app/

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
