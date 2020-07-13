import curses
import time
import threading
import logging

from .cli import CommandInputBox, LineBuilder, InfoView, ConsoleBox, ColorPairMaker, SelectionList
from .trackmania.gbxremote import DedicatedRemote
from .trackmania.state import GameStateTracker
from .syntax import Parser

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

    def mainUi(self):
        height, width = self.screen.getmaxyx()
        logger.debug('%s, %s' % (width, height))
        
        # widgets
        cmdInput = CommandInputBox(self.screen, 2, height-1, width-4, self.remote)
        infoView = InfoView(self.screen, 0, height - 2, self.gameState, self.connInfo)

        consoleBox = ConsoleBox(self.screen, 0, 0, width, height-3, self.gameState)
        consoleBox.log(LineBuilder().addText('GBXRemote Ready to recieve commands. Type \'help\' for usage.', ColorPairMaker.MakeColorPair(curses.COLOR_MAGENTA)))

        chatname = self.connInfo['username']

        # initialize
        self.screen.clear()
        self.gameState.initialize()

        while True:
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
                    cmdInput.y = height - 1
                    cmdInput.width = width - 4

                    # info view
                    infoView.y = height - 2

                    # console
                    consoleBox.width = width
                    consoleBox.height = height - 3

                    self.screen.erase()
                
                ####################
                
                # handle inputs
                cmdInput.handle_input(c)
                consoleBox.handle_input(c)

                ####################

                # check if we have a new command
                rawcmd = cmdInput.action(False)

                if rawcmd is not None:
                    try:
                        logger.debug('New command entered: ' + rawcmd)
                        # parse the new cmd
                        parser = Parser(rawcmd)
                        cmd, args = parser.parse()

                        # only clear if correctly parsed
                        cmdInput.clear()

                        # basic internal cmd setup
                        if cmd.lower() == 'exit': # Exit the app
                            self.remote.stop()
                            break
                        elif cmd.lower() == 'help': # Show help msg
                            consoleBox.custom('- HELP -', consoleBox.colorLog, 'For GBXRemote methods, see XMLRPC docs.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, 'Internal app commands:')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  help - Show this help message.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  exit - Close the session and the application.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  togglecallbacks - Toggle automatic display callbacks from the server.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  togglechat - Toggle dispalying of parsed chat messages.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  setname <name> - Set your chat name.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  chat <message> - Toggle dispalying of parsed chat messages.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, 'Keybinds:')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  F1 - Scroll up in the console.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  F2 - Scroll down in the console.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  ENTER - Send method call.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  TAB - Complete method suggestion.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  ARROW UP - Go back in call history.')
                            consoleBox.custom('- HELP -', consoleBox.colorLog, '  ARROW Down - Go forward in call history.')
                            consoleBox.scrollbottom()
                        elif cmd.lower() == 'togglecallbacks': # toggle callbacks display
                            state = consoleBox.getEnableShowcallbacks()
                            consoleBox.enableShowcallbacks(False if state else True)
                            if not state:
                                consoleBox.log('Will now show callbacks.')
                            else:
                                consoleBox.log('Disabled displaying of callbacks.')
                            consoleBox.scrollbottom()
                        elif cmd.lower() == 'togglechat': # toggle chat display
                            state = consoleBox.getEnableShowChat()
                            nextState = False if state else True
                            consoleBox.enableShowChat(nextState)
                            if nextState:
                                consoleBox.log('Will now show the in-game chat.')
                            else:
                                consoleBox.log('Disabled in-game chat display.')
                        elif cmd.lower() == 'setname': # set chat name
                            if len(args) == 1 and type(args[0]) is str:
                                chatname = args[0]
                                consoleBox.log('Your chat name is now: ' + chatname)
                            else:
                                consoleBox.error("Invalid argument for command 'setname'")
                        elif cmd.lower() == 'chat': # send chat message
                            if len(args) > 0:
                                message = ''
                                for arg in args:
                                    message += str(arg) + ' '
                                message = message[:-1]
                                message = '[$c00Admin$g:$<$f36%s$>$fff]$g $< $fc3%s $>' % (chatname, message)
                                t = threading.Thread(target=self.cmdsend_handler, args=('ChatSendServerMessage', [message], cmdInput, consoleBox))
                                t.start()
                                cmdInput.setLoading()
                                consoleBox._logChat('<server-local>', chatname, message)
                            else:
                                consoleBox.error('Please provide an actual message!')
                        else:
                            # send xmlrpc method call
                            t = threading.Thread(target=self.cmdsend_handler, args=(cmd, args, cmdInput, consoleBox))
                            t.start()
                            cmdInput.setLoading()
                    except:
                        pass
                
                c = self.screen.getch()

            ####################
            
            # draw widgets and other things
            consoleBox.draw()
            cmdInput.draw()
            self.screen.addstr(height - 3, 0, '─'*width)
            infoView.draw()
            self.screen.addstr(height - 1, 0, '> ')

            ####################

            # refresh the screen
            cmdInput.setCursor()
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
