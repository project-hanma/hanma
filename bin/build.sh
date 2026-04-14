#!/bin/bash

podman build --no-cache -f Containerfile -t localhost/hanma:testing .
