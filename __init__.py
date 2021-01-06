from flask import Flask, session, request, redirect, url_for
from flask_socketio import SocketIO, join_room
from werkzeug.utils import secure_filename
from datetime import datetime
from decouple import config
import ast

# noinspection PyPackageRequirements,PyUnresolvedReferences
from helpers import LazyView, Firebase, Memohub, validate_file_format

app = Flask(__name__)
app.config.from_object('config.BaseConfig')

socket_io = SocketIO(app)


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
    payload = {
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
            print(file.filename)
            if validate_file_format(file.filename):
                sender = session.get('display_name')
                content_type = ast.literal_eval(config("ALLOWED_EXTENSIONS"))[
                    secure_filename(file.filename).rsplit('.', 1)[1].lower()]
                file_id = datetime.now().strftime("%Y%m%d%H%M%S%f%z")
                file_url = Firebase.upload_file_to_storage(file,
                                                           f"file_{file_id}.{secure_filename(file.filename).rsplit('.', 1)[1].lower()}",
                                                           content_type)
                topic = file.filename
                Memohub.save_attach_msg(batch_id, sender, topic, file_url)
                upload_data = {
                    'sender': display_name,
                    'topic': topic,
                    'file_url': file_url
                }
                payload.append(upload_data)
                print(payload)
            else:
                flash(f"Could not upload {file.filename} due to invalid file type")
        socket_io.emit('receive_attach_msg', payload, room=batch_id)
        print(payload)
        return redirect(url_for('batch', batch_id=batch_id))
    return render_template('404.html')


# Runs App
if __name__ == '__main__':
    socket_io.run(app, debug=True)
