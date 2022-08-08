from typing import Union
from dejavu import Dejavu
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from fastapi.responses import FileResponse
import argparse
from os import path
import json
import sys
from argparse import RawTextHelpFormatter
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from os.path import isdir
import os
from fastapi.middleware.cors import CORSMiddleware

def remove_file(folder):
    for dir in os.listdir(folder):
        os.remove(f'{folder}/{dir}')


DEFAULT_CONFIG_FILE = "db.cnf.SAMPLE"
def init(configpath):
    """
    Load config from a JSON file
    """
    try:
        with open(configpath) as f:
            config = json.load(f)
    except IOError as err:
        print(f"Cannot open configuration: {str(err)}. Exiting")
        sys.exit(1)

    # create a Dejavu instance
    return Dejavu(config)

app = FastAPI()
origins = [
    "https://dpaportal.apps.xplat.fis.com.vn",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
class Properties(BaseModel):
    language: str = None
    author: str = None

djv = init(DEFAULT_CONFIG_FILE)

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/upload_image/")
async def upload_image(is_save : int,fast_check:int,file: UploadFile = File(...)):
    if path.exists('static') == False:
        os.mkdir('static')
    file_name = file.filename
    print(file_name)
    content = await file.read()
    target_path = f"static/{file_name}"
    with open(target_path, "wb") as f:
        f.write(content)
    songs = djv.recognize(FileRecognizer, target_path,'-1',file_name,is_save,fast_check)
    remove_file('static')
    return songs


@app.get("/get_file/{file_name}")
def get_file(file_name: str):
    file_path = "./static/" + file_name
    return FileResponse(path=file_path)



@app.get("/hash")
def hash_song():
    os.system('python main.py --hash 1')
    return {"data": 'finish!!!'}

@app.get("/check")
def check_song():
    os.system('python main.py --recognize 1 --is_save 1')
    return {"data": 'finish!!!'}