# src/auth.py
#
# Den här filen innehåller små hjälpfunktioner för deltagarlänkar.
#
# Viktig idé:
# Vi vill inte spara den privata token direkt i databasen.
# I stället sparar vi en hash av token.
#
# Deltagaren får:
#   http://localhost:8501?token=hemlig-token
#
# Databasen sparar:
#   sha256(hemlig-token)
#
# Det gör att om någon ser databasen så ser den inte själva länktoken.

import hashlib
import secrets as py_secrets
from urllib.parse import urlencode


def generate_private_token() -> str:
    """
    Skapar en slumpmässig privat token för en deltagare.

    token_urlsafe skapar en URL-vänlig sträng.
    32 bytes ger en lång token som är mycket svår att gissa.
    """

    return py_secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Gör om en token till en SHA-256-hash.

    Samma token ger alltid samma hash.
    Men det är praktiskt taget omöjligt att gå från hash tillbaka till token.
    """

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_participant_link(base_url: str, token: str) -> str:
    """
    Bygger en deltagarlänk.

    urlencode ser till att query-parametern blir korrekt formaterad.
    Exempel:
        http://localhost:8501?token=abc123
    """

    query_string = urlencode({"token": token})
    return f"{base_url}?{query_string}"