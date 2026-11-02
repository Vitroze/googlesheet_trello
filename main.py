# This code sample uses the 'requests' library:
# http://docs.python-requests.org

import requests
import time
from datetime import datetime, timedelta

# google lib
import os
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

load_dotenv()
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID_GOOGLE_SHEETS')


KEY_TRELLO = os.getenv('KEY_TRELLO')
TOKEN_TRELLO = os.getenv('TOKEN_TRELLO')
ID_BOARD = os.getenv('BOARD_TRELLO')

tID_Category = {
    "61b0023e50b4f01835449c83": "bugs faibles",
    "61b00b368ff9738500821915": "bugs modérés",
    "61b00b45a19a7872fc697e4b": "bugs urgent",
    "64fb7b0cc7dda475b47e2a4f": "Arme TFA",
    "61b00250cca53d3720bc19c3": "bugs résolus",
    "657cf14e70a1dccbaa593fc4": "bugs résolus"
}

tCategory_GoogleSheet = {
    "A": "Mois",
    "B": "Date précise",
    "C": "ID",  
    "D": "Resp Bug",
    "E": "Catégorie de Bugs",
    "F": "Nom du Bug",
    "G": "Description",
    "H": "Résolu ?",
}


def get_cards():
    url = f"https://api.trello.com/1/boards/{ID_BOARD}/cards"
    params = {
        'key': KEY_TRELLO,
        'token': TOKEN_TRELLO
    }
    response = requests.get(url, params=params)
    cards = response.json()
    return cards


def getCreatorCard(idCard):
    url = f"https://api.trello.com/1/boards/{ID_BOARD}/actions?key={KEY_TRELLO}&token={TOKEN_TRELLO}&filter=createCard&fields=idMemberCreator&idModels={idCard}"

    response = requests.get(url)
    cards = response.json()

    if not cards or len(cards) == 0 or "idMemberCreator" not in cards[0] or "fullName" not in cards[0]["memberCreator"]:
        return "Non renseigné", "Non renseigné"

    return cards[0]["idMemberCreator"], cards[0]["memberCreator"]["fullName"]


request_times = []
# Fonction pour vérifier et gérer le délai d'attente

iCount = 0
def check_request_limit():
    # Ajouter l'heure actuelle à la liste
    global request_times 
    request_times.append(datetime.now())

    # Limiter la liste aux éléments dans la dernière minute
    cutoff_time = datetime.now() - timedelta(minutes=1)
    recent_requests = [t for t in request_times if t > cutoff_time]

    # Si le nombre de requêtes dans la dernière minute est supérieur à 60
    if len(recent_requests) > 59:
        # Attendre une minute avant de poursuivre
        global iCount


        iCount += 1
        print("Limite de requêtes atteinte. En attente pendant 1 minute...", "Nombre de requêtes: ", len(recent_requests), "iCount: ", iCount)


        time.sleep(60)
        # Supprimer les requêtes qui sont maintenant plus âgées que 1 minute
        request_times = [t for t in request_times if t > cutoff_time]

def main():
    credentials = None;
    if os.path.exists('token.json'):
        credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            credentials = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(credentials.to_json())
    
    
    # Get All Cards by Board ID and write in Google Sheet 
    service = build('sheets', 'v4', credentials=credentials)
    sheet = service.spreadsheets()


    cards = get_cards()

    for card in cards:

        if "idList" not in card:
            continue

        iType = card["idList"]
        if not iType in tID_Category:
            continue



        iIDMember, sNameMember = getCreatorCard(card["id"])

        # format date
        card["dateLastActivity"] = card["dateLastActivity"].replace("T", " ")
        card["dateLastActivity"] = card["dateLastActivity"].replace("Z", "")
        card["dateLastActivity"] = card["dateLastActivity"].replace("-", "/")
        card["dateLastActivity"] = card["dateLastActivity"].split(" ")[0]

        check_request_limit()

        records = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID, range="C:C").execute().get('values', [])

        card_exists = False
        iCol = None
        for i, record in enumerate(records):
            if record and record[0] == str(card["idShort"]):
                print("Card already exists", card["idShort"])
                card_exists = True
                iCol = i + 1  
                break
        
        if card_exists:
            bResolu = "Oui" if tID_Category[iType] == "bugs résolus" else "Non"

            values = [
                [
                    card["dateLastActivity"],
                    card["dateLastActivity"],
                    card["idShort"],
                    sNameMember,
                    tID_Category[iType],
                    card["name"],
                    card["desc"] if "desc" in card else "Non renseigné",
                    bResolu,
                ],
            ]

            body = {
                'values': values
            }

            # ecrire a la place de la ligne existante
            range_to_update = f"A{iCol}:H{iCol}"

            print(range_to_update)
            result = sheet.values().update(
                spreadsheetId=SPREADSHEET_ID, range=range_to_update,
                valueInputOption="USER_ENTERED", body=body).execute()
            
        else:
            # Write in Google Sheet
            bResolu = "Oui" if tID_Category[iType] == "bugs résolus" else "Non"
            values = [
                [
                    card["dateLastActivity"],
                    card["dateLastActivity"],
                    card["idShort"],
                    sNameMember,
                    tID_Category[iType],
                    card["name"],
                    card["desc"] if "desc" in card else "Non renseigné",
                    bResolu,
                ],
            ]


            body = {
                'values': values
            }

            # Verifier que la carte n'existe pas déjà dans le Google Sheet (avec le short ID, si il existe, on le met à jour)

            

            result = sheet.values().append(
                spreadsheetId=SPREADSHEET_ID, range="A1:H1",
                valueInputOption="USER_ENTERED", body=body).execute()
            print('{0} cells updated.'.format(result.get('updatedCells')))
            print('{0} rows updated.'.format(result.get('updatedRows')))
            print('{0} columns updated.'.format(result.get('updatedColumns')))
            print('{0} sheets updated.'.format(result.get('updatedSheets')))


        

    try:
        service = build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()

    except HttpError as err:
        print("View error details: %s" % err._get_reason())

while True:
    time.sleep(2)
    main()