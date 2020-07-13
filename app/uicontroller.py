import curses
import time
import threading
import logging

from .cli import CommandInputBox, LineBuilder, InfoView, ConsoleBox, ColorPairMaker, SelectionList
from .trackmania.gbxremote import DedicatedRemote
from .trackmania.state import GameStateTracker
from .syntax import Parser
from .internalcmds import Commands

logger = logging.getLogger('clifga')

class Clifga:
    """GBXRemote admin interface.
    """
    def __init__(self, connInfo, config):
        self.connInfo = connInfo
        self.config = config
        self.remote = DedicatedRemote(
            host=connInfo['host'], 
            port=connInfo['port'], 
            username=connInfo['username'], 
            password=connInfo['password'],
            connRetries=3 if 'connRetries' not in connInfo else connInfo['connRetries'],
            resultTimeout=3 if 'resultTimeout' not in connInfo else connInfo['resultTimeout'])
        
        self.gameState = GameStateTracker(self.remote)
        
        self.screen = None

        self._conn_retry = 0
        self._conn_maxretries = 0

        self.commands = Commands(self)
        self._mainLoopEnabled = True

        # main widgets
        self.cmdInput = None
        self.infoView = None
        self.consoleBox = None

        # chat functions
        self.chatname = 'Admin'
        self.chatMode = config['chatMode']
    
    def _conn_attempt_cb(self, retry, maxretries):
        self._conn_retry = retry
        self._conn_maxretries = maxretries

        self._draw_connectionui()
    
    def _draw_connectionui(self):
        width = curses.COLS
        height = curses.LINES
        s1 = '%s@%s:%s' % (self.connInfo['username'], self.connInfo['host'], self.connInfo['port'])
        s2 = 'Connecting, please wait ...'
        s3 = 'Attempt %d of %d' % (self._conn_retry, self._conn_maxretries)

        x1 = round((width - len(s1))/2)
        x2 = round((width - len(s2))/2)
        x3 = round((width - len(s3))/2)
        ymiddle = round(height/2)

        self.screen.clear()
        self.screen.addstr(ymiddle-1, x1, s1)
        self.screen.addstr(ymiddle, x2, s2)
        self.screen.addstr(ymiddle+1, x3, s3)
        self.screen.refresh()
   
    def connectionUi(self):
        result = self.remote.connect(5, attemptcb=self._conn_attempt_cb)
        return result
    
    def cmdsend_handler(self, cmd, args, cmdInput, console):
        try:
            result = self.remote.call(cmd, *tuple(args))
            console.custom('Result ~ %s' % cmd, console.colorWarning, str(result))
        except Exception as e:
            console.error('Failed calling XMLRPC method: %s' % str(e))
        finally:
            cmdInput.setLoading(False)
            console.scrollbottom()

    def chatSend(self, message):
        # build message
        message = '[$c00Admin$g:$<$f66%s$>$fff]$g $<$fc3%s$>' % (self.chatname, message)

        # send it
        t = threading.Thread(target=self.cmdsend_handler, args=('ChatSendServerMessage', [message], self.cmdInput, self.consoleBox))
        t.start()
        self.cmdInput.setLoading()
        self.consoleBox._logChat('<server-local>', self.chatname, message)

    def mainUi(self):
        height, width = self.screen.getmaxyx()
        logger.debug('%s, %s' % (width, height))
        
        # widgets
        self.cmdInput = CommandInputBox(self.screen, 2, height-1, width-4, self.remote)
        self.infoView = InfoView(self.screen, 0, height - 2, self.gameState, self.connInfo, self)

        self.consoleBox = ConsoleBox(self.screen, 0, 0, width, height-3, self.gameState, self.config['maxLogs'])
        self.consoleBox.enableShowChat(self.config['chatDisplay'])
        self.consoleBox.enableShowcallbacks(self.config['callbacksDisplay'])
        self.consoleBox.enableShowJoinAndLeave(self.config['showJoinAndLeave'])

        # initialize
        self.gameState.initialize()

        # ready
        self.consoleBox.log(LineBuilder().addText('GBXRemote Ready to recieve commands. Type \'help\' for usage.', ColorPairMaker.MakeColorPair(curses.COLOR_MAGENTA)))
        self.screen.clear()

        while self._mainLoopEnabled:
            c = self.screen.getch()

            while c != curses.ERR:
                if c == 27:
                    # detect special key, fix for ssh
                    seq = [c]
                    while True:
                        nextc = self.screen.getch()
                        if nextc == curses.ERR:
                            break
                        seq.append(nextc)
                    logger.debug('Special key sequence detected: %s' % str(seq))

                    if seq == [27, 79, 80]: # F1
                        c = curses.KEY_F1
                    elif seq == [27, 79, 81]: # F2
                        c = curses.KEY_F2
                elif c == 127: # Backspace
                    c = curses.KEY_BACKSPACE

                # update variables and perform full re-draw if window is resized
                if c == curses.KEY_RESIZE:
                    height, width = self.screen.getmaxyx()
                    logger.debug('RESIZE EVENT')
                    logger.debug('%s, %s' % (width, height))

                    # input box
                    self.cmdInput.y = height - 1
                    self.cmdInput.width = width - 4

                    # info view
                    self.infoView.y = height - 2

                    # console
                    self.consoleBox.width = width
                    self.consoleBox.height = height - 3

                    self.screen.erase()
                
                ####################
                
                # handle inputs
                self.cmdInput.handle_input(c)
                self.consoleBox.handle_input(c)

                ####################

                # check if we have a new command
                rawcmd = self.cmdInput.action(False)

                if rawcmd is not None:
                    try:
                        tryCommand = False

                        # check for chatmode
                        if self.chatMode:
                            if len(rawcmd) > 0 and rawcmd[0] == '/':
                                rawcmd = rawcmd[1:]
                                tryCommand = True
                            else:
                                # in chatmode and not a command, so send the raw input to chat
                                self.cmdInput.clear()
                                self.chatSend(rawcmd)
                        else:
                            tryCommand = True

                        if tryCommand:
                            logger.debug('New command entered: ' + rawcmd)
                            # parse the new cmd
                            parser = Parser(rawcmd)
                            cmd, args = parser.parse()

                            # only clear if correctly parsed
                            self.cmdInput.clear()

                            if not self.commands.callIfExists(cmd, *args):
                                # send xmlrpc method call
                                t = threading.Thread(target=self.cmdsend_handler, args=(cmd, args, self.cmdInput, self.consoleBox))
                                t.start()
                                self.cmdInput.setLoading()
                    except:
                        pass
                
                c = self.screen.getch()

            ####################
            
            # draw widgets and other things
            self.consoleBox.draw()
            self.cmdInput.draw(self.chatMode)
            self.screen.addstr(height - 3, 0, '─'*width)
            self.infoView.draw()
            self.screen.addstr(height - 1, 0, '> ')

            ####################

            # refresh the screen
            self.cmdInput.setCursor()
            self.screen.refresh()

            time.sleep(0.1)
        
        return True

    def run(self, screen):
        self.screen = screen
        screen.nodelay(1)
        curses.noecho()

        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)

        if not self.connectionUi():
            raise Exception('Connection failed.')

        if not self.mainUi():
            raise Exception('Main UI failed, see log.')

class ServerSelector:
    """Server selection screen.
    """
    def __init__(self, config):
        self.screen = None
        self.config = config
        self.selectedServer = None
    
    def selectionScreen(self):
        self.screen.clear()
        height, width = self.screen.getmaxyx()

        # setup selection widget
        selectionList = SelectionList(self.screen, 0, 0, width, height)

        for server in self.config['servers']:
            selectionList.addOption(server['name'], server)

        while True:
            c = self.screen.getch()

            # handle resizing
            if c == curses.KEY_RESIZE:
                height, width = self.screen.getmaxyx()
                selectionList.width = width
                selectionList.height = height
                self.screen.erase()
            
            # handle inputs
            selectionList.handle_input(c)

            # check selection
            if selectionList.hasSelected():
                self.selectedServer = selectionList.options[selectionList.selection]['value']
                logger.debug(self.selectedServer)
                return

            # draw screen
            selectionList.draw()
            self.screen.refresh()
    
    def run(self, screen):
        self.screen = screen
        screen.nodelay(True)
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
        self.selectionScreen()
