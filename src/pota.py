import requests


SPOT_URL = "https://api.pota.app/spot/activator"
SPOT_COMMENTS_URL = "https://api.pota.app/spot/comments/{act}/{park}"
ACTIVATOR_URL = "https://api.pota.app/stats/user/{call}"


class Api():
    '''Class that calls the POTA endpoints and returns their results'''

    def __init__(self):
        pass

    def get_spots(self):
        '''Return all current spots from POTA API'''
        response = requests.get(SPOT_URL)
        if response.status_code == 200:
            json = response.json()
            return json

    def get_spot_comments(self, activator, park):
        '''Return all spot + comments from a given activation'''
        url = SPOT_COMMENTS_URL.format(act=activator, park=park)
        response = requests.get(url)
        if response.status_code == 200:
            json = response.json()
            return json

    def get_activator_stats(self, activator: str):
        '''Return all spot + comments from a given activation'''
        x = activator.split('/')
        if len(x) == 3:
            s = x[1]
        else:
            s = x[0]

        url = ACTIVATOR_URL.format(call=s)
        response = requests.get(url)
        if response.status_code == 200:
            json = response.json()
            return json
        else:
            return None
