from logging import exception
from turtle import pensize
from xml.dom import ValidationErr
import pytest
import os
import sys

# https://www.crummy.com/software/BeautifulSoup/bs4/doc/
from bs4 import BeautifulSoup

topdir = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(topdir)

from npi_app import npi_app,npyi
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
@pytest.mark.parametrize(
    "npi,valid,results",
    [
        ("", False, False), # Invalid
        ("123", False, False), # Invalid
        ("abc", False, False), # Invalid
        ("1235398777", True, False), # Exception (npyi.exceptions.NPyIException)
        ("1234567890", True, False), # No Results
        ("1104392323", True, True), # Results
    ]
)
def test_npi_api(client, npi, valid, results):
    # Given
    data = {
        "npi": npi
    }

    # When
    response = client.post("/npi_check", data={
        "NPINUMBER": data["npi"]
        #"NPINUMBER": "1234567890"
    })
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    front = soup.get_text()
    #print("soup:",soup)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0
    #print("Results returned:",str(results))

    # 1 result from NPI search.
    if results == True:
        assert results == 1
    if (results == False and valid == True) or (valid == False and results == False):
        assert results == 0
    if npi == "1235398777":
        assert front == "Given NPI number [1235398777] is valid but deactivated, no information available."

        

    # print(rows[1].get_text())
    # for row in rows:
    #     print(row.get_text())

    # count = 0
    # for item in soup.contents:
    #     print("Item [%s]: %s" %(str(count),item))
    #     count = count+1

    #print(type(response.data))
    #print(response.status_code)
    #print(response.data.decode())
    #assert response.data.decode() == "<span style='color: red;'>No results found</span> for NPI: 1234567890"
    # print(str(response.data, "utf-8"))

def LOCAL_npi_api(client):
    # Given
    data = {
        "npi": "1235398777"
    }

    # When
    response = client.test_client().post("/npi_check", data={
        "NPINUMBER": data["npi"]
    })
    npi = data["npi"]
    response = response.data.decode()
    soup = BeautifulSoup(response, 'html.parser')
    print("soup:",soup)
    front = soup.get_text()
    print("front:",front)
    
    rows = soup.find_all('tr')

    # Number of rows returned (-1 for header)
    if rows:
        results = len(rows)-1
    else:
        results = 0
    print("Results returned:",str(results))

    # print(rows[1].get_text())
    # for row in rows:
    #     print(row.get_text())

    # count = 0
    # for item in soup.contents:
    #     print("Item [%s]: %s" %(str(count),item))
    #     count = count+1

    #print(type(response.data))
    #print(response.status_code)
    #print(response.data.decode())
    #assert response.data.decode() == "<span style='color: red;'>No results found</span> for NPI: 1234567890"
    # print(str(response.data, "utf-8"))

        

def test_npi_get(client):
    response = client.get("/npi")
    #print(response.status_code)
    assert response.status_code == 200


#test_npi_api(npi_app)
#test_npi_get(npi_app)
#test_exception(npi_app)
#test_npi_api_local(npi_app)