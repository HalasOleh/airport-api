FROM python:3.14-slim
LABEL maintainer="oleggalas8@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt #4 here is the last layer form cashe

COPY . . 

EXPOSE 8000 

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"] # metadata