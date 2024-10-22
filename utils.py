import logging
import re
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from typing import Any

from flask.json import JSONEncoder
from flask_login import current_user, AnonymousUserMixin
from pydantic import BaseModel, json
from pymongo import monitoring


done_page = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Authorized</title>
</head>
<body>
    <script>
        window.onload = function() {
            window.close()
        }
    </script>
</body>
</html>
    """


class ACTIVITY(Enum):
    NONE = 0
    STREAM = 1
    LISTEN = 2


class PydanticEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:

        return json.pydantic_encoder(o)


def utcnow():
    return datetime.now(timezone.utc)


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
        }
    else:
        _status = {
            "activity": current_user.activity.name,
            "username": current_user.display_name if current_user.display_name else current_user.username,
            "stream": current_user.stream.name if current_user.stream else None,
        }
    return _status


class Validator:
    # match any string written with any word character, - or " "(space) but ends with alphabet or digits
    stream_name_re = re.compile(r"^[\w\- ]{4,19}[a-zA-Z0-9]$")

    @classmethod
    def stream_name(cls, text):
        return cls.stream_name_re.match(text) is not None
