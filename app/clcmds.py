import argparse
import json
from .trackmania.gbxremote import DedicatedRemote
from .syntax import Parser
import socket

# load config
config = json.load(open('config.json', 'r'))

class SimpleOutput:
    @staticmethod
    def Info(msg):
        print('[+] %s' % msg)
    
    @staticmethod
    def Error(msg):
        print('[-] %s' % msg)
    
    @staticmethod
    def NoLine(msg):
        print(msg, end="")

    @staticmethod
    def Line(msg):
        print(msg)
    
    @staticmethod
    def ExitMessage(msg, code=0):
        SimpleOutput.Line(msg)
        exit(code)

class CLCMDHandler:
    _parser = argparse.ArgumentParser(description='Clifga Command-Line utilities.')
    _subparsers = None
    _cmds = {}

    @staticmethod
    def Check():
        if CLCMDHandler._subparsers is None:
            CLCMDHandler._subparsers = CLCMDHandler._parser.add_subparsers(dest='cmd')
        
        args = CLCMDHandler._parser.parse_args()
        if args.cmd in CLCMDHandler._cmds:
            try:
                CLCMDHandler._cmds[args.cmd](args)
            finally:
                return True
        
        return False

    @staticmethod
    def AddCommand(name, description, method):
        if CLCMDHandler._subparsers is None:
            CLCMDHandler._subparsers = CLCMDHandler._parser.add_subparsers(dest='cmd')

        CLCMDHandler._cmds[name] = method

        cmd_parser = CLCMDHandler._subparsers.add_parser(name, help=description)
        return cmd_parser

def Cmd_CallMethod(args):
    for server in config['servers']:
        # check if we want to connect to this server
        isServer = False
        for serverName in args.servers:
            if serverName == server['name']:
                isServer = True
                break
        
        if not isServer:
            continue

        SimpleOutput.NoLine('%s: ' % server['name'])
        
        remote = DedicatedRemote(
            server['connection']['host'], 
            server['connection']['port'], 
            server['connection']['username'], 
            server['connection']['password']
        )

        try:
            # parse call
            callparser = Parser(args.call)
            method, methodargs = callparser.parse()

            # connect to server and send call
            if not remote.connect(0):
                raise Exception('Connection refused.')

            result = remote.call(method, *methodargs)
            SimpleOutput.Line(str(result))
        except Exception as e:
            SimpleOutput.Error('Error Occured: %s' % str(e))
        finally:
            remote.stop()

def Cmd_FreezeCheck(args):
    CODE_NOTFROZEN = ('NOT FROZEN', 0)
    CODE_FROZEN = ('FROZEN', 1)
    CODE_DOWN = ('DOWN', 2)
    CODE_NOHOST = ('HOST NOT RESOLVED', 3)
    
    xmlrpc_on = False
    game_on = False

    # resolve host
    try:
        resolved = socket.gethostbyname(args.host)
    except:
        SimpleOutput.ExitMessage(*CODE_NOHOST)

    # check xmlrpc
    try:
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.settimeout(0.5)
        s1.connect((resolved, int(args.xmlrpcport)))
        xmlrpc_on = True
    except:
        pass
    finally:
        s1.close()
    
    # check game
    try:
        s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s1.settimeout(0.5)
        s1.connect((resolved, int(args.gameport)))
        game_on = True
    except:
        pass
    finally:
        s1.close()
    
    # check states
    if game_on and xmlrpc_on:
        SimpleOutput.ExitMessage(*CODE_NOTFROZEN)

    if not game_on:
        SimpleOutput.ExitMessage(*CODE_DOWN)
    
    SimpleOutput.ExitMessage(*CODE_FROZEN)

# callmethod
parser = CLCMDHandler.AddCommand('callmethod', 'Call a XMLRPC method on a set of servers.', Cmd_CallMethod)
parser.add_argument('-c', '--call', help='The method call.', required=True)
parser.add_argument('-s', '--servers', nargs='+', help='The method call.', required=True)

# freezecheck
parser = CLCMDHandler.AddCommand('freezecheck', 'Check if a server is frozen. Will exit with code 1 if frozen, 0 if not, 2 if the game server is down and 3 if host cannot be resolved.', Cmd_FreezeCheck)
parser.add_argument('-i', '--host', help='The host address to the server.', required=True)
parser.add_argument('-x', '--xmlrpcport', help='The XMLRPC port to use.', required=True)
parser.add_argument('-g', '--gameport', help='The game port to use.', required=True)
