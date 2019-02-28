from __future__ import print_function
import requests, json, re, sys
import os, base64, hashlib
import uuid, time
import nsohandler

class Nsotoken():
	def __init__(self, client, nsohandler):
		self.client = client
		self.session = requests.Session()
		self.nsohandler = nsohandler
		self.lang = 'en-US'

	async def login(self, message):
		auth_state = base64.urlsafe_b64encode(os.urandom(36))

		auth_code_verifier = base64.urlsafe_b64encode(os.urandom(32))
		auth_cv_hash = hashlib.sha256()
		auth_cv_hash.update(auth_code_verifier.replace(b"=", b""))
		auth_code_challenge = base64.urlsafe_b64encode(auth_cv_hash.digest())

		app_head = {
			'Host':                      'accounts.nintendo.com',
			'Connection':                'keep-alive',
			'Cache-Control':             'max-age=0',
			'Upgrade-Insecure-Requests': '1',
			'User-Agent':                'Mozilla/5.0 (Linux; Android 7.1.2; Pixel Build/NJH47D; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36',
			'Accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8n',
			'DNT':                       '1',
			'Accept-Encoding':           'gzip,deflate,br',
		}

		body = {
			'state':                                auth_state,
			'redirect_uri':                         'npf71b963c1b7b6d119://auth',
			'client_id':                            '71b963c1b7b6d119',
			'scope':                                'openid user user.birthday user.mii user.screenName',
			'response_type':                        'session_token_code',
			'session_token_code_challenge':         auth_code_challenge.replace(b"=", b""),
			'session_token_code_challenge_method': 'S256',
			'theme':                               'login_form'
		}

		url = 'https://accounts.nintendo.com/connect/1.0.0/authorize'
		r = self.session.get(url, headers=app_head, params=body)

		post_login = r.history[0].url

		await self.client.send_message(message.channel, "Navigate to this URL in your browser: " + post_login)
		await self.client.send_message(message.channel, "Log in, right click the \"Select this person\" button, copy the link address, and paste it back to me")

		while True:
			accounturl = await self.client.wait_for_message(author=message.author, channel=message.channel)
			accounturl = accounturl.content
			if 'npf71b963c1b7b6d119' not in accounturl:
				await self.client.send_message(message.channel, "Invalid URL, please copy the link in \"Select this person\"")
			else:
				break

		
		session_token_code = re.search('session_token_code=(.*)&', accounturl)
		session_token_code = self.get_session_token(session_token_code.group(0)[19:-1], auth_code_verifier)
		thetoken = self.get_cookie(session_token_code)
		await self.nsohandler.addToken(message, str(thetoken))

	def get_session_token(self, session_token_code, auth_code_verifier):
		app_head = {
			'User-Agent':      'OnlineLounge/1.4.1 NASDKAPI Android',
			'Accept-Language': 'en-US',
			'Accept':          'application/json',
			'Content-Type':    'application/x-www-form-urlencoded',
			'Content-Length':  '540',
			'Host':            'accounts.nintendo.com',
			'Connection':      'Keep-Alive',
			'Accept-Encoding': 'gzip'
		}

		body = {
			'client_id':                   '71b963c1b7b6d119',
			'session_token_code':          session_token_code,
			'session_token_code_verifier': auth_code_verifier.replace(b"=", b"")
		}

		url = 'https://accounts.nintendo.com/connect/1.0.0/api/session_token'

		r = self.session.post(url, headers=app_head, data=body)
		return json.loads(r.text)["session_token"]

	def get_cookie(self, session_token):
		timestamp = int(time.time())
		guid = str(uuid.uuid4())

		app_head = {
			'Host': 'accounts.nintendo.com',
			'Accept-Encoding': 'gzip',
			'Content-Type': 'application/json; charset=utf-8',
			'Accept-Language': self.lang,
			'Content-Length': '437',
			'Accept': 'application/json',
			'Connection': 'Keep-Alive',
			'User-Agent': 'OnlineLounge/1.4.1 NASDKAPI Android'
		}

		body = {
			'client_id': '71b963c1b7b6d119',
			'session_token': session_token,
			'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer-session-token'
		}

		url = "https://accounts.nintendo.com/connect/1.0.0/api/token"

		r = requests.post(url, headers=app_head, json=body)
		id_response = json.loads(r.text)

		# get user info
		try:
			app_head = {
				'User-Agent': 'OnlineLounge/1.4.1 NASDKAPI Android',
				'Accept-Language': self.lang,
				'Accept': 'application/json',
				'Authorization': 'Bearer {}'.format(id_response["access_token"]),
				'Host': 'api.accounts.nintendo.com',
				'Connection': 'Keep-Alive',
				'Accept-Encoding': 'gzip'
			}
		except:
			print("Not a valid authorization request. Please delete config.txt and try again.")
			print("Error from Nintendo:")
			print(json.dumps(id_response, indent=2))
			return
		url = "https://api.accounts.nintendo.com/2.0.0/users/me"

		r = requests.get(url, headers=app_head)
		user_info = json.loads(r.text)

		nickname = user_info["nickname"]

		app_head = {
			'Host': 'api-lp1.znc.srv.nintendo.net',
			'Accept-Language': self.lang,
			'User-Agent': 'com.nintendo.znca/1.4.1 (Android/7.1.2)',
			'Accept': 'application/json',
			'X-ProductVersion': '1.4.1',
			'Content-Type': 'application/json; charset=utf-8',
			'Connection': 'Keep-Alive',
			'Authorization': 'Bearer',
			'Content-Length': '1036',
			'X-Platform': 'Android',
			'Accept-Encoding': 'gzip'
		}

		body = {}
		
		idToken = id_response["id_token"]
		parameter = {
			'f': self.get_f_from_flapg_api(idToken, guid, timestamp),
			'naIdToken': idToken,
			'naCountry': user_info["country"],
			'naBirthday': user_info["birthday"],
			'language': user_info["language"],
			'requestId': guid,
			'timestamp': timestamp
		}

		body["parameter"] = parameter

		url = "https://api-lp1.znc.srv.nintendo.net/v1/Account/Login"

		r = requests.post(url, headers=app_head, json=body)
		splatoon_token = json.loads(r.text)

		app_head = {
			'Host': 'api-lp1.znc.srv.nintendo.net',
			'User-Agent': 'com.nintendo.znca/1.4.1 (Android/7.1.2)',
			'Accept': 'application/json',
			'X-ProductVersion': '1.4.1',
			'Content-Type': 'application/json; charset=utf-8',
			'Connection': 'Keep-Alive',
			'Authorization': 'Bearer {}'.format(splatoon_token["result"]["webApiServerCredential"]["accessToken"]),
			'Content-Length': '37',
			'X-Platform': 'Android',
			'Accept-Encoding': 'gzip'
		}

		body = {}
		parameter = {
			"id": 5741031244955648
		}
		body["parameter"] = parameter

		url = "https://api-lp1.znc.srv.nintendo.net/v1/Game/GetWebServiceToken"

		r = requests.post(url, headers=app_head, json=body)
		splatoon_access_token = json.loads(r.text)

		app_head = {
			'Host': 'app.splatoon2.nintendo.net',
			'X-IsAppAnalyticsOptedIn': 'false',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
			'Accept-Encoding': 'gzip,deflate',
			'X-GameWebToken': splatoon_access_token["result"]["accessToken"],
			'Accept-Language': self.lang,
			'X-IsAnalyticsOptedIn': 'false',
			'Connection': 'keep-alive',
			'DNT': '0',
			'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; Pixel Build/NJH47D; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36',
			'X-Requested-With': 'com.nintendo.znca'
		}


		url = "https://app.splatoon2.nintendo.net/?lang={}".format(self.lang)

		r = requests.get(url, headers=app_head)
		return r.cookies["iksm_session"]

	def get_f_from_flapg_api(self, id_token, guid, timestamp):
		api_app_head = {
			'x-token': id_token,
			'x-time': str(timestamp),
			'x-guid': guid,
			'x-hash': get_hash_from_s2s_api(id_token, timestamp)
		}
		api_response = requests.get("https://flapg.com/ika2/api/login", headers=api_app_head)
		f = json.loads(api_response.text)['f']
		return f