"""
Advanced command parser that parses multiple input types like integers, floats, 
arrays, strings and dicts/maps and converts them into their approriate python type.

Author:
    snixtho
"""

import enum

class TokenType(enum.Enum):
    Unknown = enum.auto()
    Number = enum.auto()
    String = enum.auto()
    Identifier = enum.auto()
    ArrayStart = enum.auto()
    ArrayEnd = enum.auto()
    ArraySeparator = enum.auto()
    Boolean = enum.auto()
    Whitespace = enum.auto()

class Token:
    """Base token.
    """
    def __init__(self, tokenType, pos):
        self.type = tokenType
        self.pos = pos

class WhitespaceToken(Token):
    """Any whitespace.
    """
    def __init__(self, value, pos):
        super(WhitespaceToken, self).__init__(TokenType.Whitespace, pos)
        self.value = value
    
    @staticmethod
    def IsWhitespace(c):
        return c <= ' '
    
    @staticmethod
    def Parse(tokenizer):
        whitespace = tokenizer.peekForward()
        tokenizer.forward()

        return WhitespaceToken(whitespace, tokenizer.position() - 1)

class IdentifierToken(Token):
    """A individual alpha-dot string.
    """
    def __init__(self, value, pos):
        super(IdentifierToken, self).__init__(TokenType.Identifier, pos)
        self.value = value
    
    @staticmethod
    def IsValidChar(c):
        return (c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z') or c == '.'

    @staticmethod
    def Parse(tokenizer):
        identifier = ''

        while tokenizer.hasNext():
            c = tokenizer.peekForward()
            if not IdentifierToken.IsValidChar(c):
                break

            identifier += c
            tokenizer.forward()

        return IdentifierToken(identifier, tokenizer.position() - len(identifier))

class NumberToken(Token):
    """A pos/neg integer or float.
    """
    def __init__(self, value, pos):
        super(NumberToken, self).__init__(TokenType.Number, pos)
        self.value = value
    
    @staticmethod
    def IsDigit(c):
        return c >= '0' and c <= '9'

    @staticmethod
    def Parse(tokenizer):
        isFloat = False
        num = ''
        neg = False

        if tokenizer.hasNext() and tokenizer.peekForward() == '-':
            neg = True
            tokenizer.forward()

        while tokenizer.hasNext():
            c = tokenizer.peekForward()

            if c != '.' and not NumberToken.IsDigit(c):
                break

            if c == '.':
                if isFloat:
                    raise Exception('Invalid float number at pos %d.' % (tokenizer.i))
                isFloat = True
            
            num += c
            tokenizer.forward()
        
        if isFloat:
            parsednum = float(num)
        else:
            parsednum = int(num)
        
        if neg:
            parsednum = -parsednum
        
        return NumberToken(parsednum, tokenizer.position() - len(num))

class StringToken(Token):
    """A quote enclosed string.
    """
    def __init__(self, value, pos):
        super(StringToken, self).__init__(TokenType.String, pos)
        self.value = value
    
    @staticmethod
    def Parse(tokenizer):
        s = ''

        while tokenizer.hasNext():
            c = tokenizer.peekForward()
            tokenizer.forward()

            if c == '"' and (len(s) == 0 or s[-1] != '\\'):
                break

            s += c

        if not tokenizer.hasNext() and tokenizer.last() != '"':
            raise Exception('No end of string detected at pos %d.' % tokenizer.i)

        return StringToken(s, tokenizer.position() - len(s) - 2)

class BooleanToken(Token):
    """A bool, true or false.
    """
    def __init__(self, value, pos):
        super(BooleanToken, self).__init__(TokenType.Boolean, pos)
        self.value = value
    
    @staticmethod
    def Parse(tokenizer):
        if tokenizer.hasNext(4) and tokenizer.peekForward(4).lower() == 'true':
            tokenizer.forward(4)
            return BooleanToken(True, tokenizer.position() - 4)
        elif tokenizer.hasNext(5) and tokenizer.peekForward(5).lower() == 'false':
            tokenizer.forward(5)
            return BooleanToken(False, tokenizer.position() - 5)
        else:
            raise Exception('Invalid boolean token at %d.' % tokenizer.i)

class TokenIdentifier:
    """Identifies the token type in order for the tokenizer
    to parse the value correctly.
    """
    @staticmethod
    def Identify(tokenizer):
        """Identify the next token.
        """
        detectors = [
            [ TokenType.Whitespace,     TokenIdentifier.IsWhiteSpace,     0 ],
            [ TokenType.Number,         TokenIdentifier.IsNumber,         0 ],
            [ TokenType.String,         TokenIdentifier.IsString,         1 ],
            [ TokenType.ArrayStart,     TokenIdentifier.IsArrayStart,     1 ],
            [ TokenType.ArrayEnd,       TokenIdentifier.IsArrayEnd,       1 ],
            [ TokenType.ArraySeparator, TokenIdentifier.IsArraySeparator, 1 ],
            [ TokenType.Boolean,        TokenIdentifier.IsBoolean,        0 ],
            [ TokenType.Identifier,     TokenIdentifier.IsIdentifier,     0 ]
        ]

        for detector in detectors:
            if detector[1](tokenizer):
                return (detector[0], detector[2])
        
        return (TokenType.Unknown, 1)
    
    @staticmethod
    def IsNumber(tokenizer):
        if not tokenizer.hasNext():
            return False
        first = tokenizer.peekForward()
        if first == '-' and tokenizer.hasNext(2):
            return NumberToken.IsDigit(tokenizer.peekForward(2)[1])
        return NumberToken.IsDigit(first)

    @staticmethod
    def IsString(tokenizer):
        if not tokenizer.hasNext():
            return False
        return tokenizer.peekForward() == '"'
    
    @staticmethod
    def IsArrayStart(tokenizer):
        if not tokenizer.hasNext():
            return False
        return tokenizer.peekForward() == '['
    
    @staticmethod
    def IsArrayEnd(tokenizer):
        if not tokenizer.hasNext():
            return False
        return tokenizer.peekForward() == ']'
    
    @staticmethod
    def IsBoolean(tokenizer):
        if tokenizer.hasNext(4) and tokenizer.peekForward(4) == 'true':
            return True
        if tokenizer.hasNext(5) and tokenizer.peekForward(5) == 'false':
            return True
        return False

    @staticmethod
    def IsIdentifier(tokenizer):
        if not tokenizer.hasNext():
            return False
        return IdentifierToken.IsValidChar(tokenizer.peekForward())

    @staticmethod
    def IsArraySeparator(tokenizer):
        if not tokenizer.hasNext():
            return False
        return tokenizer.peekForward() == ','
    
    @staticmethod
    def IsWhiteSpace(tokenizer):
        if not tokenizer.hasNext():
            return False
        return WhitespaceToken.IsWhitespace(tokenizer.peekForward())

class Tokenizer:
    """Lexer for splitting input into tokens.
    """
    def __init__(self, rawCommand):
        self.rawCommand = rawCommand
        self.i = 0
    
    def reset(self):
        """Reset the buffer.
        """
        self.i = 0
    
    def hasNext(self, n=1):
        """Whether the buffer has more characters.

        Args:
            n (int, optional): Num characters to check for.. Defaults to 1.

        Returns:
            bool: True if n more chars exists, false if not.
        """
        return self.i < len(self.rawCommand)
    
    def peekForward(self, n=1):
        """Get the next n characters in the buffer.

        Args:
            n (int, optional): Num characters to retrieve. Defaults to 1.

        Returns:
            string: Characters retrieved.
        """
        return self.rawCommand[self.i : self.i + n]
    
    def forward(self, n=1):
        """Move the buffer n steps forward.

        Args:
            n (int, optional): [description]. Defaults to 1.
        """
        self.i += n
    
    def last(self):
        """Get the last character in the buffer.

        Returns:
            [type]: [description]
        """
        return self.rawCommand[-1]
    
    def position(self):
        """Get the current position in the buffer.

        Returns:
            [type]: [description]
        """
        return self.i
    
    def tokenize(self):
        """Split the raw command into tokens.

        Raises:
            Exception: [description]
        """
        self.tokens = []

        while self.hasNext():
            #if self.peekForward() == ' ':
            #    self.forward()
            #    continue

            tokenType, advance = TokenIdentifier.Identify(self)

            if advance > 0:
                self.forward(advance)
            
            # throw on unknown tokens.
            if tokenType == TokenType.Unknown:
                raise Exception('Unknown token at pos %d near "%s".' % (int(self.i - advance), self.rawCommand[self.i-5:self.i+5]))

            # parse tokens with a value
            token = None
            if tokenType == TokenType.Identifier:
                token = IdentifierToken.Parse(self)
            elif tokenType == TokenType.Number:
                token = NumberToken.Parse(self)
            elif tokenType == TokenType.String:
                token = StringToken.Parse(self)
            elif tokenType == TokenType.Boolean:
                token = BooleanToken.Parse(self)
            elif tokenType == TokenType.Whitespace:
                token = WhitespaceToken.Parse(self)
            else:
                token = Token(tokenType, self.position() - advance)

            self.tokens.append(token)

class Parser:
    """Parses raw command text.
    """
    def __init__(self, rawCommand):
        self.rawCommand = rawCommand
        self.tokenizer = Tokenizer(rawCommand)

        self.i = 0

    def reset(self):
        """Reset the buffer.
        """
        self.i = 0
    
    def hasNext(self, n=1):
        """Whether the buffer has more characters.

        Args:
            n (int, optional): Num characters to check for.. Defaults to 1.

        Returns:
            bool: True if n more chars exists, false if not.
        """
        return self.i < len(self.tokenizer.tokens)
    
    def peekForward(self, n=1):
        """Get the next n characters in the buffer.

        Args:
            n (int, optional): Num characters to retrieve. Defaults to 1.

        Returns:
            string: Characters retrieved.
        """
        return self.tokenizer.tokens[self.i : self.i + n]
    
    def forward(self, n=1):
        """Move the buffer n steps forward.

        Args:
            n (int, optional): [description]. Defaults to 1.
        """
        self.i += n
    
    def _array(self):
        """Parse an array.

        Returns:
            array: The parsed array.
        """
        if not self.hasNext():
            raise Exception('Expected start of array, but nothing left to parse.')

        # check if first token is the start of an array
        firstToken = self.peekForward()[0]

        if firstToken.type != TokenType.ArrayStart:
            raise Exception('Start of array expected.')

        self.forward()

        arrayElements = []

        # parse array elements
        nelements = 0
        while self.hasNext():
            nextToken = self.peekForward()[0]

            if nextToken.type == TokenType.Whitespace:
                self.forward()
                continue

            # every odd element, there should be a comma separator
            if nelements % 2 == 1 and nextToken.type != TokenType.ArraySeparator and nextToken.type != TokenType.ArrayEnd:
                raise Exception('Array separator expected, instead got %s.'  % str(nextToken.type)[10:])

            # check if we have an actual element after a separator
            if nextToken.type == TokenType.ArraySeparator:
                if not self.hasNext(2):
                    raise Exception('Another array element expected.')
                self.forward()
                nelements += 1
                continue

            if nextToken.type == TokenType.ArrayEnd:
                break # end of array

            if nextToken.type == TokenType.ArrayStart:
                # sub array detected, parse it
                arrayElements.append(self._array())
                nelements += 1
                continue
            else:
                # add element value
                arrayElements.append(nextToken.value)
            
            self.forward()
            nelements += 1

        # check that we properly reached the end of the array
        if not self.hasNext() or self.peekForward()[0].type != TokenType.ArrayEnd:
            raise Exception('End of array expected.')
        self.forward()

        return arrayElements

    def parse(self):
        """Parse the provided expression and extract the 
        method name and its arguments into proper python types.

        Raises:

        Returns:
            tuple: Tuple with method name and an array of arguments.
        """
        command = ''
        args = []

        # get tokens
        self.tokenizer.tokenize()

        if not self.hasNext():
            raise Exception('Empty expression provided.')

        # check that first token is a identifier (xmlrpc method)
        firstToken = self.peekForward()[0]

        if firstToken.type == TokenType.Identifier:
            command = firstToken.value
        else:
            raise Exception('First token must be an identifier, not %s.' % str(firstToken.type)[10:])

        self.forward()

        # parse remaining tokens as method arguments
        while self.hasNext():
            nextToken = self.peekForward()[0]

            if nextToken.type == TokenType.Whitespace:
                self.forward()
                continue

            # we do not want unknown tokens
            if nextToken.type == TokenType.Unknown:
                raise Exception('Unknown token.')

            # check for invalid array syntax
            if nextToken.type == TokenType.ArraySeparator:
                raise Exception('Unexpected array separator.')
            if nextToken.type == TokenType.ArrayEnd:
                raise Exception('Unexpected end of array.')

            if nextToken.type == TokenType.ArrayStart:
                # array detected, parse it
                args.append(self._array())
            else:
                # append value of token
                args.append(nextToken.value)
                self.forward()
        
        return command, args
