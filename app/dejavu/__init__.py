import multiprocessing
import os
import sys
import traceback
from itertools import groupby
from time import time
import numpy as np
from typing import Dict, List, Tuple

import dejavu.logic.decoder as decoder
from dejavu.base_classes.base_database import get_database
from dejavu.config.settings import (DEFAULT_FS, DEFAULT_OVERLAP_RATIO,
                                    DEFAULT_WINDOW_SIZE, FIELD_FILE_SHA1,
                                    FIELD_TOTAL_HASHES,FIELD_SONG_ID,
                                    FINGERPRINTED_CONFIDENCE,
                                    FINGERPRINTED_HASHES, HASHES_MATCHED,
                                    INPUT_CONFIDENCE, INPUT_HASHES, OFFSET,
                                    OFFSET_SECS, SONG_ID, SONG_NAME, TOPN,TIME_CONSIDER)
from dejavu.logic.fingerprint import fingerprint


class Dejavu:
    def __init__(self, config):
        self.config = config

        # initialize db
        db_cls = get_database(config.get("database_type", "mysql").lower())

        self.db = db_cls(**config.get("database", {}))
        self.db.setup()

        # if we should limit seconds fingerprinted,
        # None|-1 means use entire track
        self.limit = self.config.get("fingerprint_limit", None)
        if self.limit == -1:  # for JSON compatibility
            self.limit = None
        self.__load_fingerprinted_audio_hashes()

    def __load_fingerprinted_audio_hashes(self) -> None:
        """
        Keeps a dictionary with the hashes of the fingerprinted songs, in that way is possible to check
        whether or not an audio file was already processed.
        """
        # get songs previously indexed
        self.songs = self.db.get_songs()
        self.songid_set = set()  # to know which ones we've computed before
        for song in self.songs:
            song_id = song[FIELD_SONG_ID]
            self.songid_set.add(song_id)

    def get_fingerprinted_songs(self) -> List[Dict[str, any]]:
        """
        To pull all fingerprinted songs from the database.

        :return: a list of fingerprinted audios from the database.
        """
        return self.db.get_songs()

    def delete_songs_by_id(self, song_ids: List[int]) -> None:
        """
        Deletes all audios given their ids.

        :param song_ids: song ids to delete from the database.
        """
        self.db.delete_songs_by_id(song_ids)

    def fingerprint_directory(self, path: str, extensions: str, nprocesses: int = None, song_info : list = None) -> None:
        """
        Given a directory and a set of extensions it fingerprints all files that match each extension specified.

        :param path: path to the directory.
        :param extensions: list of file extensions to consider.
        :param nprocesses: amount of processes to fingerprint the files within the directory.
        """
        # Try to use the maximum amount of processes if not given.
        try:
            nprocesses = nprocesses or multiprocessing.cpu_count()
        except NotImplementedError:
            nprocesses = 1
        else:
            nprocesses = 1 if nprocesses <= 0 else nprocesses

        pool = multiprocessing.Pool(nprocesses)

        filenames_to_fingerprint = []
        for filename, _ in decoder.find_files(path, extensions):
            # don't refingerprint already fingerprinted files
            song_id = int(filename.split("/")[1].split('.')[0])
            print(song_id)
            if song_id in self.songid_set:
                print(f"{filename} already fingerprinted, continuing...")
                continue

            filenames_to_fingerprint.append(filename)
        print(filenames_to_fingerprint)

        # Prepare _fingerprint_worker input
        worker_input = list(zip(filenames_to_fingerprint, [self.limit] * len(filenames_to_fingerprint)))

        # Send off our tasks
        iterator = pool.imap_unordered(Dejavu._fingerprint_worker, worker_input)


        # Loop till we have all of them
        while True:
            try:
                song_name, hashes, file_hash = next(iterator)
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                break
            except Exception:
                print("Failed fingerprinting")
                # Print traceback because we can't reraise it here
                traceback.print_exc(file=sys.stdout)
            else:
                song_id = int(song_name)
                sid = self.db.insert_song(song_id,song_info[song_id][0], file_hash, len(hashes))

                self.db.insert_hashes(sid, hashes)
                self.db.set_song_fingerprinted(sid)
                self.db.update_song_status(song_id)
                self.__load_fingerprinted_audio_hashes()

        pool.close()
        pool.join()

    def fingerprint_file(self, file_path: str, song_name: str = None) -> None:
        """
        Given a path to a file the method generates hashes for it and stores them in the database
        for later be queried.

        :param file_path: path to the file.
        :param song_name: song name associated to the audio file.
        """
        song_name_from_path = decoder.get_audio_name_from_path(file_path)
        song_hash = decoder.unique_hash(file_path)
        song_name = song_name or song_name_from_path
        # don't refingerprint already fingerprinted files
        if song_hash in self.songhashes_set:
            print(f"{song_name} already fingerprinted, continuing...")
        else:
            song_name, hashes, file_hash = Dejavu._fingerprint_worker(
                file_path,
                self.limit,
                song_name=song_name
            )
            sid = self.db.insert_song(song_name, file_hash)

            self.db.insert_hashes(sid, hashes)
            self.db.set_song_fingerprinted(sid)
            self.__load_fingerprinted_audio_hashes()

    def generate_fingerprints(self, samples: List[int], Fs=DEFAULT_FS) -> Tuple[List[Tuple[str, int]], float]:
        f"""
        Generate the fingerprints for the given sample data (channel).

        :param samples: list of ints which represents the channel info of the given audio file.
        :param Fs: sampling rate which defaults to {DEFAULT_FS}.
        :return: a list of tuples for hash and its corresponding offset, together with the generation time.
        """
        t = time()
        hashes = fingerprint(samples, Fs=Fs)
        fingerprint_time = time() - t
        return hashes, fingerprint_time

    def find_matches(self, fast_check,hashes: List[Tuple[str, int]]) -> Tuple[List[Tuple[int, int]], Dict[str, int], float]:
        """
        Finds the corresponding matches on the fingerprinted audios for the given hashes.

        :param hashes: list of tuples for hashes and their corresponding offsets
        :return: a tuple containing the matches found against the db, a dictionary which counts the different
         hashes matched for each song (with the song id as key), and the time that the query took.

        """
        t = time()
        matches, dedup_hashes = self.db.return_matches(fast_check,hashes)
        query_time = time() - t

        return matches, dedup_hashes, query_time
    def calculate_time(self,s,e):
        return (s - e)/DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO

    def align_matches(self, matches: List[Tuple[int, int]], dedup_hashes: Dict[str, int], queried_hashes: int,id_check,name_check,is_save,fast_check,
                      topn: int = TOPN) -> List[Dict[str, any]]:
        """
        Finds hash matches that align in time with other matches and finds
        consensus about which hashes are "true" signal from the audio.

        :param matches: matches from the database
        :param dedup_hashes: dictionary containing the hashes matched without duplicates for each song
        (key is the song id).
        :param queried_hashes: amount of hashes sent for matching against the db
        :param topn: number of results being returned back.
        :return: a list of dictionaries (based on topn) with match information.
        """
        # count offset occurrences per song and keep only the maximum ones.
        sorted_matches = sorted(matches, key=lambda m: (m[0], m[1]))
        counts = [(*key, len(list(group))) for key, group in groupby(sorted_matches, key=lambda m: (m[0], m[1]))]
        songs_matches = sorted(
            [max(list(group), key=lambda g: g[2]) for key, group in groupby(counts, key=lambda count: count[0])],
            key=lambda count: count[2], reverse=True
        )

        songs_result = []
        for song_id, offset, fingerprint_match in songs_matches[0:topn]:  # consider topn elements in the result
            song = self.db.get_song_by_id(song_id)

            song_name = song.get(SONG_NAME, None)
            song_hashes = song.get(FIELD_TOTAL_HASHES, None)
            nseconds = round(float(offset) / DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO, 5)
            hashes_matched = dedup_hashes[song_id]
            
            time_similar = 0.0
            print('fast_check:',fast_check)


            if fast_check != 1:

                list_offset = set()
                for id, count_match,time_match in sorted_matches:
                    if id == song_id and offset == count_match:
                        list_offset.add(time_match)
                list_offset = list(list_offset)
                list_offset.sort()


                for iter in range(0,len(list_offset)):
                    if iter == 0:
                        continue
                    delta = self.calculate_time(list_offset[iter],list_offset[iter -1])
                    if delta <= 1.5:
                        # offset_start = min(offset_start,list_offset[iter])
                        time_similar += delta
                if time_similar < 10:
                    continue

                accuracy_similar = 100 if time_similar > TIME_CONSIDER else time_similar/TIME_CONSIDER*100
                start_match_target = list_offset[0]/DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO
                start_match_source = (list_offset[0] -offset )/DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO

                song = {
                    'check_song_id':id_check,
                    'check_song_name':name_check,
                    SONG_ID: song_id,
                    SONG_NAME: song_name,
                    INPUT_HASHES: queried_hashes,
                    FINGERPRINTED_HASHES: song_hashes,
                    'time_similar': float(time_similar),
                    'accuracy_similar':accuracy_similar,
                    'fingerprint_match':fingerprint_match,
                    HASHES_MATCHED: hashes_matched,
                    # Percentage regarding hashes matched vs hashes from the input.
                    INPUT_CONFIDENCE: round(hashes_matched / queried_hashes, 2),
                    # Percentage regarding hashes matched vs hashes fingerprinted in the db.
                    FINGERPRINTED_CONFIDENCE: round(hashes_matched / song_hashes, 2),
                    'start_match_target': start_match_target,
                    'start_match_source': start_match_source
                }
            else:
                song = {
                    'check_song_id':id_check,
                    'check_song_name':name_check,
                    SONG_ID: song_id,
                    SONG_NAME: song_name,
                    INPUT_HASHES: queried_hashes,
                    FINGERPRINTED_HASHES: song_hashes,
                    'fingerprint_match':fingerprint_match,
                    HASHES_MATCHED: hashes_matched,
                    # Percentage regarding hashes matched vs hashes from the input.
                    INPUT_CONFIDENCE: round(hashes_matched / queried_hashes, 2),
                    # Percentage regarding hashes matched vs hashes fingerprinted in the db.
                    FINGERPRINTED_CONFIDENCE: round(hashes_matched / song_hashes, 2)
                }
            if is_save == 1 and fast_check == 0:
                self.db.insert_check_song(list(song.values()))
            self.db.update_song_status(id_check,'1')
            songs_result.append(song)
        return songs_result

    def recognize(self, recognizer, path,id = 1,name = '1',is_save = 0,fast_check = 1) -> Dict[str, any]:
        r = recognizer(self)
        return r.recognize(path, id,name,is_save,fast_check)

    @staticmethod
    def _fingerprint_worker(arguments):
        # Pool.imap sends arguments as tuples so we have to unpack
        # them ourself.
        try:
            file_name, limit = arguments
        except ValueError:
            pass

        song_name, extension = os.path.splitext(os.path.basename(file_name))

        fingerprints, file_hash = Dejavu.get_file_fingerprints(file_name, limit, print_output=True)

        return song_name, fingerprints, file_hash

    @staticmethod
    def get_file_fingerprints(file_name: str, limit: int, print_output: bool = False):
        channels, fs, file_hash = decoder.read(file_name, limit)
        fingerprints = set()
        channel_amount = len(channels)
        for channeln, channel in enumerate(channels, start=1):
            if print_output:
                print(f"Fingerprinting channel {channeln}/{channel_amount} for {file_name}")

            hashes = fingerprint(channel, Fs=fs)

            if print_output:
                print(f"Finished channel {channeln}/{channel_amount} for {file_name}")

            fingerprints |= set(hashes)

        return fingerprints, file_hash
