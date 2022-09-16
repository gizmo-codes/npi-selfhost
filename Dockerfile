FROM python:3.9-slim
ENV LISTEN_PORT=5755
EXPOSE 5755
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN apt-get update && \
    apt-get install -y gnupg wget curl unzip --no-install-recommends && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list && \
    apt-get update -y && \
    apt-get install -y google-chrome-stable && \
    CHROMEVER=$(google-chrome --product-version | grep -o "[^\.]*\.[^\.]*\.[^\.]*") && \
    DRIVERVER=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMEVER") && \
    wget -q --continue -P /chromedriver "http://chromedriver.storage.googleapis.com/$DRIVERVER/chromedriver_linux64.zip" && \
    unzip /chromedriver/chromedriver* -d /chromedriver/
COPY . .
ENV PATH /chromedriver:$PATH
# Shell form (/bin/sh)
# CMD python -u npi_app.py
# Exec form
CMD ["waitress-serve","--listen=*:5755", "npi_app:npi_app"]