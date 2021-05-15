import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

from flask_login import current_user, AnonymousUserMixin
from pymongo import monitoring

from models import ACTIVITY

done_page = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Authorized</title>
</head>
<body>
    <script>
        window.close();
    </script>
</body>
</html>
    """


class CommandLogger(monitoring.CommandListener):
    def __init__(self):
        self.logger = logging.getLogger("PyMongo")

    def started(self, event):
        self.logger.debug("Command {0.command_name} with request id "
                          "{0.request_id} started on server "
                          "{0.connection_id}".format(event))

    def succeeded(self, event):
        self.logger.debug("Command {0.command_name} with request id "
                          "{0.request_id} on server {0.connection_id} "
                          "succeeded in {0.duration_micros} "
                          "microseconds".format(event))

    def failed(self, event):
        self.logger.debug("Command {0.command_name} with request id "
                          "{0.request_id} on server {0.connection_id} "
                          "failed in {0.duration_micros} "
                          "microseconds".format(event))


def configure_global_logging():
    log_format = '%(asctime)s--%(name)s:%(levelname)s:%(message)s'
    log_file = ".logs/listenParty.log"

    file_handler = TimedRotatingFileHandler(filename=log_file, when='midnight', backupCount=2)
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(logging.Formatter(log_format))
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.setLevel("DEBUG")

    monitoring.register(CommandLogger())

    # log = logging.getLogger('authlib')
    # log.setLevel("DEBUG")
    # log.addHandler(logging.StreamHandler(sys.stdout))

    # noinspection PyArgumentList
    logging.basicConfig(format=log_format, level='DEBUG', handlers=[file_handler])


def message(text, status_):
    return {
        "text": text, "status": status_, "time": datetime.utcnow().timestamp()
    }


def prepare_status():
    if isinstance(current_user, AnonymousUserMixin):
        _status = {
            "activity": ACTIVITY.NONE.name,
            "username": None,
            "stream": None,
            "listener": None
        }
    else:
        _status = {
            "activity": current_user.activity.name,
            "username": current_user.display_name if current_user.display_name else current_user.username,
            "stream": current_user.stream.name if current_user.stream else None,
            "listener": len(current_user.stream.listeners) if current_user.stream else None
        }
    return _status
