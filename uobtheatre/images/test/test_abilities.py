from unittest.mock import patch

import pytest

from uobtheatre.images.abilities import UploadImage
from uobtheatre.productions.abilities import AddProduction, EditProduction
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.django_db
@pytest.mark.parametrize(
    "can_add_production,can_edit_production,expected",
    [
        (False, False, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_image_upload_ability(can_add_production, can_edit_production, expected):
    user = UserFactory()

    with patch.object(
        AddProduction, "user_has", return_value=can_add_production
    ), patch.object(EditProduction, "user_has", return_value=can_edit_production):
        assert UploadImage.user_has(user) is expected
