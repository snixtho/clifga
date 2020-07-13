import curses
from curses.textpad import Textbox
import logging
import time
from .syntax import Tokenizer, TokenType, Parser
import threading
import math
import datetime

logger = logging.getLogger('clifga')


class LineBuilder:
    """Builds a line with styling and can output it.
    """
    def __init__(self, spacefill=True):
        self.parts = []
        self.spacefill = spacefill
        
        # gui speed optimization
        self.fulltextCache = None
    
    def addText(self, text, colorpair=1, attrib=None):
        """Add a text component with or without individual styling to the end
        of the line.

        Args:
            text (string): Text to append.
            colorpair (int, optional): The color pair ID to use. Defaults to 1.
            attrib ([type], optional): [description]. Defaults to None.

        Returns:
            [type]: [description]
        """
        self.parts.append({
            'text': text,
            'attrib': attrib,
            'color': colorpair
        })

        self.fulltextCache = None
        return self
    
    def prependText(self, text, colorpair=1, attrib=None):
        """Add a text component with or without individual styling to the start
        of the line.

        Args:
            text (string): Text to append.
            colorpair (int, optional): The color pair ID to use. Defaults to 1.
            attrib ([type], optional): [description]. Defaults to None.

        Returns:
            [type]: [description]
        """
        self.parts = [{
            'text': text,
            'attrib': attrib,
            'color': colorpair
        }] + self.parts

        self.fulltextCache = None
        return self
    
    def output(self, x, y, screen):
        """Output the buffer at the provided position
        on a screen object.

        Args:
            x (int): [description]
            y (int): [description]
            screen ([type]): [description]
        """
        l = 0
        for part in self.parts:
            screen.addstr(y, x + l, part['text'], curses.color_pair(part['color']))
            l += len(part['text'])
        
        # get current screen width for finding remaining space
        _, width = screen.getmaxyx()

        # fill remaining space with whitespaces.
        spaces = ' '*(width-l-x-1)
        screen.addstr(y, x+l, spaces)
    
    def fullText(self):
        """Get the plain-text of the internal buffer.
        Complexity: O(n-parts)

        Returns:
            [type]: [description]
        """
        if self.fulltextCache is None:
            self.fulltextCache = ''
            for part in self.parts:
                self.fulltextCache += part['text']
        return self.fulltextCache
    
    def wrapLines(self, maxWidth):
        """Perform line wrapping in between a specific width.
        and return one or multiple line builders that has equal
        or less output length to the provided max width.

        Args:
            maxWidth (int): Maximum number of characters per line.

        Returns:
            [type]: [description]
        """
        lines = [LineBuilder(self.spacefill)]
        currLineWidth = 0

        for part in self.parts:
            partlen  = len(part['text'])

            if partlen + currLineWidth > maxWidth:
                # line is bigger than provided width, so split it
                remainingText = part['text']
                i = 0
                while len(remainingText) + currLineWidth > maxWidth:
                    # remaining length after filling up the rest of the line
                    remainingLen = len(remainingText)
                    remaining = remainingLen + currLineWidth - maxWidth

                    # fill up the line up to the max width
                    lines[-1].addText(remainingText[:remainingLen - remaining], part['color'], part['attrib'])
                    lines.append(LineBuilder(self.spacefill))

                    # get remaining text
                    remainingText = remainingText[remainingLen - remaining:]
                    currLineWidth = 0
                    i += 1
                
                remainingLen = len(remainingText)
                if remainingLen > 0:
                    # still some remaining text, so add it to the new line created
                    currLineWidth = remainingLen
                    lines[-1].addText(remainingText, part['color'], part['attrib'])
            else:
                lines[-1].addText(part['text'], part['color'], part['attrib'])
                currLineWidth += partlen

        return lines
    
    def addLineBuilder(self, builder):
        """Append the buffer of another line builder to this one.

        Args:
            builder (LineBuilder): The other LineBuilder to append.
        """
        for part in builder.parts:
            self.parts.append(part)
        self.fulltextCache = None

class ColorPairMaker:
    """A static class that tracks colorpair ids and
    can be used to create new ones without having to worry
    about tracking the number of pairs created.
    """
    CURR_INDEX = 2

    @staticmethod
    def MakeColorPair(foreground, background=curses.COLOR_BLACK):
        """Create a new curses colorpair.

        Args:
            foreground (int): The foreground color to set.
            background (int, optional): Background color to set. Defaults to curses.COLOR_BLACK.

        Returns:
            int: The index of the new color pair.
        """
        index = ColorPairMaker.CURR_INDEX
        curses.init_pair(ColorPairMaker.CURR_INDEX, foreground, background)
        ColorPairMaker.CURR_INDEX += 1
        return index

class SyntaxHighlighter:
    """Highlight the syntax of some text corresponding to
    the command syntax of clifga.
    """
    ColorString = None
    ColorNumber = None
    ColorBoolean = None
    ColorIdentifier = None

    __ins = None

    def __init__(self):
        SyntaxHighlighter.ColorString = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
        SyntaxHighlighter.ColorNumber = ColorPairMaker.MakeColorPair(curses.COLOR_MAGENTA)
        SyntaxHighlighter.ColorBoolean = ColorPairMaker.MakeColorPair(curses.COLOR_BLUE)
        SyntaxHighlighter.ColorIdentifier = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)

    @staticmethod
    def highlight(tokens):
        """Highlight the tokenized text.

        Args:
            tokens (array): Tokens generated from the tokenizer.

        Returns:
            LineBuilder: Styled text using the LineBuilder.
        """
        if SyntaxHighlighter.__ins is None:
            SyntaxHighlighter.__ins = SyntaxHighlighter()

        line = LineBuilder(False)

        for token in tokens:
            if token.type == TokenType.Number:
                line.addText(str(token.value), SyntaxHighlighter.ColorNumber)
            if token.type == TokenType.String:
                line.addText('"%s"' % str(token.value), SyntaxHighlighter.ColorString)
            if token.type == TokenType.Identifier:
                line.addText(str(token.value), SyntaxHighlighter.ColorIdentifier)
            if token.type == TokenType.ArrayStart:
                line.addText('[')
            if token.type == TokenType.ArrayEnd:
                line.addText(']')
            if token.type == TokenType.ArraySeparator:
                line.addText(',')
            if token.type == TokenType.Boolean:
                line.addText(str(token.value), SyntaxHighlighter.ColorBoolean)
            if token.type == TokenType.Whitespace:
                line.addText(str(token.value))
        
        return line

class InputBoxLogic:
    """Controls the cmd input box.
    """
    def __init__(self):
        self.cursor = 0
        self.text = ''
    
    def insertChar(self, c):
        """Insert one character.

        Args:
            c (int): Character code representing the character.
        """
        if type(c) is int:
            c = chr(c)

        self.text = self.text[0:self.cursor] + c + self.text[self.cursor:]
        self.cursor += 1
    
    def performBackspace(self):
        """Perform a backspace operation on the cursor position.
        """
        if self.cursor == 0:
            # ignore if we're already in the start
            return

        self.text = self.text[0:self.cursor-1] + self.text[self.cursor:]
        self.cursor -= 1
    
    def performDelete(self):
        """Perform a delete key operation on the current cursor position.
        """
        if self.cursor == len(self.text):
            return
        
        self.text = self.text[0:self.cursor] + self.text[self.cursor+1:]
    
    def cursorLeft(self):
        """Move the cursor one step left.
        """
        if self.cursor-1 >= 0:
            self.cursor -= 1
    
    def cursorRight(self):
        """Move the cursor one step to the right.
        """
        if self.cursor+1 <= len(self.text):
            self.cursor += 1
    
    def setText(self, text):
        """Overwrite and set the buffer text.

        Args:
            text (string): String to set.
        """
        self.text = text
        self.cursor = len(text)
    
    def reset(self):
        """Clear buffer and reset cursor.
        """
        self.cursor = 0
        self.text = ''

class BaseWidget:
    """Base widget for all UI widgets.
    """
    def __init__(self, screen, x, y):
        self.x = x
        self.y = y
        self.screen = screen
    
    def handle_input(self, c):
        """Handle a character generated by a key press.

        Args:
            c (int): [description]
        """
        pass
    
    def draw(self):
        """Draw the widget on screen.
        """
        pass

class CommandInputBox(BaseWidget):
    """Widget for command input.
    """
    def __init__(self, screen, baseX, baseY, width, remote):
        super(CommandInputBox, self).__init__(screen, baseX, baseY)
        self.inputLogic = InputBoxLogic()
        self.width = width
        self.hasAction = False
        self.suggested = ''

        self.availableMethods = remote.call('system.listMethods')
        self.colorSuggestion = ColorPairMaker.MakeColorPair(curses.COLOR_BLUE)
        self.colorError = ColorPairMaker.MakeColorPair(curses.COLOR_RED)

        self.loading = False
        self.loadingLastTime = 0

        self.log = []
        self.logpos = 0
    
    def suggestCommand(self, search):
        """Suggest a command based on the search keyword.

        Args:
            search (string): String to search for.
        """
        if search != '':
            for cmd in self.availableMethods:
                if search == cmd[0:len(search)]:
                    self.suggested = cmd
                    return
        
        self.suggested = ''
    
    def _movelog(self, amount):
        """Move through command log by an amount.

        Args:
            amount (int): How much to move, forward or backwards (neg. number)
        """
        if len(self.log) == 0:
            return
        
        self.logpos += amount

        if self.logpos < 0:
            self.logpos = 0
        
        if self.logpos >= len(self.log):
            self.logpos = len(self.log)
            self.inputLogic.text = ''
            self.suggestCommand('')
            return
        
        self.suggestCommand(self.log[self.logpos])
        self.inputLogic.text = self.log[self.logpos]

    def handle_input(self, c):
        if self.loading:
            return
        
        if c >= 32 and c <= 126: # insert printable chars
            self.inputLogic.insertChar(c)
            self.suggestCommand(self.inputLogic.text)
        elif c == curses.KEY_LEFT: # move cursor left
            self.inputLogic.cursorLeft()
        elif c == curses.KEY_RIGHT: # move cursor right
            self.inputLogic.cursorRight()
        elif c == curses.KEY_BACKSPACE: # remove 1 char backwards
            self.inputLogic.performBackspace()
            self.suggestCommand(self.inputLogic.text)
        elif c == 330: # remove 1 char forward
            self.inputLogic.performDelete()
            self.suggestCommand(self.inputLogic.text)
        elif c == ord('\n'): # ENTER (send command)
            self.hasAction = True
        elif c == ord('\t'): # TAB (complete suggestion)
            self.suggestCommand(self.inputLogic.text)
            self.inputLogic.setText(self.suggested)
        elif c == curses.KEY_UP: # move backwards in cmd log
            self._movelog(-1)
        elif c == curses.KEY_DOWN: # move forward in cmd log
            self._movelog(1)
    
    def clear(self):
        """Reset the input box.
        """
        self.inputLogic.reset()
        self.hasAction = False
    
    def setCursor(self):
        """Set the cursor depending on loading or not.
        """
        if not self.loading:
            self.screen.move(self.y, self.x + self.inputLogic.cursor)
        else:
            self.screen.move(self.y, 0)
    
    def setLoading(self, loading=True):
        """Set the state to loading.

        Args:
            loading (bool, optional): [description]. Defaults to True.
        """
        self.loading = loading
        if loading:
            self.loadingLastTime = time.time()

    def draw(self, chatMode=False):
        if not self.loading:
            inptext = self.inputLogic.text
            stripped = ''

            try:
                dontparse = False
                if chatMode:
                    dontparse = True
                    if len(inptext) > 0 and inptext[0] == '/':
                        inptext = inptext[1:]
                        stripped = '/'
                        dontparse = False

                # Run whole parser to check syntax as well
                if not dontparse:
                    parser = Parser(inptext)
                    parser.parse()
                    line = SyntaxHighlighter.highlight(parser.tokenizer.tokens)
                else:
                    line = LineBuilder()
                    line.addText(inptext)
            except Exception as e:
                # invalid syntax
                line = LineBuilder()
                line.addText(inptext, self.colorError)

            line.prependText(stripped)

            # draw suggestion
            if self.suggested is not None:
                line.addText(self.suggested[len(inptext):], self.colorSuggestion)

            self.screen.move(self.y, self.x)
            # self.screen.addstr(self.y, self.x, self.inputLogic.text)
            line.output(self.x, self.y, self.screen)
            self.setCursor()
        else:
            indicator = [
                'Sending ...', '>ending  ..', 'S>nding . .', 'Se>ding .. ',
                'Sen>ing ...', 'Send>ng  ..', 'Sendi>g . .', 'Sendin> .. ',
                'Sending>...', 'Sending >..', 'Sending .>.', 'Sending ..>',
                ][round(time.time()*10)%12]
            self.screen.addstr(self.y, self.x, indicator)
    
    def action(self, removeAction=True):
        """Check whether the input box has a action. It returns
        true if the user has pressed enter.

        Args:
            removeAction (bool, optional): Set action state to false if its true. Defaults to True.

        Returns:
            bool: True if action, false if not.
        """
        if not self.hasAction:
            return None

        text = self.inputLogic.text

        # add cmd to log
        if len(self.log) == 0 or text != self.log[-1]:
            self.log.append(text)
        self.logpos = len(self.log)

        if removeAction:
            self.hasAction = False
        return text

class InfoView(BaseWidget):
    """Show basic info about the server and connection.
    """
    def __init__(self, screen, x, y, state, connInfo, main):
        super(InfoView, self).__init__(screen, x, y)
        self.state = state
        self.maxPlayers = None
        self.connInfo = connInfo
        self.main = main

        self.colorConnected = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
        self.colorUser = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)
        self.colorHost = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)
        self.colorPort = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
        self.colorPlayers = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)
        self.colorMaxPlayers = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
    
    def draw(self):
        if self.maxPlayers is None:
            self.maxPlayers = self.state.remote.call('GetMaxPlayers')

        remoteInfo = LineBuilder()
        remoteInfo.addText('GBXRemote')
        remoteInfo.addText(' ~ ')
        remoteInfo.addText('Connected', self.colorConnected)
        remoteInfo.addText(' | ')
        remoteInfo.addText(str(self.connInfo['username']), self.colorUser)
        remoteInfo.addText('@')
        remoteInfo.addText(str(self.connInfo['host']), self.colorHost)
        remoteInfo.addText(':')
        remoteInfo.addText(str(self.connInfo['port']), self.colorPort)
        remoteInfo.addText(' | ')
        remoteInfo.addText('Players: ')
        remoteInfo.addText(str(self.state.getPlayerCount()), self.colorPlayers)
        remoteInfo.addText('/')
        remoteInfo.addText(str(self.maxPlayers['CurrentValue']), self.colorMaxPlayers)

        if self.main.chatMode:
            remoteInfo.addText(' | Chat Mode Enabled')

        remoteInfo.output(0, self.y, self.screen)

class ConsoleBox(BaseWidget):
    """Console view that shows formatted and styled logs.
    """
    LogTypeInfo = 0
    LogTypeError = 1

    def __init__(self, screen, x, y, width, height, state, maxLogs=100):
        super(ConsoleBox, self).__init__(screen, x, y)
        self.width = width
        self.height = height
        
        # scroll functionality
        self.scroll = 0
        self.updatescroll = False

        # logs and state
        self.logs = []
        self.maxLogs = maxLogs
        self.logsLock = threading.RLock()
        self.state = state

        # styling
        self.colorLog = ColorPairMaker.MakeColorPair(curses.COLOR_CYAN)
        self.colorError = ColorPairMaker.MakeColorPair(curses.COLOR_RED)
        self.colorWarning = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)

        self._colorchat = ColorPairMaker.MakeColorPair(curses.COLOR_MAGENTA)
        self._colorchat2 = ColorPairMaker.MakeColorPair(curses.COLOR_GREEN)
        
        self.colorTime = ColorPairMaker.MakeColorPair(curses.COLOR_BLUE)

        # gbxremote callback registrations
        self.state.remote.registerCallback('*', self.handle_callback)
        self.showcallbacks = False
        self.showcallbacksLock = threading.RLock()

        self.state.remote.registerCallback('ManiaPlanet.PlayerChat', self.handle_chat)
        self.showchat = False
        self.showchatLock = threading.RLock()
    
    def log(self, text):
        """Send a INFO log message to the console.

        Args:
            text (string): Text of the log msg.
        """ 
        self.custom('Info', self.colorLog, text)
    
    def error(self, text):
        """Send a ERROR log message to the console.

        Args:
            text (string): Text of the log msg.
        """
        self.custom('Error', self.colorError, text)
    
    def custom(self, typestr, color, text):
        """Send a custom log message to the console.

        Args:
            typestr (string): Type of the.
            color (color pair): The color of the log type.
            text (string): Text of the log, can be a LineBuilder for further styling.
        """
        with self.logsLock:
            self.logs.append({
                'text': text,
                'typestr': typestr,
                'color': color
            })

            if len(self.logs) > self.maxLogs:
                self.logs = self.logs[1:]
            
            self.updatescroll = True
    
    def handle_callback(self, method, *args):
        """Shows all callbacks if toggled.
        """
        with self.showcallbacksLock:
            if not self.showcallbacks:
                return

        self.custom('Callback:'+method, self.colorWarning, str(args))
        self.scrollbottom()
    
    def _logChat(self, login, nickname, text):
        """Send a chat message to the console.

        Args:
            login (string): Login of the player.
            nickname (string): Nickname of the player.
            text (string): The chat message.
        """

        t = datetime.datetime.now().strftime('%H:%M:%S')

        line = LineBuilder()
        line.addText('[%s] ' % str(t), self.colorTime)
        line.addText('[')
        line.addText(login, self._colorchat2)
        line.addText('] ')
        line.addText(nickname, self.colorLog)
        line.addText(': ')
        line.addText(text)
        self.custom('Chat', self._colorchat, line)

    def handle_chat(self, playerUid, login, text, isRegisteredCmd):
        """Parse incoming chat message callbacks.

        Args:
            playerUid ([type]): [description]
            login ([type]): [description]
            text ([type]): [description]
            isRegisteredCmd (bool): [description]
        """
        with self.showchatLock:
            if not self.showchat:
                return
        
        player = self.state.getPlayerByLogin(login)
        nickname = player['NickName'] if player is not None else '<unknown>'
        self._logChat(login, nickname, text)
        self.scrollbottom()
    
    def enableShowcallbacks(self, enable=True):
        """Enable/Disable showing of callbacks in the console.

        Args:
            enable (bool, optional): [description]. Defaults to True.
        """
        with self.showcallbacksLock:
            self.showcallbacks = enable
    
    def getEnableShowcallbacks(self, enable=True):
        """Get whether the console is showing callbacks or not.

        Args:
            enable (bool, optional): [description]. Defaults to True.

        Returns:
            bool: True if showing, false if not.
        """
        with self.showcallbacksLock:
            return self.showcallbacks
    
    def enableShowChat(self, enable=True):
        """Enable/Disable showing of chat in the console.

        Args:
            enable (bool, optional): [description]. Defaults to True.
        """
        with self.showchatLock:
            self.showchat = enable
    
    def getEnableShowChat(self, enable=True):
        """Get whether the console is showing chat or not.

        Args:
            enable (bool, optional): [description]. Defaults to True.

        Returns:
            bool: True if showing, false if not.
        """
        with self.showchatLock:
            return self.showchat

    def handle_input(self, c):
        if c < 0:
            return
        
        if c == curses.KEY_F1: # scroll upwards
            if self.scroll -1 >= 0:
                self.scroll -= 1
            self.updatescroll = True
        elif c == curses.KEY_F2: # scroll downwards
            self.scroll += 1
            self.updatescroll = True
    
    def scrollbottom(self):
        """Scroll to the last log message.
        """
        self.scroll = -1
        self.updatescroll = True

    def draw(self):
        lines = []

        if self.updatescroll:
            self.screen.erase()
            self.updatescroll = False

        # prepare lines
        with self.logsLock:
            for log in self.logs:
                line = LineBuilder()
                line.addText('[')
                line.addText(log['typestr'], log['color'])
                line.addText('] ')

                if type(log['text']) is str:
                    line.addText(log['text'])
                else:
                    line.addLineBuilder(log['text'])

                outLines = line.wrapLines(self.width - self.x - 2)
                for outline in outLines:
                    lines.append(outline)

        i = 0

        # find out which lines to poutput
        if self.scroll > len(lines) - self.height:
            self.scroll = len(lines) - self.height

        if self.scroll < 0:
            linesStart = len(lines) - self.height if len(lines) > self.height else 0
            self.scroll = linesStart
        else:
            linesStart = self.scroll

        # draw log lines
        for line in lines[linesStart:linesStart + self.height]:
            if i+1 <= self.height:
                line.output(self.x, self.y + i, self.screen)
                i += 1
        
        # draw scroll view
        if len(lines) - self.height <= 0:
            scbarpos = 0
        else:
            scbarpos = round((linesStart)/(len(lines) - self.height)*(self.height - 3))

        self.screen.addstr(self.y, self.width-1, '▲')
        self.screen.addstr(self.y + scbarpos + 1, self.width-1, '█')
        self.screen.addstr(self.y+self.height-1, self.width-1, '▼')

class SelectionList(BaseWidget):
    """Menu with items a user can select from.
    """
    def __init__(self, screen, x, y, width, height):
        super(SelectionList, self).__init__(screen, x, y)
        self.width = width
        self.height = height

        self.options = []
        self.selection = 0
        self.selected = False

        self.colorTitle = ColorPairMaker.MakeColorPair(curses.COLOR_YELLOW)
    
    def addOption(self, title, value):
        """Add a menu option.

        Args:
            title (string): Title of the option.
            value (object): Any object you'd like that will be attached to the item.
        """
        self.options.append({
            'value': value,
            'title': title
        })

        self.screen.erase()
    
    def handle_input(self, c):
        if c == curses.KEY_UP: # move up in the list
            if self.selection > 0:
                self.selection -= 1
            self.screen.erase()
        elif c == curses.KEY_DOWN: # move down in the list
            if self.selection + 1 < len(self.options):
                self.selection += 1
            self.screen.erase()
        elif c == ord('\n'): # select current item
            logger.debug('enters')
            self.selected = True
    
    def hasSelected(self):
        """Check if the user has performed the selection action.

        Returns:
            bool: True if selected, false if not.
        """
        if self.selected:
            self.selected = False
            return True
        return False

    def draw(self):
        middleX = self.x + round(self.width/2)
        middleY = self.y = round(self.height/2)

        maxOptionsWidth = 0
        for option in self.options:
            rawLineText = '> ' + option['title']
            maxOptionsWidth = max(maxOptionsWidth, len(rawLineText))
        
        startX = middleX - round(maxOptionsWidth/2)
        startY = middleY - round(len(self.options)/2) - 2
        
        i = 0
        for option in self.options:
            line = LineBuilder()
            
            if i == self.selection:
                line.addText('> ')
            else:
                line.addText('  ')
            
            line.addText(option['title'], self.colorTitle)
            line.output(startX, startY + i, self.screen)

            i += 1
        
        infotext = 'Use arrow UP/DOWN to move through the list, ENTER to accept.'
        infoX = self.x + round((self.width - len(infotext))/2)
        self.screen.addstr(startY + 2 + len(self.options), infoX, infotext)
