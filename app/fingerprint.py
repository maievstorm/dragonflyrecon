import argparse
import json
import sys
from argparse import RawTextHelpFormatter
from os.path import isdir
from os import path
from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import DictCursor
from minio import Minio
import os
from psycopg2.extensions import AsIs
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
import time


DEFAULT_CONFIG_FILE = "db.cnf.SAMPLE"
DEFAULT_MINIO_CONFIG_FILE = "minio.cnf.SAMPLE"


parser = argparse.ArgumentParser(
    description="Dejavu: Audio Fingerprinting library", formatter_class=RawTextHelpFormatter)
parser.add_argument('--fingerprint', type=list, default=['mp3', 'mp3'])
parser.add_argument('--config', type=dict, default=None)
parser.add_argument('--minio_config', type=dict, default=None)
parser.add_argument('--recognize', type=int, default=0)
parser.add_argument('--is_save', type=int, default=0)
parser.add_argument('--fast_check', type=int, default=0)
parser.add_argument('--hash', type=int, default=0)
args = parser.parse_args()


class Utils:
    def __init__(self, save_location='mp3',minio_config=None) -> None:
        self.DETAIL_CRAWL = 'detail_crawl'
        self.minio_config = minio_config
        print( self.minio_config )

    def init_minio(self):
        try:
            self.client = Minio(**self.minio_config)
        except Exception as e:
            print(e)

    def close_minio(self):
        self.client = 0

    def get_audio(self, bucket_name: str, object_name: str, song_name: str, save_location):
        try:
            self.client.fget_object(bucket_name=bucket_name, object_name=object_name,
                                    file_path=f'{save_location}/{song_name}.mp3')
        except Exception as e:
            print(e)

    def remove_file(self,folder):
        for dir in os.listdir(folder):
            os.remove(f'{folder}/{dir}')

    def hash_song(self, djv, directory,song_info,list_info_songs):
        print('hash_songs')
        if path.exists(directory) == False:
            os.mkdir(directory)


        num_process = 4

        for i in range(0,len(list_info_songs),num_process):
            self.init_minio()
            first = i
            last = len(list_info_songs) if i + num_process > len(list_info_songs) else i + num_process

            for j in range(first, last):
                item = list_info_songs[j]

                try:
                    self.client.fget_object(bucket_name=item[0], object_name=item[1],
                                            file_path=f'{directory}/{item[2]}{item[3]}')

                except Exception as e:
                    print(e)
                    print(item[2])
            try:
                self.close_minio()
                print('hash_songs 123')
                djv.fingerprint_directory(f"{directory}", [".mp3", ".wav"], num_process, song_info)
            except Exception as e:
                print(item[2])


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
    return config


def get_hash_song(conn):
    song_info = {}
    list_info_songs = []

    with conn.cursor() as cur:
        query = f"""
            SELECT id,name,path FROM detail_crawl
            where status = '0' and item_type = 'official_song';
        """
        cur.execute(query)
        while True:
            rows = cur.fetchmany(50)
            if not rows:
                break
            for row in rows:
                tail = row[2][-4:]

                list_path = row[2].split('/')
                bucket_name = list_path[0]
                row_2 = '/'.join(list_path[1:])
                song_info[row[0]] = [row[1], row_2]
                list_info_songs.append([bucket_name,row_2,row[0],tail])
        cur.close()
    return song_info,list_info_songs


if __name__ == '__main__':

    config_file = args.config
    if config_file is None:
        config_file = DEFAULT_CONFIG_FILE
    
    minio_config = args.minio_config
    if minio_config is None:
        minio_config = init(DEFAULT_MINIO_CONFIG_FILE)
    db_config = init(config_file)

    while True:

        print('Connecting to the PostgreSQL database...')
        conn = psycopg2.connect(**db_config.get("database", {}))

        song_info,list_info_songs = get_hash_song(conn)
        conn.close()

        print(len(list_info_songs))

        if len(list_info_songs) != 0:
            djv = Dejavu(init(config_file))
            utils = Utils(minio_config=minio_config)
            directory = 'mp3'
            utils.hash_song(djv, directory,song_info,list_info_songs)
        else:
            time_sleep = 24*60*60
            print(f'sleep: {time_sleep}')
            time.sleep(time_sleep)