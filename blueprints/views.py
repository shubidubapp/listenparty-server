import os

from flask import Blueprint, send_from_directory, current_app, render_template_string

from utils import done_page

blueprint = Blueprint("views", __name__, url_prefix="/", template_folder="templates/dist/", static_folder="templates/dist/")


@blueprint.route('/done')
def done():
    return render_template_string(done_page)


@blueprint.route('/', defaults={'path': ''})
@blueprint.route('/<path:path>')
def homepage(path):
    if path != "" and os.path.exists(blueprint.template_folder + '/' + path):
        return send_from_directory(f"{blueprint.template_folder}", path)
    return send_from_directory(f"{blueprint.template_folder}", 'index.html')
