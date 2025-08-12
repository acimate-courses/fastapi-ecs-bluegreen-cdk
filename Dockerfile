FROM public.ecr.aws/docker/library/python:3.11-slim
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
COPY ./app /code/app
CMD ["fastapi", "run", "app/main.py", "--port", "80"]
