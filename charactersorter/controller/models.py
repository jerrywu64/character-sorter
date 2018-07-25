import abc
import math
import numpy as np
from django.db import models
from django.utils import timezone

import sorterinput.models

class Controller(abc.ABC):

    @classmethod
    @abc.abstractmethod
    def get_sorted_chars(cls, charlist):
        """Get a list of char IDs, sorted from best to worst."""
        pass

    @classmethod
    @abc.abstractmethod
    def get_next_comparison(cls, charlist):
        """Retrieves the next pair of char ids to compare, or None"""
        pass

    @classmethod
    def register_comparison(cls, charlist, char1_id, char2_id, value):
        record = SortRecord()
        record.charlist = charlist
        record.char1 = sorterinput.models.Character.objects.get(id=char1_id)
        assert record.char1.characterlist == charlist
        record.char2 = sorterinput.models.Character.objects.get(id=char2_id)
        assert record.char2.characterlist == charlist
        record.value = value
        record.save()
        return record

    @classmethod
    @abc.abstractmethod
    def get_annotations(cls, charlist):
        """Returns an annotation for each character, if any, e.g. whether the
        character has been sorted or not. Returns a dict mapping character ID
        to annotation, or None if that character has no annotation."""
        pass


class InsertionSortController(Controller):

    @staticmethod
    def insertion_sort(charlist, characters=None):
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
                    return sorted_chars, compair
            sorted_chars.insert(high, character)
        return sorted_chars, None

    @classmethod
    def get_sorted_chars(cls, charlist):
        characters = charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        sorted_chars = cls.insertion_sort(charlist, characters)[0]
        sorted_char_set = set(sorted_chars)
        for char_id in characters:
            if char_id not in sorted_char_set:
                sorted_chars.append(char_id)
        return sorted_chars

    @classmethod
    def get_next_comparison(cls, charlist):
        return cls.insertion_sort(charlist)[1]

    @classmethod
    def get_annotations(cls, charlist):
        characters = charlist.character_set.all(
            ).order_by("id").values_list("id", flat=True)
        sorted_chars, compair = cls.insertion_sort(charlist, characters)
        sorted_char_set = set(sorted_chars)
        annotations = {
            char: None if char in sorted_char_set else "Unsorted"
            for char in characters}
        if compair is not None:
            annotations[compair[0]] = "Now Sorting"
        return annotations

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
    Q = math.log(10) / 400


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
            assert (t is None) or (timestamp > t)
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

    @classmethod
    def compute_ratings(cls, charlist, raw=False, interval=False):
        records = charlist.sortrecord_set.all().order_by("timestamp")
        char_ids = charlist.character_set.all().values_list("id", flat=True)
        rating_info = {
            char_id: (cls.DEFAULT_RATING, cls.DEFAULT_RD, None)
            for char_id in char_ids}
        for record in records:
            cls.process_record(record, rating_info)
        # Make rds decay to the present
        now = timezone.now()
        for char_id, (r, rd, ts) in rating_info.items():
            rating_info[char_id] = r, cls.rd_after_time(rd, ts, now), None
        if raw:
            return rating_info
        else:
            ratings = {}
            for char_id in char_ids:
                # Return rating - 2 * rd
                r, rd, _ = rating_info[char_id]
                ratings[char_id] = (
                    (r - 2 * rd) if not interval else (r - 2 * rd, r + 2 *rd))
            return ratings

    @classmethod
    def get_match_weight(cls, char_id, opponent_id, rating_info, last_matches):
        """How much do we want this match to occur? We'd like a match which
        will minimize char_id's rd while avoiding repeated matchups."""
        r, rd, _ = rating_info[char_id]
        r_other, rd_other, _ = rating_info[opponent_id]
        _, inv_dsquared, _, _ = cls.compute_values(r, rd, r_other, rd_other)
        last_match = last_matches.get((char_id, opponent_id), None)
        # TODO: isn't this always none?
        days_since_last = (
            cls.RD_RESET_TIME if last_match is None else
            min((timezone.now() - last_match.timestamp).total_seconds()
                / (3600 * 24),
                cls.RD_RESET_TIME))
        return days_since_last * inv_dsquared

    @classmethod
    def get_sorted_chars(cls, charlist):
        """Get a list of char IDs, sorted from best to worst."""
        ratings = cls.compute_ratings(charlist)
        return sorted(ratings, key=ratings.get, reverse=True)

    @classmethod
    @abc.abstractmethod
    def get_next_comparison(cls, charlist):
        """Retrieves the next pair of characters to compare, or None"""
        char_ids = charlist.character_set.all().values_list("id", flat=True)
        if len(char_ids) < 2:
            return None
        rating_info = cls.compute_ratings(charlist, raw=True)
        # Pick a random first character
        char_id = np.random.choice(char_ids)
        # Select their opponent:
        opponents = [opponent for opponent in char_ids if opponent != char_id]
        last_matches = SortRecord.get_last_matches(charlist)
        opponent_weights = np.array([cls.get_match_weight(
            char_id, opponent, rating_info, last_matches) for opponent in opponents])
        opponent_weights /= np.sum(opponent_weights)
        return char_id, np.random.choice(opponents, p=opponent_weights)

    @classmethod
    @abc.abstractmethod
    def get_annotations(cls, charlist):
        """Returns an annotation for each character, if any, e.g. whether the
        character has been sorted or not. Returns a dict mapping character ID
        to annotation, or None if that character has no annotation."""
        ratings = cls.compute_ratings(charlist, interval=False)
        return {i: int(r) for i, r in ratings.items()}


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
    value = models.IntegerField()

    @staticmethod
    def get_last_matches(charlist):
        """Returns a dict mapping (char1_id, char2_id) to the most recent match among
        the charlist's matches."""
        last_matches = {}
        sorted_records = charlist.sortrecord_set.all().order_by("timestamp")
        for record in sorted_records:
            last_matches[(record.char1.id, record.char2.id)] = record
            last_matches[(record.char2.id, record.char1.id)] = record
        return last_matches

    def __str__(self):
        return "{} vs {}".format(self.char1, self.char2)

CONTROLLER_TYPES = {
    "InsertionSortController": InsertionSortController,
    "GlickoRatingController": GlickoRatingController,
}
