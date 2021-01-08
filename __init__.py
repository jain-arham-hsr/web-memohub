from flask import Flask, session, request, redirect, url_for
from flask_socketio import SocketIO, join_room
from flask_talisman import Talisman
from werkzeug.utils import secure_filename
from datetime import datetime
from decouple import config
import ast

# noinspection PyPackageRequirements,PyUnresolvedReferences
from helpers import LazyView, Firebase, Memohub, validate_file_format, timezone, get_timestamp

app = Flask(__name__)
app.config.from_object('config.BaseConfig')

csp = {
    'default-src': ['\'self\''],
    'script-src': ['*',
                   '\'unsafe-inline\''],
    'style-src': ['*',
                  '\'unsafe-inline\''],
    'img-src': ['*'],
    'font-src': ['*']
}

socket_io = SocketIO(app)
talisman = Talisman(app, content_security_policy=csp)

app.add_url_rule('/',
                 view_func=LazyView('views.home'))
app.add_url_rule('/auth/<action>',
                 view_func=LazyView('views.auth'))
app.add_url_rule('/auth',
                 view_func=LazyView('views.auth_verification'),
                 methods=['POST'])
app.add_url_rule('/resetPassword',
                 view_func=LazyView('views.reset_password'),
                 methods=['POST'])
app.add_url_rule('/dashboard',
                 view_func=LazyView('views.dashboard'))
app.add_url_rule('/createBatch',
                 view_func=LazyView('views.create_batch'),
                 methods=['POST'])
app.add_url_rule('/batch/<batch_id>',
                 view_func=LazyView('views.batch'))
app.add_url_rule('/addParticipant',
                 view_func=LazyView('views.add_participant'),
                 methods=['POST'])
app.add_url_rule('/removeParticipant',
                 view_func=LazyView('views.remove_participant'),
                 methods=['POST'])
app.add_url_rule('/threads/',
                 view_func=LazyView('views.threads'))
app.add_url_rule('/deleteBatch',
                 view_func=LazyView('views.delete_batch'),
                 methods=['POST'])
app.add_url_rule('/removeBatch',
                 view_func=LazyView('views.remove_batch'),
                 methods=['POST'])
app.register_error_handler(404, f=LazyView('views.not_found_error'))
app.register_error_handler(405, f=LazyView('views.method_not_allowed_error'))
app.add_url_rule('/changeTheme',
                 view_func=LazyView('views.change_theme'),
                 methods=['POST'])
app.add_url_rule('/logout',
                 view_func=LazyView('views.logout'))


@socket_io.on('join_room')
def handle_join_room_event():
    print(f"{session.get('display_name')}")
    join_room(session.get('last_batch_opened'))


@socket_io.on('send_text_msg')
def handle_send_text_msg_event(data):
    batch_id = session.get('last_batch_opened')
    display_name = session.get('display_name')
    msg = data['message']
    Memohub.save_text_msg(batch_id, display_name, msg)
    timestamp = get_timestamp()
    payload = {
        'timestamp': timestamp,
        'sender': display_name,
        'msg': msg
    }
    socket_io.emit('receive_text_msg', payload, room=batch_id)


@app.route('/sendAttachMsg', methods=['POST'])
def send_attach_msg():
    if request.method == 'POST':
        batch_id = session.get('last_batch_opened')
        display_name = session.get('display_name')
        files = request.files.getlist("files")
        payload = []
        for file in files:
            if validate_file_format(file.filename):
                sender = session.get('display_name')
                content_type = ast.literal_eval(config("ALLOWED_EXTENSIONS"))[
                    secure_filename(file.filename).rsplit('.', 1)[1].lower()]
                file_id = datetime.now().astimezone(timezone).strftime("%Y%m%d%H%M%S%f%z")
                file_url = Firebase.upload_file_to_storage(file,
                                                           f"file_{file_id}.{secure_filename(file.filename).rsplit('.', 1)[1].lower()}",
                                                           content_type)
                topic = file.filename
                Memohub.save_attach_msg(batch_id, sender, topic, file_url)
                timestamp = get_timestamp()
                upload_data = {
                    'timestamp': timestamp,
                    'sender': display_name,
                    'topic': topic,
                    'file_url': file_url
                }
                payload.append(upload_data)
            else:
                flash(f"Could not upload {file.filename} due to invalid file type")
        socket_io.emit('receive_attach_msg', payload, room=batch_id)
        return redirect(url_for('batch', batch_id=batch_id))
    return render_template('404.html')


@socket_io.on('post_query')
def handle_post_query(data):
    batch_id = session.get('last_batch_opened')
    sender = session.get('display_name')
    query = data['query']
    # only for testing purposes
    profile_img = "https://firebasestorage.googleapis.com/v0/b/project-aa-e98db.appspot.com/o/profileImage.jpg?alt=media&token=6dc5a27f-7bdd-49e8-ba8e-bfd5f61237b1"
    Memohub.save_query(batch_id, sender, query, profile_img)
    timestamp = get_timezone()
    payload = {
        'timestamp': timestamp,
        'author': sender,
        'query': query,
        'profile_img': profile_img
    }
    socket_io.emit('receive_query', payload, room=batch_id)


@socket_io.on('send_reply')
def handle_send_reply(data):
    batch_id = session.get('last_batch_opened')
    sender = session.get('display_name')
    reply = data['message']
    thread = data['thread']
    # only for testing purposes
    profile_img = "https://firebasestorage.googleapis.com/v0/b/project-aa-e98db.appspot.com/o/profileImage.jpg?alt=media&token=6dc5a27f-7bdd-49e8-ba8e-bfd5f61237b1"
    Memohub.save_reply(batch_id, sender, reply, profile_img, thread)
    timestamp = get_timestamp()
    payload = {
        'timestamp': timestamp,
        'author': sender,
        'reply': reply,
        'profile_img': profile_img,
        'thread': thread
    }
    socket_io.emit('receive_reply', payload, room=batch_id)


# Runs App
if __name__ == '__main__':
    socket_io.run(app, debug=True)
