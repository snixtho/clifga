import logging
import threading
from .cli import LineBuilder, ColorPairMaker
import curses

logger = logging.getLogger('clifga')

class Commands:
    def __init__(self, main):
        self.cmds = dict()
        self.main = main

        self._register('help', self.cmd_help, 'Show this help message.')
        self._register('exit', self.cmd_exit, 'Close the session and the application.')
        self._register('togglecallbacks', self.cmd_togglecallbacks, 'Toggle automatic display callbacks from the server.')
        self._register('togglechat', self.cmd_togglechat, 'Toggle displaying of parsed chat messages.')
        self._register('setname', self.cmd_setname, 'Set your chat name.')
        self._register('chat', self.cmd_chat, 'Send a chat message.')
        self._register('togglechatmode', self.cmd_togglechatmode, 'Toggles the chat mode. If enabled, anything you type will be sent as a chat message, start the text with \'/\' to invoke a command.')
        self._register('players', self.cmd_players, 'Show a list of connected players.')
        self._register('togglejoinleave', self.cmd_togglejoinleave, 'Toggle displaying of join/leave messages.')

        self.colorBlack = ColorPairMaker.MakeColorPair(curses.COLOR_BLACK)
        self.colorBlue = ColorPairMaker.MakeColorPair(curses.COLOR_BLUE)
        self.colorCyan = ColorPairMaker.MakeColorPair(curses.COLOR_CYAN)
        self.colorGreen = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
        self.colorMagenta = ColorPairMaker.MakeColorPair(curses.COLOR_MAGENTA)
        self.colorRed = ColorPairMaker.MakeColorPair(curses.COLOR_RED)
        self.colorWhite = ColorPairMaker.MakeColorPair(curses.COLOR_WHITE)
        self.colorYellow = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)
    
    def _register(self, name, func, desc=''):
        self.cmds[name] = {
            'func': func,
            'desc': desc
        }
    
    def callIfExists(self, name, *args):
        logger.debug(name)
        if name in self.cmds:
            try:
                self.cmds[name]['func'](*args)
            except Exception as e:
                self.main.consoleBox.error('Command failed: %s' % str(e))
                logger.debug('Failed executing command.', exc_info=e)
            return True
        return False
    
    ###########################################################

    def cmd_help(self):
        color = self.main.consoleBox.colorLog
        self.main.consoleBox.custom('- HELP -', color, 'For GBXRemote methods, see XMLRPC docs.')
        self.main.consoleBox.custom('- HELP -', color, 'Internal app commands:')

        for name, cmd in self.cmds.items():
            self.main.consoleBox.custom('- HELP -', color, '  %s - %s' % (str(name), str(cmd['desc'])))
        
        self.main.consoleBox.custom('- HELP -', color, 'Keybinds:')
        self.main.consoleBox.custom('- HELP -', color, '  F1 - Scroll up in the console.')
        self.main.consoleBox.custom('- HELP -', color, '  F2 - Scroll down in the console.')
        self.main.consoleBox.custom('- HELP -', color, '  ENTER - Send method call.')
        self.main.consoleBox.custom('- HELP -', color, '  TAB - Complete method suggestion.')
        self.main.consoleBox.custom('- HELP -', color, '  ARROW UP - Go back in call history.')
        self.main.consoleBox.custom('- HELP -', color, '  ARROW Down - Go forward in call history.')
    
    def cmd_exit(self):
        """Exit the application properly.
        """
        self.main.remote.stop()

        # notify stop
        self.main._mainLoopEnabled = False
    
    def cmd_togglecallbacks(self):
        """Toggle callbacks display.
        """
        state = self.main.consoleBox.getEnableShowcallbacks()
        self.main.consoleBox.enableShowcallbacks(False if state else True)
        if not state:
            self.main.consoleBox.log('Will now show callbacks.')
        else:
            self.main.consoleBox.log('Disabled displaying of callbacks.')
        self.main.consoleBox.scrollbottom()
    
    def cmd_togglechat(self):
        """Toggle chat display.
        """
        state = self.main.consoleBox.getEnableShowChat()
        nextState = False if state else True
        self.main.consoleBox.enableShowChat(nextState)
        if nextState:
            self.main.consoleBox.log('Will now show the in-game chat.')
        else:
            self.main.consoleBox.log('Disabled in-game chat display.')

    def cmd_setname(self, name):
        """Set chat name.

        Args:
            name (string): Your chat name.
        """
        if type(name) is str:
            self.main.chatname = name
            self.main.consoleBox.log('Your chat name is now: ' + self.main.chatname)
        else:
            self.main.consoleBox.error("Invalid argument for command 'setname'")

    def cmd_chat(self, *args):
        """Send a chat message.
        """
        if len(args) > 0:
            message = ''
            for arg in args:
                message += str(arg) + ' '
            message = message[:-1]

            self.main.chatSend(message)
        else:
            self.main.consoleBox.error('Please provide an actual message!')

    def cmd_togglechatmode(self):
        """Enable chat mode.
        """
        self.main.chatMode = not self.main.chatMode
        line = LineBuilder()
        line.addText('Chat mode ')

        if self.main.chatMode:
            line.addText('enabled', self.colorGreen)
        else:
            line.addText('disabled', self.colorRed)
        
        line.addText('.')
        self.main.consoleBox.log(line)
    
    def cmd_players(self, cols=3):
        """Print a list of player's id and nickname.

        Args:
            cols (int, optional): Number of columns to split the players into. Defaults to 3.
        """
        # setup fields and find the longest column
        components = []
        longest = 0
        fmt = '(%s) %s'
        for player in self.main.gameState.getPlayers():
            login = player['Login']
            if 'NickName' in player:
                nick = player['NickName']
            else:
                nick = '<unknown>'
            
            components.append({
                'login': login,
                'nick': nick
            })

            longest = max(longest, len(fmt % (str(login), str(player['NickName']))))
        
        longest += 1

        # sort players alphabetically
        components.sort(key=lambda x: x['nick'])

        # build lines in n columns
        i = 0
        lines = []
        for component in components:
            if i % cols == 0:
                lines.append(LineBuilder(False))
            
            line = lines[-1]
            length = len(fmt % (str(component['login']), str(component['nick'])))
            fill = ' '*(longest - length)
            
            line.addText('(')
            line.addText(component['login'], self.colorGreen)
            line.addText(') ')
            line.addText(component['nick'])
            line.addText(fill)

            i += 1
        
        # finally, output the lines
        for line in lines:
            self.main.consoleBox.custom('', self.colorWhite, line)
        self.main.consoleBox.scrollbottom()
    
    def cmd_togglejoinleave(self):
        """Enable showing of join/leave messages.
        """
        state = not self.main.consoleBox.getEnableShowJoinAndLeave()
        self.main.consoleBox.enableShowJoinAndLeave(state)
        line = LineBuilder()
        line.addText('Showing of join/leave messages ')

        if state:
            line.addText('enabled', self.colorGreen)
        else:
            line.addText('disabled', self.colorRed)
        
        line.addText('.')
        self.main.consoleBox.log(line)
