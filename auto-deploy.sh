#!/bin/bash
sudo docker build -t derailed-gateway .
sudo docker run -p 5000:5000 -d derailed-gateway