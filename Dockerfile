FROM python:3.13-alpine

ADD ./ /tw

WORKDIR /tw

RUN pip install -r requirements.txt

CMD ["python", "-OO", "-u", "/tw/main.py"]
