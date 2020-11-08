import pytest 

from uobtheatre.productions.test.factories import (
    ProductionFactory,
    SocietyFactory,
)

@pytest.mark.django_db
def test_production_view_get(api_client):

    # Create a fake production
    prod1 = ProductionFactory()
    prod2 = ProductionFactory()

    # Get the productions endpoint
    response = api_client.get(
        "/api/v1/productions/"
    )

    # Assert it returns 200 and what is expected
    assert response.status_code == 200 
    assert response.json() == {
        'count': 2,
        'next': None,
        'previous': None,
        'results': [
            {
                'id': prod1.id,
                'name': prod1.name,
                'society': {
                    'id': prod1.society.id,
                    'name': prod1.society.name 
                }
            },
            {
                'id': prod2.id,
                'name': prod2.name,
                'society': {
                    'id': prod2.society.id,
                    'name': prod2.society.name 
                }
            }
        ],
    }

