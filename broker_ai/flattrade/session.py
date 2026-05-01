import hashlib
import requests
import pyotp
from urllib.parse import urlparse, parse_qs


def get_session_token(userid, password, twoFA, api_key, api_secret, verbose=False):
    session_url = "https://authapi.flattrade.in/auth/session"
    ftauth_url = "https://authapi.flattrade.in/ftauth"
    apitoken_url = "https://authapi.flattrade.in/trade/apitoken"

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Host": "authapi.flattrade.in",
        "Origin": "https://auth.flattrade.in",
        "Referer": "https://auth.flattrade.in/",
    }

    with requests.Session() as session:
        session.headers.update(headers)

        # Step 1: Get session ID (sid)
        r = session.post(session_url)
        if r.status_code != 200:
            raise Exception("Failed to get session ID")
        sid = r.text

        if verbose:
            print("SID:", sid)

        # Step 2: Prepare auth payload
        def auth_request(override=""):
            return {
                "UserName": userid,
                "Password": hashlib.sha256(password.encode()).hexdigest(),
                "App": "",
                "ClientID": "",
                "Key": "",
                "APIKey": api_key,
                "PAN_DOB": pyotp.TOTP(twoFA).now(),
                "Sid": sid,
                "Override": override,
            }

        r = session.post(ftauth_url, json=auth_request())
        auth_json = r.json()

        if verbose:
            print("Auth Response:", auth_json)

        if auth_json.get("emsg") == "DUPLICATE":
            if verbose:
                print("Retrying with Override: Y")
            r = session.post(ftauth_url, json=auth_request("Y"))
            auth_json = r.json()

            if verbose:
                print("Auth Response 2:", auth_json)

        if auth_json.get("emsg"):
            raise Exception("Auth error: " + auth_json["emsg"])

        redirect_url = auth_json.get("RedirectURL")
        if not redirect_url:
            raise Exception("Missing RedirectURL")

        if verbose:
            print("Redirect URL:", redirect_url)

        # Step 3: Extract code
        parsed_url = urlparse(redirect_url)
        params = parse_qs(parsed_url.query)
        code = params.get("code", [None])[0]

        if not code:
            raise Exception("Missing code in RedirectURL")

        if verbose:
            print("Code:", code)

        # Step 4: Generate final token
        item = api_key + code + api_secret
        api_secret_hash = hashlib.sha256(item.encode()).hexdigest()
        payload = {
            "api_key": api_key,
            "request_code": code,
            "api_secret": api_secret_hash,
        }

        r = session.post(apitoken_url, json=payload)
        token_json = r.json()

        if verbose:
            print("Token JSON:", token_json)

        token = token_json.get("token")
        if not token:
            raise Exception("Token not found")

        return token


# Example usage
if __name__ == "__main__":
    userid = ""
    password = ""
    twoFA = ""
    api_key = ""
    api_secret = ""

    token = get_session_token(
        userid, password, twoFA, api_key, api_secret, verbose=True
    )
    print(f"Session Token: {token}")
