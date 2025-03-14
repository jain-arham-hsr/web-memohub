from flask import session, redirect, url_for
from datetime import datetime
import requests
import json
import ast
from werkzeug.utils import import_string, cached_property
from functools import wraps
from decouple import config
import pytz

from firebase_admin import credentials, initialize_app, storage, db, auth
import firebase_admin


class LazyView(object):

    def __init__(self, import_name):
        self.__module__, self.__name__ = import_name.rsplit(".", 1)
        self.import_name = import_name

    @cached_property
    def view(self):
        return import_string(self.import_name)

    def __call__(self, *args, **kwargs):
        return self.view(*args, **kwargs)


class Firebase:

    default_profile_photo = "https://storage.googleapis.com/project-aa-e98db.appspot.com/defaultProfile"

    def __init__(self):
        # noinspection PyProtectedMember
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            initialize_app(cred, {"databaseURL": "https://project-aa-e98db-default-rtdb.firebaseio.com",
                                  "storageBucket": "project-aa-e98db.appspot.com"})
        self.FIREBASE_WEB_API_KEY = config("FIREBASE_WEB_API_KEY")

    def signup(self, f_name, l_name, email, password, user_cat):
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
        payload = json.dumps({
            "email": email,
            "password": password
        })
        response = requests.post(endpoint,
                                 params={"key": self.FIREBASE_WEB_API_KEY},
                                 data=payload).json()
        try:
            id_token = response['idToken']
            local_id = response['localId']
            self.update_profile(id_token, f"{f_name} {l_name}")
            self.send_verification_email(id_token)
            self.save_data(f"users/{local_id}", {
                'category': user_cat,
                'batches': [],
                'theme': 'light'
            })
        except:
            raise Exception(response['error']['message'])

    def login(self, email, password):
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        payload = json.dumps({
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        response = requests.post(endpoint,
                                 params={"key": self.FIREBASE_WEB_API_KEY},
                                 data=payload).json()
        try:
            id_token = response['idToken']
            user_data = self.get_user_data(id_token)['users'][0]
            email_verified = user_data["emailVerified"]
        except:
            raise Exception(response['error']['message'])
        if email_verified:
            return user_data['localId'], user_data['displayName'], user_data['photoUrl']
        else:
            self.send_verification_email(id_token)
            raise Exception("Email not verified yet. Please check your Inbox for verification email.")

    def get_user_data(self, id_token):
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:lookup"
        payload = json.dumps({
            "idToken": id_token,
        })
        response = requests.post(endpoint,
                                 params={"key": self.FIREBASE_WEB_API_KEY},
                                 data=payload).json()
        return response

    @staticmethod
    def get_user_by_uid(uid):
        return auth.get_user(uid)

    @staticmethod
    def get_user_by_email(email):
        return auth.get_user_by_email(email)

    def update_profile(self, id_token, display_name, photo_url=default_profile_photo):
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:update"
        payload = json.dumps({
            "idToken": id_token,
            "displayName": display_name,
            "photoUrl": photo_url,
            "deleteAttribute": [],
            "returnSecureToken": True
        })
        requests.post(endpoint,
                      params={"key": self.FIREBASE_WEB_API_KEY},
                      data=payload)

    def send_password_reset_email(self, email):
        endpoint = 'https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode'
        payload = json.dumps({
            "requestType": "PASSWORD_RESET",
            "email": email
        })
        response = requests.post(endpoint,
                                 params={"key": self.FIREBASE_WEB_API_KEY},
                                 data=payload).json()
        if 'error' in response.keys():
            raise Exception(response['error']['message'])

    def send_verification_email(self, id_token):
        endpoint = "https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode"
        payload = json.dumps({
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        })
        requests.post(endpoint,
                      params={"key": self.FIREBASE_WEB_API_KEY},
                      data=payload)

    @staticmethod
    def upload_file_to_storage(binary_file, filename, content_type="application/octet-stream"):
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        blob.upload_from_file(binary_file, content_type=content_type)
        blob.make_public()
        return blob.public_url

    @staticmethod
    def delete_file_from_storage(filename):
        bucket = storage.bucket()
        if bucket.get_blob(filename):
            bucket.delete_blob(filename)

    @staticmethod
    def save_data(key, value):
        ref = db.reference(key)
        ref.set(value)

    @staticmethod
    def retrieve_data(key):
        ref = db.reference(key)
        return ref.get()

    def append_data(self, key, value_to_append):
        batches_array = self.retrieve_data(key)
        if batches_array:
            batches_array.append(value_to_append)
            self.save_data(key, batches_array)
        else:
            self.save_data(key, [value_to_append])

    def remove_list_item(self, key, value_to_remove):
        batches_array = self.retrieve_data(key)
        batches_array.remove(value_to_remove)
        self.save_data(key, batches_array)

    @staticmethod
    def update_user_by_uid(uid, display_name, photo_url):
        auth.update_user(uid=uid,
                         display_name=display_name,
                         photo_url=photo_url)


firebase = Firebase()


class Memohub:

    @staticmethod
    def save_text_msg(batch_id, sender, msg):
        firebase.append_data(f'batches/batch_{batch_id}/messages', {
            'timestamp': get_timestamp(),
            'type': 'text',
            'sender': sender,
            'value': msg
        })

    @staticmethod
    def save_attach_msg(batch_id, sender, topic, file_url):
        firebase.append_data(f'batches/batch_{batch_id}/messages', {
            'timestamp': get_timestamp(),
            'type': 'file',
            'sender': sender,
            'value': [topic, file_url]
        })

    @staticmethod
    def save_query(batch_id, sender, query, profile_img):
        firebase.append_data(f'batches/batch_{batch_id}/threads', {
            'timestamp': get_timestamp(),
            'author': sender,
            'profile_img': profile_img,
            'query': query,
        })

    @staticmethod
    def save_reply(batch_id, sender, msg, profile_img, thread):
        firebase.append_data(f'batches/batch_{batch_id}/threads/{thread}/sub_threads', {
            'timestamp': get_timestamp(),
            'author': sender,
            'profile_img': profile_img,
            'msg': msg
        })


# login required decorator function
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'uid' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('auth', action="login"))
    return wrap


def set_theme():
    session['profile_data']['theme'] = ast.literal_eval(config("THEME"))[firebase.retrieve_data(f"users/{session.get('uid')}/theme")]


def validate_duplicate_batches(name, section, subject):
    batches = firebase.retrieve_data(f'users/{session["uid"]}/batches') or []
    for batch in batches:
        corresponding_batch_data = firebase.retrieve_data(f'batches/{batch}')
        if all([corresponding_batch_data['name'] == name,
                corresponding_batch_data['section'] == section,
                corresponding_batch_data['subject'] == subject]):
            return True
    return False


def validate_file_format(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ast.literal_eval(config("ALLOWED_EXTENSIONS")).keys()


timezone = pytz.timezone("Asia/Kolkata")


def get_timestamp():
    return datetime.now().astimezone(timezone).strftime("%H:%M %B %d, %Y")
