FROM python:3.12-slim

# Install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application
WORKDIR /hanma
COPY hanma.py  ./
COPY app/      ./app/
COPY themes/   ./themes/
COPY conf/     ./conf/

# Non-root user
RUN useradd -r -u 1000 -g users hanma \
    && mkdir -p /site /output \
    && chown -R hanma:users /site /output /hanma

USER hanma

# Volumes: mount your Markdown source at /site, get HTML at /output
VOLUME ["/site", "/output"]

EXPOSE 8000

ENTRYPOINT ["python", "/hanma/hanma.py"]
CMD ["--output", "/output", "/site"]
