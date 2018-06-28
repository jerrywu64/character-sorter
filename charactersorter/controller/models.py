import abc
from django.db import models

import sorterinput.models

class Controller(abc.ABC):
    @abc.abstractmethod
    def get_char_ranks(self):
        """Get a dict mapping char id to char rank."""
        pass

    @abc.abstractmethod
    def is_ascending(self):
        """Return True if a low rank is best."""
        pass

    @abc.abstractmethod
    def get_next_comparison(self):
        """Retrieves the next pair of characters to compare, or None"""
        pass

    @abc.abstractmethod
    def register_comparison(self, char1, char2, value):
        """Registers a comparison between two characters. 1 means char1 wins,
        -1 means char2 wins, 0 means draw."""
        pass


class InsertionSortController(models.Model, Controller):
    charlist = models.ForeignKey(
        sorterinput.models.CharacterList, on_delete=models.CASCADE)

    def insertion_sort(self, characters=None):
        characters = characters or self.charlist.character_set.all(
            ).sort_by("id").values_list("id")
        records = self.insertionsortrecord_set.all().values_list(
            "char1__id", "char2__id", "value")
        record_dict = {}
        for char1, char2, value in records:
            # ensure that char1 is always greater
            if char1 < char2:
                temp = char1
                char1 = char2
                char2 = temp
            record_dict[(char1, char2)] = value
        sorted_chars = []
        for character in characters:
            # Binary insertion sort to insert character into
            # the sorted list of chars. Note that the list
            # of sorted chars necessarily contains ids less than
            # the new one.
            low = 0
            high = len(sorted_chars)
            while low < high:
                mid = (low + high) / 2
                compair = (character.id, sorted_chars[mid])
                if compair in record_dict:
                    value = record_dict[compair]
                    if value > 0:
                        high = mid
                    else:
                        low = mid + 1
                else:
                    return sorted_chars, compair
            sorted_chars.insert(low, character)
        return sorted_chars, None

    def is_ascending(self):
        return True

    def get_char_ranks(self):
        characters = self.charlist.character_set.all(
            ).sort_by("id").values_list("id")
        sorted_chars = self.insertion_sort(characters)[0]
        return {
            char_id: sorted_chars.index(char_id) if char_id in sorted_chars
                     else i
            for i, char_id in enumerate(characters)}

    def get_next_comparison(self):
        return self.insertion_sort()[1]

    def register_comparison(self, char1, char2, value):
        record = InsertionSortRecord()
        record.controller = self
        record.char1 = char1
        record.char2 = char2
        record.value = value
        record.save()

class InsertionSortRecord(models.Model):
    controller = models.ForeignKey(
        InsertionSortController, on_delete=models.CASCADE)
    char1 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE)
    char2 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE)
    value = models.IntegerField()
