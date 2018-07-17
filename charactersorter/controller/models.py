import abc
from django.db import models

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
        """Retrieves the next pair of characters to compare, or None"""
        pass

    @classmethod
    @abc.abstractmethod
    def register_comparison(cls, charlist, char1_id, char2_id, value):
        """Registers a comparison between two characters. 1 means char1 wins,
        -1 means char2 wins, 0 means draw."""
        pass

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
        records = charlist.sortrecord_set.all().values_list(
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
    def register_comparison(cls, charlist, char1_id, char2_id, value):
        record = SortRecord()
        record.controller = charlist
        record.char1 = sorterinput.models.Character.objects.get(id=char1_id)
        record.char2 = sorterinput.models.Character.objects.get(id=char2_id)
        record.value = value
        record.save()

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


class SortRecord(models.Model):
    controller = models.ForeignKey(
        sorterinput.models.CharacterList, on_delete=models.CASCADE)
    char1 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE,
        related_name="sortrecord1")
    char2 = models.ForeignKey(
        sorterinput.models.Character, on_delete=models.CASCADE,
        related_name="sortrecord2")
    timestamp = models.DateTimeField(auto_now_add=True)
    value = models.IntegerField()

    def __str__(self):
        return "{} vs {}".format(self.char1, self.char2)

CONTROLLER_TYPES = {
    "InsertionSortController": InsertionSortController
}
