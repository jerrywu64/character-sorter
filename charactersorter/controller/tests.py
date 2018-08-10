import math
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from sorterinput.models import CharacterList, Character
from .models import InsertionSortController, GlickoRatingController, SortRecord

class ControllerTest(TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.charlist = None
        self.characters = None
        self.controller = None

    def setUp(self):
        self.user = User()
        self.user.save()

        # one charlist
        self.charlist = CharacterList()
        self.charlist.owner = self.user
        self.charlist.title = "testtitle"
        self.charlist.save()

        # 12 characters over 2 fandoms
        self.characters = []
        # Desired order mapping the character number to their ranking.
        # Converted to ID below.
        # Desried order is character ID mapping to their ranking. Ties allowed.
        self.raw_order = {
            8: 1,
            0: 2,
            6: 3, 11: 3,
            9: 4,
            10: 5,
            2: 6, 1: 6, 5: 6,
            7: 7,
            3: 8,
            4: 9,
        }
        self.desired_order = {}  # maps character ID to their rank
        for i, _ in enumerate(self.raw_order):
            char = Character()
            char.characterlist = self.charlist
            char.name = "char{}".format(i)
            char.fandom = "fandom{}".format(i % 2)
            self.characters.append(char)
            char.save()
            self.desired_order[char.id] = self.raw_order[i]

    def register_comparison(self, char1_id, char2_id, result=None, ts=None):
        """Registers a comparison between the two specified characters. The
        result of the match is according to the desired order, unless a result
        is specified. If the timestamp is specified, it is used for the
        match."""
        if result is None:
            if self.desired_order[char1_id] < self.desired_order[char2_id]:
                result = 1
            elif self.desired_order[char1_id] == self.desired_order[char2_id]:
                result = 0
            else:
                result = -1
        rec = self.controller.register_comparison(
            self.charlist, char1_id, char2_id, result)
        if ts is not None:
            rec.timestamp = ts
            rec.save()

    def assertSorted(self):
        """Verifies that the characters are sorted."""
        sorted_chars = self.controller.get_sorted_chars(self.charlist)
        self.assertEqual(len(sorted_chars), len(self.desired_order))
        # Verify that each sorted char is at least as good as the next
        for char1_id, char2_id in zip(sorted_chars, sorted_chars[1:]):
            self.assertLessEqual(
                self.desired_order[char1_id], self.desired_order[char2_id],
                "Got incorrect ranking {}".format(sorted_chars))


class InsertionSortControllerTest(ControllerTest):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.controller = InsertionSortController()

    def test_sort(self):
        # Compute number of comparisons for efficiency
        comparisons_left = 0
        for i, _ in enumerate(self.desired_order):
            comparisons_left += math.ceil(math.log(i + 1) / math.log(2))
        while self.controller.get_next_comparison(self.charlist) is not None:
            self.assertGreaterEqual(
                comparisons_left, 0,
                msg="Insertion sort was too inefficient!")
            comparisons_left -= 1
            char1, char2 = self.controller.get_next_comparison(self.charlist)
            self.register_comparison(char1, char2)
        self.assertSorted()

class GlickoRatingControllerTest(ControllerTest):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.controller = GlickoRatingController()

    def test_rating_monotonicity(self):
        """First, play one match for each player. Then, play a number of
        matches in quick succession. Verify that after each match, the winner's
        raw rating increases, the loser's raw rating decreases, and both RDs
        decrease."""
        # 20 randomly generated matches. First two numbers are raw character
        # numbers of the match contestants. Third number is the result.
        matches = [
            (5, 3, -1), (6, 10, 1), (11, 2, -1), (7, 6, 1), (10, 8, -1),
            (10, 4, 1), (6, 7, 1), (6, 1, 0), (11, 4, -1), (8, 3, -1),
            (9, 8, 0), (11, 9, 0), (4, 2, 1), (9, 11, -1), (10, 3, 1),
            (0, 7, -1), (1, 11, -1), (0, 8, 1), (6, 3, -1), (3, 8, 1)]

        next_ts = timezone.now() - datetime.timedelta(days=1)
        char_ids = list(self.desired_order)
        pivot = len(char_ids) // 2
        initial_matches = zip(char_ids[:pivot], char_ids[pivot:])
        # First, make sure everyone has a match
        for char1_id, char2_id in initial_matches:
            self.register_comparison(char1_id, char2_id, ts=next_ts)
            next_ts += datetime.timedelta(milliseconds=1)

        # Check each of the matches
        for char1_raw, char2_raw, res in matches:
            char1_id = self.characters[char1_raw].id
            char2_id = self.characters[char2_raw].id
            rating_info = self.controller.compute_ratings(
                self.charlist, raw=True)
            old_r_1, old_rd_1, _ = rating_info[char1_id]
            old_r_2, old_rd_2, _ = rating_info[char2_id]
            self.register_comparison(
                char1_id, char2_id, result=res, ts=next_ts)
            next_ts += datetime.timedelta(milliseconds=1)
            rating_info = self.controller.compute_ratings(
                self.charlist, raw=True)
            new_r_1, new_rd_1, _ = rating_info[char1_id]
            new_r_2, new_rd_2, _ = rating_info[char2_id]
            if res == 1:
                self.assertGreater(new_r_1, old_r_1)
                self.assertLess(new_r_2, old_r_2)
            elif res == -1:
                self.assertLess(new_r_1, old_r_1)
                self.assertGreater(new_r_2, old_r_2)
            elif old_r_1 < old_r_2:
                self.assertGreater(new_r_1, old_r_1)
                self.assertLess(new_r_2, old_r_2)
            elif old_r_1 > old_r_2:
                self.assertLess(new_r_1, old_r_1)
                self.assertGreater(new_r_2, old_r_2)
            else:
                self.assertEqual(new_r_1, old_r_1)
                self.assertEqual(new_r_2, old_r_2)
            self.assertLess(new_rd_1, old_rd_1)
            self.assertLess(new_rd_2, old_rd_2)

    def test_rating_convergence(self):
        """Ensure that after a sufficiently large number of matches, the
        ratings produce the correct order of characters."""
        for char1 in self.characters:
            for char2 in self.characters:
                self.register_comparison(char1.id, char2.id)
        self.assertSorted()

    def test_match_weight_finds_unmade_match(self):
        """Matches one character against all but one opponent, then verifies
        that the match weight for the last opponent is the highest."""
        char1_id = self.characters[0].id
        for char2 in self.characters[1:-1]:
            self.register_comparison(char1_id, char2.id)
        rating_info = self.controller.compute_ratings(self.charlist, raw=True)
        last_matches = SortRecord.get_last_matches(self.charlist)
        weights = [
            self.controller.get_match_weight(
                char1_id, char2.id, rating_info, last_matches)
            for char2 in self.characters[1:]]
        for weight in weights[:-1]:
            self.assertLess(weight, weights[-1])

    def test_char_weight_finds_unused_char(self):
        """Matches every character but one, then verifies that the character
        weight for the last character is the highest."""
        for char in self.characters[1:-1]:
            self.register_comparison(self.characters[0].id, char.id)
        rating_info = self.controller.compute_ratings(self.charlist, raw=True)
        char_ids = [char.id for char in self.characters]
        weights = self.controller.get_char_weights(char_ids, rating_info)
        for weight in weights[:-1]:
            self.assertLess(weight, weights[-1])
