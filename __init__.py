from flask import Flask

# noinspection PyPackageRequirements,PyUnresolvedReferences
from helpers import LazyView

app = Flask(__name__)

app.config.from_object('config.BaseConfig')


app.add_url_rule('/',
                 view_func=LazyView('memohub.views.home'))
app.add_url_rule('/auth/<action>',
                 view_func=LazyView('memohub.views.auth'))
app.add_url_rule('/auth',
                 view_func=LazyView('memohub.views.auth_verification'),
                 methods=['POST'])
app.add_url_rule('/resetPassword',
                 view_func=LazyView('memohub.views.reset_password'),
                 methods=['POST'])
app.add_url_rule('/dashboard',
                 view_func=LazyView('memohub.views.dashboard'))
app.add_url_rule('/createBatch',
                 view_func=LazyView('memohub.views.create_batch'),
                 methods=['POST'])
app.add_url_rule('/batch/<batch_id>',
                 view_func=LazyView('memohub.views.batch'))
app.add_url_rule('/sendTextMsg',
                 view_func=LazyView('memohub.views.send_text_msg'),
                 methods=['POST'])
app.add_url_rule('/sendAttachMsg',
                 view_func=LazyView('memohub.views.send_attach_msg'),
                 methods=['POST'])
app.add_url_rule('/addParticipant',
                 view_func=LazyView('memohub.views.add_participant'),
                 methods=['POST'])
app.add_url_rule('/removeParticipant',
                 view_func=LazyView('memohub.views.remove_participant'),
                 methods=['POST'])
app.add_url_rule('/deleteBatch',
                 view_func=LazyView('memohub.views.delete_batch'),
                 methods=['POST'])
app.add_url_rule('/removeBatch',
                 view_func=LazyView('memohub.views.remove_batch'),
                 methods=['POST'])
app.register_error_handler(404, f=LazyView('memohub.views.not_found_error'))
app.register_error_handler(405, f=LazyView('memohub.views.method_not_allowed_error'))
app.add_url_rule('/changeTheme',
                 view_func=LazyView('memohub.views.change_theme'),
                 methods=['POST'])
app.add_url_rule('/logout',
                 view_func=LazyView('memohub.views.logout'))

# Runs App
if __name__ == '__main__':
    app.run(debug=True)