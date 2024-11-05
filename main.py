import requests
import pandas as pd

radboud = "i145872427"
"works/W2125284466"

class ApiRequest:
    # Configure API class default parameters
    BASE_URL = "https://api.openalex.org/"
    EMAIL = "sjors.startman@ru.nl"
    HEADER = {"User-Agent": f"mailto:{EMAIL}"}

    """ Initialize API request """
    def __init__(self, base_url=None, email=None, header=None):
        # Configure API class variables
        self.base_url = base_url or self.BASE_URL
        self.email = email or self.EMAIL
        self.header = header or self.HEADER

    """ Build full url """
    def full_url(self, endpoint):
        full_url = f"{self.base_url}{endpoint}"
        return full_url

    """ Make API request and returns JSON response data """
    def get_data(self, endpoint):
        full_url = self.full_url(endpoint)
        response = requests.get(full_url, headers=self.header)
        data = response.json()
        return data

    """ Return meta data"""
    def get_meta_data(self, endpoint):
        meta_data = self.get_data(endpoint)["meta"]
        return meta_data

    """ Return results data """
    def get_results_data(self, endpoint):
        results_data = self.get_data(endpoint)["results"]
        return results_data

class Paging:
    """ Configure number of pages to be shown """
    PER_PAGE = "100"
    def __init__(self, per_page=None):
        self.request = ApiRequest()
        self.per_page = per_page or self.PER_PAGE

    """ Cursor paging to see all pages and return data """
    def cursor_paging(self, endpoint):
        cursor = "*"
        data = []
        while True:
            response = self.request.get_data(f"{endpoint}&per_page={self.per_page}&cursor={cursor}")
            data.extend(response.get('results', []))
            cursor = response.get('meta', {}).get('next_cursor', None)
            if cursor is None:
                break
        return data

class Dataframe:
    # Convert JSON data to pandas Dataframe
    def json_to_dataframe(self, json_data):
        if isinstance(json_data, list):
            # If it's a list, pass it directly to pd.json_normalize
            df = pd.json_normalize(json_data)
        elif isinstance(json_data, dict):
            # If it's a dictionary, wrap it in a list first
            df = pd.json_normalize([json_data])
        else:
            raise ValueError("The input data must be a dictionary or a list of dictionaries.")
        return df

class Filter:
    def __init__(self):
        self.request = ApiRequest()

    def filter_expressions(self):
        pass
        # different symbols

    def filter_url(self, attribute, value):
        filter_url = f"?filter={attribute}:{value}"
        return filter_url

    def filter_endpoint(self):
        filter_endpoint = f"{self.request.full_url}{self.filter_url}"
        return filter_endpoint


class Entities:
    def __init__(self):
        self.request = ApiRequest()

class Works:
    def __init__(self):
        self.request = ApiRequest()

    def get_works(self):
        #endpoint = f"{self.entity}?filter=authorships.affiliations.institution_ids:{radboud}"
        endpoint = f"works?filter=author.id:A5048491430"
        #json_data = self.get_data(endpoint)
        #df = self.json_to_dataframe(json_data)
        return self.request.get_results_data(endpoint)


work = Works()
w = work.get_works()

print(w)
#print(w["results"][0].keys())
#print(w["meta"])
#print(w["group_by"])
#print(w.keys())