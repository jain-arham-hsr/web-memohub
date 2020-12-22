from flask import Flask
from firebase_admin import credentials, initialize_app, storage


app = Flask(__name__)


@app.route('/')
def home():
    return "Hello World!"


@app.route('/lecture_upload')
def lecture_upload():
    cred = credentials.Certificate("serviceAccountKey.json")
    initialize_app(cred, {'storageBucket': 'project-aa-e98db.appspot.com'})
    file_name = "image.jpg"
    bucket = storage.bucket()
    blob = bucket.blob(file_name)
    blob.upload_from_filename(file_name)
    blob.make_public()
    print("your file url", blob.public_url)


if __name__ == '__main__':
    app.run()
