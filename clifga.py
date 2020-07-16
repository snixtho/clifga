#!/usr/bin/env python3

from app.uicontroller import Clifga, ServerSelector
from app.clcmds import CLCMDHandler
from curses import wrapper
import logging
import sys
import json

# load config
config = json.load(open('config.json', 'r'))

# setup logging
logger = logging.getLogger('clifga')
logger.setLevel(logging.DEBUG)
if config['logging']['enabled']:
    handler = logging.FileHandler(filename=config['logging']['file'], encoding="utf-8", mode="w")
    handler.setLevel(logging._nameToLevel[config['logging']['level']])
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# check for command-line arguments
if CLCMDHandler.Check():
    exit(0)

try:
    # select server
    selector = ServerSelector(config)
    wrapper(selector.run)

    # connect and start
    clifga = Clifga(selector.selectedServer['connection'], config)
    wrapper(clifga.run)
except Exception as e:
    print('ERROR: ' + str(e))
    raise e
