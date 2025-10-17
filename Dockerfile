
FROM python:3.11-slim

RUN apt-get update && apt-get install -y graphviz && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY requirements.txt /work/requirements.txt
RUN pip install -r /work/requirements.txt

COPY . /work
RUN pip install -e .

EXPOSE 8501
CMD ["streamlit", "run", "gtflow/gui/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
