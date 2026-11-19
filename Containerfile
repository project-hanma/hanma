FROM python:3.12-slim

# Install dependencies and remove build artifact
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# Copy application (owned by root:root so runtime user cannot tamper with code/templates)
WORKDIR /hanma
COPY hanma.py  ./
COPY app/      ./app/
COPY themes/   ./themes/
COPY conf/     ./conf/

# Non-root user with write access restricted to runtime output and site directories
RUN useradd -r -u 1000 -g users hanma \
    && mkdir -p /site /output /hanma/output \
    && chown -R hanma:users /site /output /hanma/output

USER hanma

# Volume: mount your Markdown source at /site (and optionally mount /output if writing there)
VOLUME ["/site"]

EXPOSE 8000

ENTRYPOINT ["python", "/hanma/hanma.py"]
CMD ["--output", "/output", "/site"]
