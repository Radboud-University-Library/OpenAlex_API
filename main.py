import requests
import pandas as pd


radboud = "i145872427"
ror = "016xsfp80"
example_work = "W2125284466"

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
        self.filter = "?filter"

    """ Filter multiple attributes """
    def filter_attributes(self, filters):
        filter_strings = [f"{attribute}:{value}" for attribute, value in filters]
        filter_url = f"{self.filter}=" + ",".join(filter_strings)
        return filter_url

class Entities:
    def __init__(self):
        self.request = ApiRequest()
        self.filter_instance = Filter()

    """ Get single entity """
    def get_entity(self, endpoint):
        return self.request.get_data(endpoint)

    """ Get multiple entities """
    def get_multiple_entities(self, endpoint):
        return self.request.get_results_data(endpoint)

    """ Create filter endpoint. Receives entity type from calling class """
    def filter(self, entity_type, filters):
        endpoint = f"{entity_type}{self.filter_instance.filter_attributes(filters)}"
        return self.get_multiple_entities(endpoint)


class Works():
    def __init__(self):
        self.entities = Entities()
        self.entity = "works"

    """ Delegates dynamic method calls to Entities class """
    def __getattr__(self, name):
        return getattr(self.entities, name)

    """ Call Filter method from Entities class for list filters and adds entity type. 
        Expects a tuple variable """
    def filter(self, filters):
        return self.entities.filter(self.entity, filters)

class Institution():
    def __init__(self):
        self.institutions_id = "i145872427"
        self.ror = "016xsfp80"


work = Works()
#w = work.filter([("institutions.id","i145872427"),("from_publication_date","2022-01-01")])
w = work.filter([("institutions.id","i145872427")])

print(len(w))
#print(w["results"][0].keys())
#w["meta"]
#print(w["group_by"])
#print(w.keys())