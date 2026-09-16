import datetime
import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime

import controller.models
from .models import Character, CharacterList

def body_of(response):
    return json.loads(response.content.decode("utf-8"))


class ApiTestCase(TestCase):

    def setUp(self):
        self.victim = User.objects.create_user("victim", password="pw")
        self.attacker = User.objects.create_user("attacker", password="pw")
        self.theirs = self.make_list(self.victim)
        self.mine = self.make_list(self.attacker)
        self.client.force_login(self.attacker)

    def make_list(self, owner):
        """A list with two characters and one comparison between them."""
        charlist = CharacterList.objects.create(
            owner=owner, title="List of {}".format(owner.username),
            controller_type=CharacterList.GLICKO)
        charlist.chars = [
            Character.objects.create(
                characterlist=charlist, name=name, fandom="Fandom")
            for name in ("Alice", "Bob")]
        charlist.record = controller.models.SortRecord.objects.create(
            charlist=charlist, char1=charlist.chars[0],
            char2=charlist.chars[1], value=1)
        return charlist

    def request(self, method, url, body=None, client=None):
        client = client or self.client
        if body is None:
            return getattr(client, method)(url)
        return getattr(client, method)(
            url, json.dumps(body), content_type="application/json")


class AuthenticationTest(ApiTestCase):
    """api_view gates every endpoint on the session, and because it is not
    csrf_exempt, Django's CSRF protection still covers the writes."""

    def test_anonymous_requests_are_refused(self):
        self.client.logout()
        for method, url, body in (
                ("get", "/api/lists", None),
                ("post", "/api/lists",
                 {"title": "T", "controller_type": "IS"}),
                ("get", "/api/lists/{}".format(self.mine.id), None),
                # Authentication is checked before the method, so even a
                # disallowed method answers in JSON rather than an HTML 405.
                ("delete", "/api/lists", None)):
            response = self.request(method, url, body)
            self.assertEqual(
                response.status_code, 401,
                "{} {} was not refused".format(method.upper(), url))
            # A JSON error, not a redirect to the HTML login page.
            self.assertIn("error", body_of(response))
        # Positive control: the same three requests succeed once logged in.
        self.client.force_login(self.attacker)
        for method, url, body, expected in (
                ("get", "/api/lists", None, 200),
                ("post", "/api/lists", {"title": "T",
                                        "controller_type": "IS"}, 201),
                ("get", "/api/lists/{}".format(self.mine.id), None, 200)):
            self.assertEqual(
                self.request(method, url, body).status_code, expected,
                "{} {} failed for its owner".format(method.upper(), url))

    def test_a_write_without_a_csrf_token_is_refused(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.attacker)
        body = {"title": "T", "controller_type": "IS"}
        self.assertEqual(
            self.request("post", "/api/lists", body, strict).status_code, 403)
        # Positive control: the same client succeeds once it sends the header
        # a browser client would, so the 403 is about CSRF alone.
        strict.get("/login/")
        response = strict.post(
            "/api/lists", json.dumps(body), content_type="application/json",
            HTTP_X_CSRFTOKEN=strict.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 201)


class ListOwnershipTest(ApiTestCase):
    """owned_list is the API's whole authorization story, so this walks every
    list-scoped route rather than re-testing the helper once per endpoint."""

    ENDPOINTS = (
        ("get", "/api/lists/{list}", None, 200),
        ("patch", "/api/lists/{list}", {"title": "Renamed"}, 200),
        ("get", "/api/lists/{list}/characters", None, 200),
        ("post", "/api/lists/{list}/characters",
         {"name": "New", "fandom": "F"}, 201),
        ("patch", "/api/lists/{list}/characters/{char}",
         {"name": "Renamed"}, 200),
        ("get", "/api/lists/{list}/characters/{char}/history", None, 200),
        ("delete", "/api/lists/{list}/characters/{char}", None, 204),
        ("get", "/api/lists/{list}/next", None, 200),
        ("post", "/api/lists/{list}/comparisons", "comparison", 201),
        ("delete", "/api/lists/{list}/comparisons/{record}", None, 204),
        ("get", "/api/lists/{list}/graph", None, 200),
        ("delete", "/api/lists/{list}", None, 204),
    )

    def fill(self, template, charlist):
        return template.format(
            list=charlist.id, char=charlist.chars[0].id,
            record=charlist.record.id)

    def body_for(self, body, charlist):
        if body != "comparison":
            return body
        return {"char1": charlist.chars[0].id,
                "char2": charlist.chars[1].id, "value": 1}

    def test_every_route_refuses_a_list_owned_by_someone_else(self):
        for method, template, body, expected in self.ENDPOINTS:
            self.assertEqual(
                self.request(method, self.fill(template, self.theirs),
                             self.body_for(body, self.theirs)).status_code,
                404,
                "{} {} reached another user's list".format(
                    method.upper(), template))
            # Positive control on a fresh list of the attacker's own, so an
            # over-restrictive filter fails here instead of passing quietly.
            mine = self.make_list(self.attacker)
            self.assertEqual(
                self.request(method, self.fill(template, mine),
                             self.body_for(body, mine)).status_code, expected,
                "{} {} failed for its owner".format(method.upper(), template))
        self.assertEqual(self.theirs.character_set.count(), 2)
        self.assertEqual(self.theirs.sortrecord_set.count(), 1)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.title, "List of victim")


class NestedLookupTest(ApiTestCase):
    """A character or record id is looked up through the list in the URL, so
    one belonging to another list is unreachable even from a list I own."""

    def test_foreign_child_ids_are_not_reachable_through_my_own_list(self):
        for method, template, body in (
                ("patch", "/api/lists/{}/characters/{}", {"name": "Pwned"}),
                ("get", "/api/lists/{}/characters/{}/history", None),
                ("delete", "/api/lists/{}/characters/{}", None)):
            self.assertEqual(
                self.request(method,
                             template.format(self.mine.id,
                                             self.theirs.chars[0].id),
                             body).status_code, 404)
        self.assertEqual(
            self.request("delete", "/api/lists/{}/comparisons/{}".format(
                self.mine.id, self.theirs.record.id)).status_code, 404)
        self.theirs.chars[0].refresh_from_db()
        self.assertEqual(self.theirs.chars[0].name, "Alice")
        self.assertEqual(self.theirs.sortrecord_set.count(), 1)
        # Positive control: my own child ids under my own list still work.
        self.assertEqual(
            self.request("patch", "/api/lists/{}/characters/{}".format(
                self.mine.id, self.mine.chars[0].id),
                {"name": "Renamed"}).status_code, 200)
        self.assertEqual(
            self.request("delete", "/api/lists/{}/comparisons/{}".format(
                self.mine.id, self.mine.record.id)).status_code, 204)


class OwnershipFieldsTest(ApiTestCase):
    """bind_form drops keys the ModelForm does not declare, so owner and
    characterlist have nothing to bind to."""

    def test_ownership_fields_in_the_body_are_ignored(self):
        response = self.request("post", "/api/lists", {
            "owner": self.victim.id, "title": "Gift",
            "controller_type": CharacterList.INSERTION})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            CharacterList.objects.get(title="Gift").owner, self.attacker)

        response = self.request(
            "post", "/api/lists/{}/characters".format(self.mine.id),
            {"characterlist": self.theirs.id,
             "name": "Mallory", "fandom": "Nowhere"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Character.objects.get(name="Mallory").characterlist, self.mine)
        self.assertEqual(self.theirs.character_set.count(), 2)


class ComparisonTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.url = "/api/lists/{}/comparisons".format(self.mine.id)

    def test_a_comparison_cannot_name_a_character_from_another_list(self):
        """register_comparison guards this with an assert, which python -O
        strips, so the ids are resolved through the list first."""
        response = self.request("post", self.url, {
            "char1": self.mine.chars[0].id,
            "char2": self.theirs.chars[0].id, "value": 1})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.mine.sortrecord_set.count(), 1)
        # Positive control: two of my own characters record fine.
        response = self.request("post", self.url, {
            "char1": self.mine.chars[0].id,
            "char2": self.mine.chars[1].id, "value": 1})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.mine.sortrecord_set.count(), 2)

    def test_a_client_supplied_timestamp_is_stored(self):
        stamp = "2018-07-12T00:01:02+00:00"
        response = self.request("post", self.url, {
            "char1": self.mine.chars[0].id, "char2": self.mine.chars[1].id,
            "value": 1, "timestamp": stamp})
        self.assertEqual(response.status_code, 201)
        record = controller.models.SortRecord.objects.get(
            pk=body_of(response)["id"])
        self.assertEqual(record.timestamp, parse_datetime(stamp))

    def test_an_invalid_comparison_is_refused_and_stores_nothing(self):
        """The record used to be saved before the timestamp was validated, so
        a 400 still left one behind for a retrying client to duplicate. The
        value and timestamp bounds matter because out-of-range input does not
        just produce bad rankings -- it makes compute_ratings raise, which
        500s the API and the HTML pages alike for that list."""
        future = (timezone.now() + datetime.timedelta(days=400)).isoformat()
        for label, override in (
                ("naive timestamp", {"timestamp": "2018-07-12T00:01:02"}),
                ("unparseable timestamp", {"timestamp": "yesterday"}),
                ("future timestamp", {"timestamp": future}),
                ("out-of-range value", {"value": 1000000}),
                ("non-numeric value", {"value": "win"}),
                ("self-match", {"char2": self.mine.chars[0].id})):
            body = {"char1": self.mine.chars[0].id,
                    "char2": self.mine.chars[1].id, "value": 1}
            body.update(override)
            self.assertEqual(
                self.request("post", self.url, body).status_code, 400, label)
            self.assertEqual(self.mine.sortrecord_set.count(), 1, label)
        # The list is still rankable: an accepted bad record would raise here
        # rather than merely skew the numbers.
        self.assertEqual(self.request(
            "get", "/api/lists/{}".format(self.mine.id)).status_code, 200)
        # Positive control: a well-formed body is still accepted, so the
        # guards above are not simply refusing everything.
        self.assertEqual(self.request("post", self.url, {
            "char1": self.mine.chars[0].id, "char2": self.mine.chars[1].id,
            "value": 0}).status_code, 201)
        self.assertEqual(self.mine.sortrecord_set.count(), 2)


class RatingHistoryTest(ApiTestCase):
    """The history endpoint replays the comparisons compute_ratings replays,
    recording a point for each one the character took part in."""

    def url_for(self, charlist, char):
        return "/api/lists/{}/characters/{}/history".format(
            charlist.id, char.id)

    def history_of(self, charlist, char):
        return body_of(self.request("get", self.url_for(charlist, char)))

    def add_match(self, charlist, winner, loser, days_later):
        """A comparison the winner won, stamped after the setUp one."""
        record = controller.models.SortRecord.objects.create(
            charlist=charlist, char1=winner, char2=loser, value=1)
        # auto_now_add means the timestamp can only be set after the fact.
        record.timestamp = charlist.record.timestamp + datetime.timedelta(
            days=days_later)
        record.save()
        return record

    def test_only_this_characters_matches_appear_and_the_sign_follows_it(self):
        alice, _ = self.mine.chars
        carol = Character.objects.create(
            characterlist=self.mine, name="Carol", fandom="Fandom")
        # setUp has Alice beating Bob; Carol then beats Alice.
        self.add_match(self.mine, carol, alice, days_later=1)

        history = self.history_of(self.mine, alice)["history"]
        self.assertEqual(
            [point["opponent"]["name"] for point in history], ["Bob", "Carol"])
        # Alice was char1 in the first and char2 in the second.
        self.assertEqual([point["value"] for point in history], [1, -1])

    def test_the_reported_pair_is_raw_not_the_rankings_annotation(self):
        alice, _ = self.mine.chars
        body = self.history_of(self.mine, alice)
        ranked = body_of(self.request(
            "get", "/api/lists/{}".format(self.mine.id)))
        by_id = {char["id"]: char for char in ranked["characters"]}
        self.assertAlmostEqual(
            body["rating"] - 2 * body["rd"],
            by_id[alice.id]["annotation"], delta=1)

    def test_a_character_with_no_matches_has_an_empty_history(self):
        loner = Character.objects.create(
            characterlist=self.mine, name="Loner", fandom="Fandom")
        body = self.history_of(self.mine, loner)
        self.assertEqual(body["history"], [])
        self.assertEqual(
            body["rating"],
            controller.models.GlickoRatingController.DEFAULT_RATING)

    def test_tied_timestamps_replay_in_a_stable_order(self):
        alice, bob = self.mine.chars
        carol = Character.objects.create(
            characterlist=self.mine, name="Carol", fandom="Fandom")
        tie = self.mine.record.timestamp + datetime.timedelta(days=1)
        for winner, loser in ((carol, alice), (alice, bob)):
            record = controller.models.SortRecord.objects.create(
                charlist=self.mine, char1=winner, char2=loser, value=1)
            record.timestamp = tie
            record.save()

        body = self.history_of(self.mine, alice)
        self.assertEqual(
            body["history"], self.history_of(self.mine, alice)["history"])
        # Only rd decays, so the last point's rating is the reported one.
        self.assertEqual(body["history"][-1]["rating"], body["rating"])

    def test_an_insertion_sort_list_has_no_rating_history(self):
        charlist = CharacterList.objects.create(
            owner=self.attacker, title="Unrated",
            controller_type=CharacterList.INSERTION)
        char = Character.objects.create(
            characterlist=charlist, name="Alice", fandom="Fandom")
        self.assertEqual(
            self.request("get", self.url_for(charlist, char)).status_code, 404)


class FocusTest(ApiTestCase):
    """?focus= pins char1 without any server-side state; match_weight is what
    lets a client decide the run has stopped paying."""

    def setUp(self):
        super().setUp()
        self.third = Character.objects.create(
            characterlist=self.mine, name="Carol", fandom="Fandom")

    def next_url(self, charlist, focus=None):
        url = "/api/lists/{}/next".format(charlist.id)
        return url if focus is None else "{}?focus={}".format(url, focus)

    def test_focus_pins_char1_over_repeated_samples(self):
        for _ in range(8):
            body = body_of(self.client.get(
                self.next_url(self.mine, self.third.id)))
            self.assertEqual(body["char1"]["id"], self.third.id)
            self.assertNotEqual(body["char2"]["id"], self.third.id)

    def test_a_character_from_another_list_is_refused(self):
        response = self.client.get(
            self.next_url(self.mine, self.theirs.chars[0].id))
        self.assertEqual(response.status_code, 404)

    def test_a_malformed_focus_is_refused(self):
        response = self.client.get(self.next_url(self.mine, "Carol"))
        self.assertEqual(response.status_code, 400)

    def test_match_weight_is_reported_and_absent_focus_still_samples(self):
        body = body_of(self.client.get(self.next_url(self.mine)))
        self.assertGreater(body["match_weight"], 0)

    def test_an_insertion_sort_list_reports_no_weight_and_ignores_focus(self):
        charlist = CharacterList.objects.create(
            owner=self.attacker, title="Insertion",
            controller_type=CharacterList.INSERTION)
        chars = [Character.objects.create(
            characterlist=charlist, name=name, fandom="Fandom")
            for name in ("Alice", "Bob", "Carol")]
        body = body_of(self.client.get(self.next_url(charlist, chars[2].id)))
        self.assertIsNone(body["match_weight"])
        self.assertFalse(body["done"])
