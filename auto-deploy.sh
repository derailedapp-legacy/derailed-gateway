#!/bin/bash
sudo docker build -t recorder-gateway .
sudo docker run -p 5000:5000 -d recorder-gateway