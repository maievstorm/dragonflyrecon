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

    def hash_song(self, djv, directory, extension):
        if path.exists(directory) == False:
            os.mkdir(directory)

        self.init_minio()
        song_info = {}
        with djv.db.cursor() as cur:
            # exps = str(input('Enter condition:'))
            query = f"""
                SELECT id,name,path FROM {self.DETAIL_CRAWL}
                where status = '0' and item_type = 'official_song';
            """
            # cur.execute(query,[AsIs(exps)])
            cur.execute(query)
            while True:
                self.remove_file('mp3')
                rows = cur.fetchmany(4)
                if not rows:
                    break
                for row in rows:
                    tail = row[2][-4:]

                    list_path = row[2].split('/')
                    bucket_name = list_path[0]
                    row_2 = '/'.join(list_path[1:])
                    song_info[row[0]] = [row[1], row_2]
                    # song_revert[row[1]] = [row[0],row[2]]
                    print('bucket_name',bucket_name)
                    print('row_2',row_2)

                    try:
                        self.client.fget_object(bucket_name=bucket_name, object_name=row_2,
                                                file_path=f'{directory}/{row[0]}{tail}')
                    except Exception as e:
                        print(e)
                        print(row[0])
                djv.fingerprint_directory(f"{directory}", [".mp3", ".wav"], 4, song_info)
            cur.close()
            self.close_minio()

    def check_song(self, is_save,fast_check):
        
        folder_test = 'test'
        if path.exists(folder_test) == False:
            os.mkdir(folder_test)
        self.init_minio()
        song_info = {}
        with djv.db.cursor() as cur:
            # exps = str(input('Enter condition:'))
            query = f"""
                SELECT id,name,path FROM {self.DETAIL_CRAWL}
                where item_type = 'check_song' and status = '0';
            """
            # cur.execute(query,[AsIs(exps)])
            cur.execute(query)
            while True:
                self.remove_file('test')
                rows = cur.fetchmany(1)
                if not rows:
                    break
                for row in rows:
                    tail = row[2][-4:]
                    list_path = row[2].split('/')
                    bucket_name = list_path[0]
                    row_2 = '/'.join(list_path[1:])
                    song_info[row[0]] = [row[1], row_2]
                    target_path = f'{folder_test}/{row[0]}{tail}'
                    try:
                        print('Check song id', row[0])
                        self.client.fget_object(bucket_name=bucket_name, object_name=row_2, file_path=target_path)
                        songs = djv.recognize(FileRecognizer, target_path, row[0], row[1], is_save,fast_check)
                        print(songs)
                    except Exception as e:
                        djv.db.update_song_status(row[0],'2')
                        print(e)
            self.remove_file('test')
            cur.close()
            self.close_minio()


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


if __name__ == '__main__':
    config_file = args.config
    if config_file is None:
        config_file = DEFAULT_CONFIG_FILE
    
    minio_config = args.minio_config
    if minio_config is None:
        minio_config = init(DEFAULT_MINIO_CONFIG_FILE)
    djv = Dejavu(init(config_file))
    if args.hash == 1:
        if len(args.fingerprint) == 2:

            directory = args.fingerprint[0]
            extension = args.fingerprint[1]
            utils = Utils(minio_config=minio_config)
            utils.hash_song(djv, directory, extension)

            print(f"Fingerprinting all .{extension} files in the {directory} directory")
        elif len(args.fingerprint) == 1:
            filepath = args.fingerprint[0]
            if isdir(filepath):
                print("Please specify an extension if you'd like to fingerprint a directory!")
                sys.exit(1)
            utils = Utils(minio_config=minio_config)
            utils.hash_song(djv, filepath)
    elif args.recognize == 1:
        utils = Utils(minio_config=minio_config)
        utils.check_song(args.is_save,args.fast_check)
