import requests
from urllib.parse import urlparse, parse_qs


def get_auth_code_automated(login_url, userid, password, current_otp):
    """
    Bridges the gap by automating the web-login to extract the auth_code.
    """

    # 2. Prepare the login payload (matching Shoonya's web form)
    payload = {"uid": userid, "pwd": password, "otp": current_otp}

    # 3. Submit the form to the login_url
    # We use allow_redirects=False to catch the 'Location' header immediately
    with requests.Session() as session:
        res = session.post(login_url, data=payload, allow_redirects=False)

        # 4. Extract the 'code' from the redirect URL
        redirect_url = res.headers.get("Location")
        if not redirect_url:
            raise Exception(
                "Login failed: No redirect URL found. Check credentials/TOTP."
            )

        parsed_url = urlparse(redirect_url)
        auth_code = parse_qs(parsed_url.query).get("code", [None])[0]

        return auth_code
