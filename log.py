import logging
from logging.handlers import RotatingFileHandler

def setup_custom_logger(name, file):
    
    formatter = logging.Formatter('%(asctime)s\t%(levelname)s\t%(message)s')
    
    handler = RotatingFileHandler(file, mode='a', maxBytes=1*1024*1024, backupCount=9, encoding=None, delay=0)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  
    logger.addHandler(handler)

    return logger
