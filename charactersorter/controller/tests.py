from django.test import TestCase
from django.contrib.auth.models import User

from sorterinput.models import CharacterList, Character
from .models import InsertionSortController

class InsertionSortControllerTest(TestCase):
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

        # 6 characters over 2 fandoms
        self.characters = []
        for i in range(6):
            char = Character()
            char.characterlist = self.charlist
            char.name = "char{}".format(i)
            char.fandom = "fandom{}".format(i % 2)
            self.characters.append(char)
            char.save()

        self.controller = InsertionSortController

    def test_sort(self):
        desired_order = [5, 2, 3, 1, 6, 4]
        comparisons_left = 11  # 0 + 1 + 2 + 2 + 3 + 3
        while self.controller.get_next_comparison(self.charlist) is not None:
            self.assertGreaterEqual(
                comparisons_left, 0,
                msg="Insertion sort was too inefficient!")
            char1, char2 = self.controller.get_next_comparison(self.charlist)
            self.controller.register_comparison(
                self.charlist, char1, char2,
                desired_order.index(char1) < desired_order.index(char2))
        sorted_chars = self.controller.get_sorted_chars(self.charlist)
        for char_id, sorted_id in zip(desired_order, sorted_chars):
            self.assertEqual(char_id, sorted_id)