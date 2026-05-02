import gspread
from google.oauth2.service_account import Credentials
from config import *

def connect_sheet():
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)


def write_row(spreadsheet, level, row):

    if level == "HIGH":
        sheet = spreadsheet.worksheet("HIGH")
    elif level == "MEDIUM":
        sheet = spreadsheet.worksheet("MEDIUM")
    else:
        sheet = spreadsheet.worksheet("WATCHLIST")

    sheet.append_row(row)
