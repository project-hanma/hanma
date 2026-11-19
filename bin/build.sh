#!/bin/bash
set -euo pipefail

podman build --no-cache -f Containerfile -t localhost/hanma:testing .
