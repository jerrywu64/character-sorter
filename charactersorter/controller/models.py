import abc
import math
import json
import numpy as np
import scipy.stats as st
from django.db import models
from django.utils import timezone

import sorterinput.models

class Controller(abc.ABC):

    def __init__(self):
        # A Controller can be instantiated for performance reasons. The dirty
        # marker helps keep track of whether cached valeus can be used. Note
        # that this is not totally reliable because e.g. SortRecords may be
        # modified through other means.
        self.dirty = True

    @abc.abstractmethod
    def get_sorted_chars(self, charlist):
        """Get a list of char IDs, sorted from best to worst."""
        pass

    @abc.abstractmethod
    def get_next_comparison(self, charlist):
        """Retrieves the next pair of char ids to compare, or None"""
        pass

    def register_comparison(self, charlist, char1_id, char2_id, value):
        record = SortRecord()
        record.charlist = charlist
        record.char1 = sorterinput.models.Character.objects.get(id=char1_id)
        assert record.char1.characterlist == charlist
        record.char2 = sorterinput.models.Character.objects.get(id=char2_id)
        assert record.char2.characterlist == charlist
        record.value = value
        record.save()
        self.dirty = True
        return record

    @abc.abstractmethod
    def get_annotations(self, charlist):
        """Returns an annotation for each character, if any, e.g. whether the
        character has been sorted or not. Returns a dict mapping character ID
        to annotation, or None if that character has no annotation."""
        pass

    def get_graph_info(self, charlist):
        """If graphing is supported for this controller type, returns data
        necessary to graph the characters. More specifically, returns a dict
        with a "graph_type" key indicating the graph type, as well as the
        information needed (appropriately escaped) for that graph type. See the
        graph html template for more information. If graphing is not supported,
        returns None (the default)."""
        return None

    def get_progress_info(self, charlist):
        """Returns a string to display progress info, e.g. "5/10 done". Can
        also return NOne."""
        return None


class InsertionSortController(Controller):

    def __init__(self):
        super().__init__()
        self.sorted_chars = None  # In decreasing order of awesomeness.
        self.compair = None

    def insertion_sort(self, charlist, characters=None):
        if not self.dirty:
            return
        self.dirty = False
        characters = characters or charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        last_matches = SortRecord.get_last_matches(charlist)
        record_dict = {}
        for (char1_id, char2_id), match in last_matches.items():
            if match.char1.id == char1_id:
                record_dict[(char1_id, char2_id)] = match.value
            else:
                assert match.char2.id == char1_id
                record_dict[(char1_id, char2_id)] = -match.value
        sorted_chars = []
        for character in characters:
            # Binary insertion sort to insert character into
            # the sorted list of chars. Note that the list
            # of sorted chars necessarily contains ids less than
            # the new one.
            low = 0
            high = len(sorted_chars)
            while low < high:
                mid = (low + high) // 2
                compair = (character, sorted_chars[mid])
                if compair in record_dict:
                    value = record_dict[compair]
                    if value > 0:
                        high = mid
                    else:
                        low = mid + 1
                else:
                    sorted_chars.insert(high, character)
                    self.sorted_chars = sorted_chars
                    self.compair = compair
                    return
            sorted_chars.insert(high, character)
        self.sorted_chars = sorted_chars
        self.compair = None

    def get_sorted_chars(self, charlist):
        characters = charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        self.insertion_sort(charlist, characters)
        sorted_chars = list(self.sorted_chars)
        sorted_char_set = set(sorted_chars)
        for char_id in characters:
            if char_id not in sorted_char_set:
                sorted_chars.append(char_id)
        return sorted_chars

    def get_next_comparison(self, charlist):
        self.insertion_sort(charlist)
        return self.compair

    def get_annotations(self, charlist):
        characters = charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        self.insertion_sort(charlist, characters)
        sorted_char_set = set(self.sorted_chars)
        annotations = {
            char: None if char in sorted_char_set else "Unsorted"
            for char in characters}
        if self.compair is not None:
            annotations[self.compair[0]] = "Now Sorting"
        return annotations

    def get_progress_info(self, charlist):
        characters = charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        self.insertion_sort(charlist, characters)
        return "{}/{} sorted".format(len(self.sorted_chars) - 1, len(characters))


class GlickoRatingController(Controller):
    """Computes a Glicko rating (http://www.glicko.net/glicko.html) for each
    character. Glicko is better than Elo because it tracks the uncertainty of
    each character's rating, and e.g. newly added characters will have more
    uncertain ratings. Glicko2 would do even better, because it also tracks
    volatility; for example, maybe the user suddenly likes a character after
    having watched a show containing the character. However, Glicko2 is
    substantially more complicated than Glicko. I don't really understand how
    Glicko2 works, and it seems to be better optimized for tournament play with
    long ``rating periods''. Since I don't understand it and it doesn't seem to
    be opimized for this usage, I won't use it for the time being."""

    DEFAULT_RATING = 1500
    DEFAULT_RD = 350
    TYPICAL_RD = 50
    MIN_RD = 30
    RD_RESET_TIME = 90  # in days. c^2 = (default_rd^2 - typical_rd^2)/reset_time
    RD_INCREASE_SCALE_SQ = (DEFAULT_RD ** 2 - TYPICAL_RD ** 2) / RD_RESET_TIME
    CONFIDENCE_BOOST = 2  # Count each match this many times.
    Q = math.log(10) / 400

    # Parameters for preferring higher-ranked people. 
    # We compute a weight for each character as follows:
    # (clamp(rating, max, min) / min) ^ pow
    # When picking a character to rank, we perform a softmax based on the
    # rating deviation, however we upweight the deviation based on this factor.
    # So in aggregate we expect the highest-ranked people to have
    # (max / min ^ # pow)
    # tighter intervals.
    BOOST_RATING_MAX = 2500
    BOOST_RATING_MIN = 500
    BOOST_RATING_POW = 0.43  # ln(2) / ln(5)

    def __init__(self):
        super().__init__()
        self.rating_info = None
        self.ratings = None

    @classmethod
    def rd_after_time(cls, old_rd, old_time, new_time):
        if old_time is None:
            return cls.DEFAULT_RD
        delta_days = (new_time - old_time).total_seconds() / (3600 * 24)
        return min(math.sqrt(old_rd ** 2 + cls.RD_INCREASE_SCALE_SQ * delta_days),
                   cls.DEFAULT_RD)

    @classmethod
    def g_of_rd(cls, rd):
        """See the Glicko paper for details. Something to do wtih Gaussians,
        probably. A high RD means a low g value."""
        return 1 / math.sqrt(1 + 3 * (cls.Q * rd / math.pi) ** 2)

    @staticmethod
    def expected_result(r, r_other, g_rd_other):
        """Returns the expected value of the result (on a 1/0.5/0 scale) when a
        player of rating r has an opponent of rating r_other with g(RD of
        opponent) = g_rd_other. See paper for details."""
        return 1 / (
            1 + math.pow(10, -g_rd_other * (r - r_other) / 400))

    @classmethod
    def inv_dsquared_of_match(cls, g_rd_other, expected):
        """Calculates the value 1/d^2 for a match against an opponent of rating
        r_other with rating deviation rd_other. See paper for details. I think
        this is the information given by the match. A high RD of the opponent
        or a highly stacked match gives a low inverse dsquared."""
        return (
            cls.Q * cls.Q * g_rd_other * g_rd_other *
            expected * (1 - expected))

    @classmethod
    def compute_values(cls, r, rd, r_other, rd_other):
        g_rd_other = cls.g_of_rd(rd_other)
        expected = cls.expected_result(r, r_other, g_rd_other)
        inv_dsquared = cls.inv_dsquared_of_match(g_rd_other, expected)
        inv_rdsquared = 1 / (rd * rd)
        new_rdsquared = 1 / (inv_rdsquared + inv_dsquared)
        update_factor = cls.Q * new_rdsquared * g_rd_other
        return expected, inv_dsquared, new_rdsquared, update_factor

    @classmethod
    def process_record(cls, record, rating_info):
        """Given a SortRecord and a dict mapping char IDs to tuples (rating,
        rd, last_played_timestamp), updates the dict reflecting the SortRecord."""
        ids = [record.char1.id, record.char2.id]
        timestamp = record.timestamp
        value = (record.value + 1) / 2  # to convert to 1/0.5/0 system
        rs, rds, times = zip(*[rating_info[char_id] for char_id in ids])
        for t in times:
            assert (t is None) or (timestamp >= t)
        results = [value, 1 - value]
        rds = [cls.rd_after_time(rds[i], times[i], timestamp)
               for i, _ in enumerate(ids)]
        new_rs = []
        new_rds = []
        for i, (r, rd, r_other, rd_other, result) in enumerate(zip(
                rs, rds, reversed(rs), reversed(rds), results)):
            expected, _, new_rdsquared, update_factor = cls.compute_values(
                r, rd, r_other, rd_other)
            new_rs.append(r + (
                update_factor * (result - expected)))
            new_rds.append(math.sqrt(new_rdsquared))
        for i, r, rd in zip(ids, new_rs, new_rds):
            rating_info[i] = (r, rd, timestamp)

    def compute_ratings(self, charlist, raw=False, interval=False):
        if self.dirty:
            self.dirty = False
            records = charlist.sortrecord_set.all().order_by("timestamp").select_related()
            char_ids = charlist.character_set.all().values_list("id", flat=True)
            rating_info = {
                char_id: (self.DEFAULT_RATING, self.DEFAULT_RD, None)
                for char_id in char_ids}
            for record in records:
                for _ in range(self.CONFIDENCE_BOOST):
                    self.process_record(record, rating_info)
            # Make rds decay to the present
            now = timezone.now()
            for char_id, (r, rd, ts) in rating_info.items():
                rating_info[char_id] = r, self.rd_after_time(rd, ts, now), None
            self.rating_info = rating_info
            ratings = {}
            for char_id in char_ids:
                # Return rating - 2 * rd
                r, rd, _ = rating_info[char_id]
                ratings[char_id] = (
                    (r - 2 * rd) if not interval else (r - 2 * rd, r + 2 *rd))
            self.ratings = ratings
        return self.rating_info if raw else self.ratings

    def get_sorted_chars(self, charlist):
        """Get a list of char IDs, sorted from best to worst."""
        ratings = self.compute_ratings(charlist)
        return sorted(ratings, key=ratings.get, reverse=True)

    @classmethod
    def get_match_weight(cls, char_id, opponent_id, rating_info, last_matches):
        """How much do we want this match to occur? We'd like a match which
        will minimize char_id's rd while avoiding repeated matchups, and
        maximizing the ranking of high-scoring characters."""
        r, rd, _ = rating_info[char_id]
        r_other, rd_other, _ = rating_info[opponent_id]
        _, inv_dsquared, _, _ = cls.compute_values(r, rd, r_other, rd_other)
        last_match = last_matches.get((char_id, opponent_id), None)
        days_since_last = (
            cls.RD_RESET_TIME if last_match is None else
            min((timezone.now() - last_match.timestamp).total_seconds()
                / (3600 * 24),
                cls.RD_RESET_TIME))
        return days_since_last * inv_dsquared

    @classmethod
    def get_char_weights(cls, char_ids, rating_info, rating_pow=None):

        """How much do we want to see a character in a match? Softmax based on
        their rating deviation, scaled to each increment of 15, boosted by
        rating."""
        rds = np.array([rating_info[char_id][1] for char_id in char_ids])
        rds = rds / 15

        rs = np.array([rating_info[char_id][0] for char_id in char_ids])

        rs = np.minimum(np.maximum(rs, cls.BOOST_RATING_MIN), cls.BOOST_RATING_MAX)
        rs /= cls.BOOST_RATING_MIN
        rs = rs ** (rating_pow if rating_pow is not None else cls.BOOST_RATING_POW)

        raw_weights = rds * rs
        raw_weights -= np.max(raw_weights)

        char_weights = np.exp(raw_weights)
        char_weights /= np.sum(char_weights)

        return char_weights

    def get_next_comparison(self, charlist):
        """Retrieves the next pair of characters to compare, or None"""
        char_ids = charlist.character_set.all().values_list("id", flat=True)
        if len(char_ids) < 2:
            return None
        self.compute_ratings(charlist)
        # Pick a character based on how uncertain their rating is, proportional
        # to the cube of the uncertainty.
        char_weights = self.get_char_weights(char_ids, self.rating_info)
        char_id = np.random.choice(char_ids, p=char_weights)
        # Select their opponent:
        opponents = [opponent for opponent in char_ids if opponent != char_id]
        last_matches = SortRecord.get_last_matches(charlist)
        opponent_weights = np.array([self.get_match_weight(
            char_id, opponent, self.rating_info, last_matches) for opponent in opponents])
        opponent_weights /= np.sum(opponent_weights)
        return char_id, np.random.choice(opponents, p=opponent_weights)

    def get_annotations(self, charlist):
        """Returns an annotation for each character, if any, e.g. whether the
        character has been sorted or not. Returns a dict mapping character ID
        to annotation, or None if that character has no annotation."""
        ratings = self.compute_ratings(charlist, interval=False)
        return {i: int(r) for i, r in ratings.items()}

    def get_graph_info(self, charlist):
        self.compute_ratings(charlist)
        sorted_char_ids = sorted(
            list(self.rating_info.keys()),
            key=lambda char_id:
            self.rating_info[char_id][0] - 2 * self.rating_info[char_id][1],
            reverse=True)
        characters = charlist.character_set.all().values_list("id", "name")
        char_dict = {char_id: name for char_id, name in characters}
        return {
            "graph_type": "bar_with_error",
            "characters": json.dumps(
                [char_dict[char_id] for char_id in sorted_char_ids]),
            "ratings_raw": json.dumps(
                [self.rating_info[char_id][0] for char_id in sorted_char_ids]),
            "double_rds": json.dumps(
                [2 * self.rating_info[char_id][1] for char_id in sorted_char_ids]),
        }

    def get_progress_info(self, charlist):
        self.compute_ratings(charlist)
        info_list = list(self.rating_info.values())
        ratings = np.array([info[0] for info in info_list])[:, np.newaxis]
        rds = np.array([info[1] for info in info_list])[:, np.newaxis]
        rating_delta = np.abs(ratings - ratings.T)
        rd_composite = np.sqrt(rds * rds + rds.T * rds.T)
        probs = st.norm.cdf(rating_delta / rd_composite)
        mask = np.full_like(probs, True, dtype=bool)
        np.fill_diagonal(mask, False)
        mean_conf = np.average(probs[mask])
        # sorted_info = sorted(
        #     list(rating_info.values()),
        #     key=lambda x: x[0], reverse=True)  # Sorted by rating
        # confidences = []
        # for (rating1, rd1, _), (rating2, rd2, _) in zip(sorted_info, sorted_info[1:]):
        #     rating_delta = rating1 - rating2
        #     combined_rd = math.sqrt(rd1 ** 2 + rd2 ** 2)
        #     confidences.append(st.norm.cdf(rating_delta / combined_rd))
        # avg = np.average(confidences)
        return "Average confidence: {:.3f}".format(mean_conf)


class SortRecord(models.Model):
    charlist = models.ForeignKey(
        sorterinput.models.CharacterList, on_delete=models.CASCADE)
    char1 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE,
        related_name="sortrecord1")
    char2 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE,
        related_name="sortrecord2")
    timestamp = models.DateTimeField(auto_now_add=True)
    value = models.IntegerField()  # Positive means char1 wins.

    @staticmethod
    def get_last_matches(charlist):
        """Returns a dict mapping (char1_id, char2_id) to the most recent match among
        the charlist's matches."""
        last_matches = {}
        sorted_records = charlist.sortrecord_set.all().order_by("timestamp").select_related()
        for record in sorted_records:
            last_matches[(record.char1.id, record.char2.id)] = record
            last_matches[(record.char2.id, record.char1.id)] = record
        return last_matches

    def __str__(self):
        if self.value > 0:
            return "{} (win) vs {}".format(self.char1, self.char2)
        elif self.value < 0:
            return "{} vs {} (win)".format(self.char1, self.char2)
        else:
            return "{} vs {} (tie)".format(self.char1, self.char2)

CONTROLLER_TYPES = {
    "InsertionSortController": InsertionSortController,
    "GlickoRatingController": GlickoRatingController,
}
