from django.test import TestCase

import controller.models
from .models import CharacterList

class ControllerTypeIntegrityTest(TestCase):
    def test_controller_type_integrity(self):
        for _, controller_type in CharacterList.CONTROLLER_CHOICES:
            self.assertIn(controller_type, controller.models.CONTROLLER_TYPES)
