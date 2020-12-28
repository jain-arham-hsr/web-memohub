from firebase_admin import credentials, initialize_app, storage, _apps, db, auth
from firebase_admin._auth_utils import UserNotFoundError
import firebase_admin
import requests
from decouple import config
import json

firebase_web_api_key = config("FIREBASE_WEB_API_KEY")

if not _apps:
    cred = credentials.Certificate('serviceAccountKey.json')
    initialize_app(cred, {'databaseURL': 'https://project-aa-e98db-default-rtdb.firebaseio.com',
                          'storageBucket': 'project-aa-e98db.appspot.com'})


def signup(f_name, l_name, email, password, user_cat):
    firebase_signup_endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
    payload = json.dumps({
        "email": email,
        "password": password
    })
    r = requests.post(firebase_signup_endpoint,
                      params={"key": firebase_web_api_key},
                      data=payload)
    response = r.json()
    if 'idToken' in response.keys():
        id_token = response['idToken']
        update_profile(id_token, f"{f_name} {l_name}")
        send_verification_email(id_token)
        save_data_to_db(f"users/{response['localId']}", {
            'category': user_cat,
            'batches': []
        })
        return True, "Registration Successful"
    else:
        return False, response['error']['message']


def login(email, password):
    firebase_signin_endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    payload = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": True
    })
    r = requests.post(firebase_signin_endpoint,
                      params={"key": firebase_web_api_key},
                      data=payload)
    response = r.json()
    try:
        id_token = response['idToken']
        user_data = get_user_data(id_token)
        email_verified = user_data['users'][0]["emailVerified"]
    except:
        return False, response['error']['message']
    if email_verified:
        return True, (user_data['users'][0]['localId'], user_data['users'][0]['displayName'])
    else:
        send_verification_email(id_token)
        return False, "We need to verify your email first. Please check your Inbox for the verification email."


def get_user_data(id_token):
    firebase_get_user_data_endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:lookup"
    payload = json.dumps({
        "idToken": id_token,
    })
    response = requests.post(firebase_get_user_data_endpoint,
                             params={"key": firebase_web_api_key},
                             data=payload)
    return response.json()


def update_profile(id_token, display_name):
    firebase_update_profile_endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:update"
    payload = json.dumps({
        "idToken": id_token,
        "displayName": display_name,
        "photoUrl": "https://storage.googleapis.com/project-aa-e98db.appspot.com/defaultProfile",
        "deleteAttribute": [],
        "returnSecureToken": True
    })
    requests.post(firebase_update_profile_endpoint,
                  params={"key": firebase_web_api_key},
                  data=payload)


def send_password_reset_email(email):
    password_reset_endpoint = 'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode'
    payload = json.dumps({
        "requestType": "PASSWORD_RESET",
        "email": email
    })
    r = requests.post(password_reset_endpoint,
                  params={"key": firebase_web_api_key},
                  data=payload)
    return r.json()


def send_verification_email(id_token: str):
    send_verification_email_endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
    payload = json.dumps({
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token
    })
    requests.post(send_verification_email_endpoint,
                  params={"key": firebase_web_api_key},
                  data=payload)


def upload_file_to_firebase(file, save_as_filename):
    bucket = storage.bucket()
    blob = bucket.blob(save_as_filename)
    blob.upload_from_file(file)
    blob.make_public()
    return blob.public_url


def save_data_to_db(key, value: dict or str):
    ref = db.reference(key)
    ref.set(value)


def retrieve_data_from_db(key):
    ref = db.reference(key)
    return ref.get()


def append_to_list_db(key, value_to_append):
    batches_array = retrieve_data_from_db(key)
    if batches_array:
        batches_array.append(value_to_append)
        save_data_to_db(key, batches_array)
    else:
        save_data_to_db(key, [value_to_append])


def get_user_info(email):
    try:
        return True, auth.get_user_by_email(email)
    except UserNotFoundError:
        return False, "The user with that email doesn't exist in our database."
    except ValueError:
        return False, "Please enter a valid email address."


def remove_from_list_db(key, value_to_delete):
    batches_array = retrieve_data_from_db(key)
    batches_array.remove(value_to_delete)
    save_data_to_db(key, batches_array)
