import logging
import sys
from logging.handlers import TimedRotatingFileHandler


def configure_global_logging():
    log_format = '%(asctime)s--%(name)s:%(threadName)s:%(levelname)s:%(message)s'
    log_file = ".logs/listenParty.log"

    file_handler = TimedRotatingFileHandler(filename=log_file, when='midnight', backupCount=5)
    file_handler.setLevel("DEBUG")
    file_handler.setFormatter(logging.Formatter(log_format))
    logger = logging.getLogger()
    logger.addHandler(file_handler)
    logger.setLevel("DEBUG")

    log = logging.getLogger('authlib')
    log.setLevel("DEBUG")
    log.addHandler(logging.StreamHandler(sys.stdout))

    # noinspection PyArgumentList
    logging.basicConfig(format=log_format, level='DEBUG', handlers=[file_handler])