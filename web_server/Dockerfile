FROM mcr.microsoft.com/dotnet/sdk:8.0

RUN apt-get update -y
RUN apt-get install -y net-tools iputils-ping nano libfontconfig

WORKDIR /home/

COPY publish /home/publish

COPY start.sh /home/

RUN chmod +x start.sh
