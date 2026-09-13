from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

import controller.models
from .models import Character, CharacterList
from .paste import FIELD_LIMIT, NO_FANDOM, parse_paste, new_entries

class ControllerTypeIntegrityTest(TestCase):
    def test_controller_type_integrity(self):
        for _, controller_type in CharacterList.CONTROLLER_CHOICES:
            self.assertIn(controller_type, controller.models.CONTROLLER_TYPES)


class PasteParseTest(TestCase):
    def parse(self, text):
        entries, skipped = parse_paste(text)
        return [tuple(entry) for entry in entries], skipped

    def test_inline_fandom(self):
        self.assertEqual(
            self.parse("Sailor Neptune (Sailor Moon)")[0],
            [("Sailor Neptune", "Sailor Moon")])

    def test_header_supplies_fandom_for_bare_names(self):
        entries, skipped = self.parse(
            "[Madoka Magica]\n Homura Akemi \n\nMami Tomoe\n")
        self.assertEqual(entries, [("Homura Akemi", "Madoka Magica"),
                                   ("Mami Tomoe", "Madoka Magica")])
        self.assertEqual(skipped, [])

    def test_inline_fandom_overrides_the_header_for_one_line_only(self):
        """The override is not sticky: the header still applies below it."""
        self.assertEqual(
            self.parse("[Trigun]\nVash\nUsagi (Sailor Moon)\nWolfwood")[0],
            [("Vash", "Trigun"), ("Usagi", "Sailor Moon"),
             ("Wolfwood", "Trigun")])

    def test_tab_separates_a_spreadsheet_paste(self):
        self.assertEqual(
            self.parse("Vash\tTrigun\nUsagi (x)\tSailor Moon")[0],
            [("Vash", "Trigun"), ("Usagi (x)", "Sailor Moon")])

    def test_only_the_last_parens_are_the_fandom(self):
        self.assertEqual(
            self.parse("Ranma (cursed) (Ranma 1/2)")[0],
            [("Ranma (cursed)", "Ranma 1/2")])

    def test_empty_parens_fall_back_to_the_header(self):
        self.assertEqual(
            self.parse("[Trigun]\nVash ()")[0], [("Vash", "Trigun")])

    def test_empty_brackets_clear_the_header(self):
        entries, skipped = self.parse("[Trigun]\n[]\nVash")
        self.assertEqual(entries, [])
        self.assertEqual([line.reason for line in skipped], [NO_FANDOM])

    def test_a_bare_name_with_no_header_is_skipped(self):
        """The model requires a fandom, so there is nothing to create."""
        entries, skipped = self.parse("Vash")
        self.assertEqual(entries, [])
        self.assertEqual(skipped[0].text, "Vash")

    def test_an_overlong_field_is_skipped(self):
        long_name = "V" * (FIELD_LIMIT + 1)
        entries, skipped = self.parse(
            "{} (Trigun)\nVash ({})".format(long_name, long_name))
        self.assertEqual(entries, [])
        self.assertEqual(len(skipped), 2)

    def test_new_entries_drops_repeats_and_existing_pairs(self):
        """Matching is case-insensitive on name and fandom together, so a
        shared name across two fandoms still gets both."""
        entries, _ = parse_paste(
            "Vash (Trigun)\nvash (trigun)\nVash (Elsewhere)\nMeryl (Trigun)")
        unseen = new_entries(entries, [("meryl", "TRIGUN")])
        self.assertEqual([tuple(entry) for entry in unseen],
                         [("Vash", "Trigun"), ("Vash", "Elsewhere")])


class PasteAddTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", password="pw")
        self.charlist = CharacterList.objects.create(
            owner=self.user, title="Mine")
        self.client.force_login(self.user)

    def test_paste_creates_characters_in_the_urls_list(self):
        Character.objects.create(
            characterlist=self.charlist, name="Vash", fandom="Trigun")
        other_list = CharacterList.objects.create(
            owner=self.user, title="Other")
        response = self.client.post(
            reverse("sorterinput:editlist", args=(self.charlist.id,)),
            {"paste": "[Trigun]\nVash\nMeryl\nWolfwood (Trigun)\n[]\nOrphan"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            sorted(self.charlist.character_set.values_list("name", flat=True)),
            ["Meryl", "Vash", "Wolfwood"])
        self.assertEqual(other_list.character_set.count(), 0)



class PostBodyAuthorizationTest(TestCase):
    """Object IDs arriving in the POST body must be scoped to the requester,
    not trusted. requires_list_owner only validates the URL's list_id. Each
    test also exercises the honest path in the same request, so that
    over-restricting a queryset fails rather than passing quietly."""

    def setUp(self):
        self.victim = User.objects.create_user("victim", password="pw")
        self.attacker = User.objects.create_user("attacker", password="pw")
        self.their_list = CharacterList.objects.create(
            owner=self.victim, title="Theirs")
        self.their_char = Character.objects.create(
            characterlist=self.their_list, name="Alice", fandom="Wonderland")
        self.my_list = CharacterList.objects.create(
            owner=self.attacker, title="Mine")
        self.client.force_login(self.attacker)

    def test_editlist_ignores_foreign_character_ids(self):
        """A tampered form-N-id neither renames nor deletes a character in
        someone else's list, while the requester's own row still saves."""
        my_char = Character.objects.create(
            characterlist=self.my_list, name="Bob", fandom="Elsewhere")
        response = self.client.post(
            reverse("sorterinput:editlist", args=(self.my_list.id,)), {
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "2",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(self.their_char.id),
                "form-0-name": "Pwned",
                "form-0-fandom": "Pwned",
                "form-0-DELETE": "on",
                "form-1-id": str(my_char.id),
                "form-1-name": "Renamed",
                "form-1-fandom": "Elsewhere",
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Character.objects.filter(pk=self.their_char.pk).exists())
        self.their_char.refresh_from_db()
        self.assertEqual(self.their_char.name, "Alice")
        my_char.refresh_from_db()
        self.assertEqual(my_char.name, "Renamed")

    def test_add_forms_ignore_client_supplied_ownership(self):
        """characterlist and owner come from the URL and request.user, so
        POSTing them has no effect on where the new object lands."""
        self.client.post(
            reverse("sorterinput:editlist", args=(self.my_list.id,)),
            {"characterlist": str(self.their_list.id),
             "name": "Mallory", "fandom": "Nowhere"})
        self.assertEqual(self.their_list.character_set.count(), 1)
        self.assertEqual(
            Character.objects.get(name="Mallory").characterlist, self.my_list)

        self.client.post(
            reverse("sorterinput:editcharlists"),
            {"owner": str(self.victim.id), "title": "Gift",
             "controller_type": CharacterList.INSERTION})
        self.assertEqual(
            CharacterList.objects.filter(owner=self.victim).count(), 1)
        self.assertEqual(
            CharacterList.objects.get(title="Gift").owner, self.attacker)

    def test_undo_rejects_sortrecord_from_another_list(self):
        their_record = self.make_record(self.their_list, "Wonderland")
        response = self.client.post(
            reverse("sorterinput:undo", args=(self.my_list.id,)),
            {"last": str(their_record.id)})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(controller.models.SortRecord.objects.filter(
            pk=their_record.pk).exists())

        my_record = self.make_record(self.my_list, "Elsewhere")
        response = self.client.post(
            reverse("sorterinput:undo", args=(self.my_list.id,)),
            {"last": str(my_record.id)})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(controller.models.SortRecord.objects.filter(
            pk=my_record.pk).exists())

    def test_sortlist_rejects_a_character_from_another_list(self):
        """register_comparison must not accept a foreign char id: the record
        would render the victim's name back on the attacker's sort page."""
        my_char = Character.objects.create(
            characterlist=self.my_list, name="Bob", fandom="Elsewhere")
        with self.assertRaises(Character.DoesNotExist):
            self.client.post(
                reverse("sorterinput:sortlist", args=(self.my_list.id,)),
                {"char1": str(my_char.id), "char2": str(self.their_char.id),
                 "sort": "1"})
        self.assertEqual(controller.models.SortRecord.objects.count(), 0)

    def make_record(self, charlist, fandom):
        chars = [Character.objects.create(
            characterlist=charlist, name=name, fandom=fandom)
                 for name in ("Carol", "Dave")]
        return controller.models.SortRecord.objects.create(
            charlist=charlist, char1=chars[0], char2=chars[1], value=1)
