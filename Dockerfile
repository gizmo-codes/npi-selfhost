FROM python:3.9-slim
ENV LISTEN_PORT=5755
EXPOSE 5755
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Shell form (/bin/sh)
# CMD python -u npi_app.py
# Exec form
CMD ["waitress-serve","--listen=*:5755", "npi_app:npi_app"]