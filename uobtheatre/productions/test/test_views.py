import pytest 

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
)

@pytest.mark.django_db
def test_production_view_get(api_client):

    # Create a fake production
    prod = ProductionFactory()

    # Get the productions endpoint
    response = api_client.get(
        "/api/v1/productions/"
    )

    # Assert it returns 200 and what is expected
    assert response.status_code == 200 
    assert response.json() == {
        'count': 1,
        'next': None,
        'previous': None,
        'results': [
            {
                'id': prod.id,
                'name': prod.name,
                'society': {
                    'id': prod.society.id,
                    'name': prod.society.name 
                }
            }
        ],
    }

