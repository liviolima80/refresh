FROM python:3.11.14

RUN apt-get update -y
RUN apt-get install -y net-tools iputils-ping nano curl

WORKDIR /home/

RUN curl -L -o toolbox https://storage.googleapis.com/genai-toolbox/v0.21.0/linux/amd64/toolbox
RUN chmod +x toolbox

COPY start.sh /home/
COPY tools.yaml /home/

RUN chmod +x start.sh

