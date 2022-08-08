 
FROM continuumio/miniconda3

# 
WORKDIR /code

# 
COPY ./requirements.txt /code/requirements.txt

#
RUN conda install -c conda-forge pydub
RUN conda install -c conda-forge PyAudio
RUN conda install -c conda-forge psycopg2
RUN conda install -c conda-forge ffmpeg

# 
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 
COPY ./app /code

# 
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]