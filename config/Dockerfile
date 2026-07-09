FROM python:3.14-slim #1
LABEL maintainer="oleggalas8@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 #2
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt . #3
RUN pip install --no-cache-dir -r requirements.txt #4 here is the last layer form cashe

COPY . . #5

EXPOSE 8000 

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"] # metadata