import logging

logger = logging.getLogger('clifga')

class Commands:
    def __init__(self, main):
        self.cmds = dict()
        self.main = main

        self._register('help', self.cmd_help, 'Show this help message.')
        self._register('exit', self.cmd_exit, 'Close the session and the application.')
        #self._register('togglecallbacks', self.cmd_togglecallbacks, 'Toggle automatic display callbacks from the server.')
        #self._register('togglechat', self.cmd_togglechat, 'Toggle dispalying of parsed chat messages.')
        #self._register('setname', self.cmd_setname, 'Set your chat name.')
        #self._register('chat', self.cmd_chat, 'Send a chat message.')
    
    def _register(self, name, func, desc=''):
        self.cmds[name] = {
            'func': func,
            'desc': desc
        }
    
    def callIfExists(self, name, *args):
        logger.debug(name)
        if name in self.cmds:
            self.cmds[name]['func'](*args)
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
        self.main.remote.stop()

        # notify stop
        self.main._mainLoopEnabled = False
