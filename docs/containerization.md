# Containerization

Hanma can be run as a container using Podman or Docker. The image defaults to a one-shot build of your site.

## Building the Image

```bash
podman build -t hanma:latest .
```

## Basic Usage (One-Shot Build)

Build your site from a local directory into an output directory:

```bash
podman run --rm \
  -v ./site:/site \
  -v ./output:/output \
  hanma:latest
```

## Serving from the Container

To serve the generated site from the container, override the default command:

```bash
podman run --rm -p 8000:8000 \
  -v ./site:/site \
  -v ./output:/output \
  hanma:latest --serve --host 0.0.0.0
```

Alternatively, mount a configuration file that enables serving:

```bash
podman run --rm -p 8000:8000 \
  -v ./site:/site \
  -v ./output:/output \
  -v ./conf/hanma.yml:/hanma/conf/hanma.yml \
  hanma:latest
```

*(Ensure `host: 0.0.0.0` is set in your config for the server to be reachable from the host).*
