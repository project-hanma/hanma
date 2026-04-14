#!/bin/bash

podman run -ti --rm --name hanma --hostname hanma -v ./conf/test.yml:/hanma/conf/hanma.yml -v ./site:/site -v./output:/output -p 8000:8000 hanma:testing /site
