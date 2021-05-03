FROM python:3.9-slim

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-binary pydantic -r /app/requirements.txt

COPY ./main.py /app/
COPY ./action.yml /app/

WORKDIR /app

CMD ["/app/main.py"]
