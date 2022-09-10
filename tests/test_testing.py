import pytest
import os
import sys
import json

# https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from npi_app import npi_app
# response = npi_app.test_client().get("/npi")
# print(response.status_code)

@pytest.fixture()
def app():
    app = npi_app
    app.config.update({
        "TESTING": True,
    })
    # other setup can go here
    yield app
    # clean up / reset resources here

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

# Works fine, running into 210s issue with API's again...
def test_npi_api(client):
    response = client.test_client().post("/npi_check", data={
        "NPINUMBER": "1104392323"
        #"NPINUMBER": "1234567890"

    })
    #resp = json.loads(response.data.decode('utf-8'))
    #print(json.dumps(resp))
    #print(respdict["result_count"])
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    hey = soup.find_all('td')
    for entry in hey:
        print(entry.string)
    #print(soup.contents)
    #hi = soup.contents[1]
    hi = soup.find(id="sticky").string
    print(hey)
    #print(type(response.data))
    #print(response.status_code)
    #print(response.data.decode())
    #assert response.data.decode() == "<span style='color: red;'>No results found</span> for NPI: 1234567890"
    # print(str(response.data, "utf-8"))

def test_npi_get(client):
    response = client.get("/npi")
    #print(response.status_code)
    assert response.status_code == 200

test_npi_api(npi_app)
# test_npi_get(npi_app)