FROM python:3.9-alpine

RUN echo "http://dl-4.alpinelinux.org/alpine/v3.14/main" >> /etc/apk/repositories && \
    echo "http://dl-4.alpinelinux.org/alpine/v3.14/community" >> /etc/apk/repositories

RUN apk update

RUN apk add chromium chromium-chromedriver
RUN apk add imagemagick ffmpeg \
    msttcorefonts-installer fontconfig \
    build-base zlib-dev jpeg-dev libpng-dev freetype-dev

RUN update-ms-fonts && fc-cache -f

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

WORKDIR /app

COPY . .

CMD [ "python", "main.py" ]
