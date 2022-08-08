import abc
from time import time
from typing import Dict, List, Tuple

import numpy as np

from dejavu.config.settings import DEFAULT_FS


class BaseRecognizer(object, metaclass=abc.ABCMeta):
    def __init__(self, dejavu):
        self.dejavu = dejavu
        self.Fs = DEFAULT_FS

    def _recognize(self, data,id_check,name_check,is_save,fast_check) -> Tuple[List[Dict[str, any]], int, int, int]:

        fingerprint_times = []
        hashes = set()  # to remove possible duplicated fingerprints we built a set.
        for channel in data:
            fingerprints, fingerprint_time = self.dejavu.generate_fingerprints(channel, Fs=self.Fs)
            fingerprint_times.append(fingerprint_time)
            hashes |= set(fingerprints)

        matches, dedup_hashes, query_time = self.dejavu.find_matches(fast_check,hashes)


        t = time()
        final_results = self.dejavu.align_matches(matches, dedup_hashes, len(hashes),id_check,name_check,is_save,fast_check)
        align_time = time() - t

        return final_results, np.sum(fingerprint_times), query_time, align_time

    @abc.abstractmethod
    def recognize(self) -> Dict[str, any]:
        pass  # base class does nothing
