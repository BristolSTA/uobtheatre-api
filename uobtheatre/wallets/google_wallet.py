import json
import os
import uuid

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from google.auth import jwt, crypt

ISSUER_ID = "3388000000022140887"

class GoogleWallet:
    """Google wallet clinet

    Attributes:
        key_file_path: Path to service account key file from Google Cloud
            Console. Environment variable: GOOGLE_APPLICATION_CREDENTIALS.
        base_url: Base URL for Google Wallet API requests.
    """

    def __init__(self):
        self.key_file_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', 'uobtheatre-aa2c8cca7987.json')
        self.base_url = 'https://walletobjects.googleapis.com/walletobjects/v1'
        self.batch_url = 'https://walletobjects.googleapis.com/batch'
        self.class_url = f'{self.base_url}/eventTicketClass'
        self.object_url = f'{self.base_url}/eventTicketObject'

        # Set up authenticated client
        self._auth()

    def _auth(self):
        """Create authenticated HTTP client using a service account file."""
        self.credentials = Credentials.from_service_account_file(
            self.key_file_path,
            scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
        )

        self.http_client = AuthorizedSession(self.credentials)

    def create_ticket_class(self, event_id: str, event_name: str, issuer: str):
        new_class = {
            'id': f'{ISSUER_ID}.test-{event_id}',
            'issuerName': issuer, 
            'reviewStatus': 'UNDER_REVIEW',
            'eventName': {
                'defaultValue': {
                    'language': 'en-US',
                    'value': event_name 
                }
            }
        }

        self.http_client.post(url=self.class_url, json=new_class)
        print(response.json())


    def create_jwt_new_objects(self, object_id: str, class_id: str) -> str:
        """Generate a signed JWT that creates a new pass class and object.

        When the user opens the "Add to Google Wallet" URL and saves the pass to
        their wallet, the pass class and object defined in the JWT are
        created. This allows you to create multiple pass classes and objects in
        one API call when the user saves the pass to their wallet.

        Args:
            issuer_id (str): The issuer ID being used for this request.
            class_suffix (str): Developer-defined unique ID for the pass class.
            object_suffix (str): Developer-defined unique ID for the pass object.

        Returns:
            An "Add to Google Wallet" link.
        """

        print("callin")

        # See link below for more information on required properties
        # https://developers.identifiedgoogle.com/wallet/tickets/events/rest/v1/eventticketobject
        new_object = {
            'id': f'{ISSUER_ID}.test-{object_id}',
            'classId': class_id,
            'state': 'ACTIVE',
            'heroImage': {
                'sourceUri': {
                    'uri':
                        'https://farm4.staticflickr.com/3723/11177041115_6e6a3b6f49_o.jpg'
                },
                'contentDescription': {
                    'defaultValue': {
                        'language': 'en-US',
                        'value': 'Hero image description'
                    }
                }
            },
            'textModulesData': [{
                'header': 'Text module header',
                'body': 'Text module body',
                'id': 'TEXT_MODULE_ID'
            }],
            'linksModuleData': {
                'uris': [{
                    'uri': 'http://maps.google.com/',
                    'description': 'Link module URI description',
                    'id': 'LINK_MODULE_URI_ID'
                }, {
                    'uri': 'tel:6505555555',
                    'description': 'Link module tel description',
                    'id': 'LINK_MODULE_TEL_ID'
                }]
            },
            'imageModulesData': [{
                'mainImage': {
                    'sourceUri': {
                        'uri':
                            'http://farm4.staticflickr.com/3738/12440799783_3dc3c20606_b.jpg'
                    },
                    'contentDescription': {
                        'defaultValue': {
                            'language': 'en-US',
                            'value': 'Image module description'
                        }
                    }
                },
                'id': 'IMAGE_MODULE_ID'
            }],
            'barcode': {
                'type': 'QR_CODE',
                'value': 'QR code'
            },
            'locations': [{
                'latitude': 37.424015499999996,
                'longitude': -122.09259560000001
            }],
            'seatInfo': {
                'seat': {
                    'defaultValue': {
                        'language': 'en-US',
                        'value': '42'
                    }
                },
                'row': {
                    'defaultValue': {
                        'language': 'en-US',
                        'value': 'G3'
                    }
                },
                'section': {
                    'defaultValue': {
                        'language': 'en-US',
                        'value': '5'
                    }
                },
                'gate': {
                    'defaultValue': {
                        'language': 'en-US',
                        'value': 'A'
                    }
                }
            },
            'ticketHolderName': 'Ticket holder name',
            'ticketNumber': 'Ticket number'
        }

        # Create the JWT claims
        claims = {
            'iss': self.credentials.service_account_email,
            'aud': 'google',
            'origins': ['www.example.com'],
            'typ': 'savetowallet',
            'payload': {
                # The listed classes and objects will be created
                # 'eventTicketClasses': [new_class],
                'eventTicketObjects': [new_object]
            }
        }

        # The service account credentials are used to sign the JWT
        print("singing")
        signer = crypt.RSASigner.from_service_account_file(self.key_file_path)
        print("token")
        token = jwt.encode(signer, claims).decode('utf-8')
        print("done")

        print('Add to Google Wallet link')
        print(f'https://pay.google.com/gp/v/save/{token}')

        return f'https://pay.google.com/gp/v/save/{token}'
