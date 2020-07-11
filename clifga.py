#!/usr/bin/env python3

#from app.syntax import Parser

"""expr = 'CallVoteEx "test1" "test2" "test3" "test3"'
parser = Parser(expr)
print('Expression: ' + expr)
print('Parsed:', parser.parse())"""


from app.uicontroller import Clifga, ServerSelector
from curses import wrapper
import logging
import sys
import json

# setup logging
logger = logging.getLogger('clifga')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename="clifga.log", encoding="utf-8", mode="w")
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

config = json.load(open('config.json', 'r'))

try:
    selector = ServerSelector(config)
    wrapper(selector.run)

    clifga = Clifga(selector.selectedServer['connection'], config)
    wrapper(clifga.run)
except Exception as e:
    print('ERROR: ' + str(e))
    raise e
