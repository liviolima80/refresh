#!/bin/sh

cd /home/publish
dotnet WebServer.dll  --urls "http://0.0.0.0:8888"
