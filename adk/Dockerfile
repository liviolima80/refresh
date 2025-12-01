FROM python:3.11.14

RUN apt-get update -y
RUN apt-get install -y net-tools iputils-ping nano 
RUN pip install google-adk
RUN pip install toolbox-core

WORKDIR /home/

COPY *.py /home/
COPY .env /home/
COPY *.json /home/
COPY start.sh /home/

RUN chmod +x start.sh

