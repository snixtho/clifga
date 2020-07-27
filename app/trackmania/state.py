from enum import Enum
import time
import threading
import math
import logging
import xmlrpc.client

logger = logging.getLogger('clifga')

class GameStateTracker:
    def __init__(self, remote, maxChatLines=50):
        self.players = []
        self.playersLock = threading.RLock()

        self.playersCache = dict()
        self.playersCacheLock = threading.RLock()

        self.chat = []
        self.chatLock = threading.RLock()

        self.matchStart = 0
        self.matchStartLock = threading.RLock()

        self.remote = remote
        
        self.maxChatLines = maxChatLines

        self.remote.registerCallback('ManiaPlanet.PlayerChat', self.on_player_chat)
        self.remote.registerCallback('ManiaPlanet.PlayerConnect', self.on_player_connect)
        self.remote.registerCallback('ManiaPlanet.PlayerDisconnect', self.on_player_disconnect)
        self.remote.registerCallback('ManiaPlanet.BeginMatch', self.on_begin_match)
        self.remote.registerCallback('ManiaPlanet.EndMatch', self.on_end_match)
        self.remote.registerCallback('ManiaPlanet.BeginMap', self.on_begin_map)
        self.remote.registerCallback('ManiaPlanet.EndMap', self.on_end_map)

        self.remote.registerCallback('ManiaPlanet.StatusChanged', self.on_status_changed)
        self.remote.registerCallback('ManiaPlanet.PlayerCheckpoint', self.on_player_checkpoint)
        self.remote.registerCallback('ManiaPlanet.PlayerFinish', self.on_player_finish)
        self.remote.registerCallback('ManiaPlanet.MapListModified', self.on_map_list_modified)
        self.remote.registerCallback('ManiaPlanet.PlayerInfoChanged', self.on_player_info_changed)
    
    def initialize(self):
        with self.playersLock:
            index = 0
            players = self.remote.call('GetPlayerList', 50, index, 0)
            while players and type(players) is not xmlrpc.client.Fault and len(players) > 0:
                for player in players:
                    self.players.append(player['Login'])
                    self.playersCache[player['Login']] = player
                
                index += 51
                players = self.remote.call('GetPlayerList', 50, index, 0)

    def on_player_connect(self, login, isSpectator):
        with self.playersLock:
            if login not in self.players:
                self.players.append(login)
    
    def on_player_disconnect(self, login, disconnectReason):
        with self.playersLock:
            logger.debug(login)
            logger.debug(login in self.players)
            logger.debug(self.players)
            if login in self.players:
                self.players.remove(login)
            logger.debug(login in self.players)

    def on_player_chat(self, playerUid, login, text, isRegisteredCmd):
        with self.chatLock:
            nickName = self.getPlayerByLogin(login)

            self.chat.append({
                'login': login,
                'nickname': nickName,
                'message': text
            })

            if len(self.chat) > self.maxChatLines:
                self.chat = self.chat[1:]
    
    def on_begin_match(self):
        with self.matchStartLock:
            self.matchStart = math.floor(time.time())

    def on_end_match(self, rankings, winnerTeam):
        pass

    def on_begin_map(self, map):
        pass

    def on_end_map(self, map):
        pass
    
    def on_status_changed(self, statusCode, statusName):
        pass

    def on_player_checkpoint(self, playerUid, login, timeOrScore, curLap, checkpointIndex):
        pass

    def on_player_finish(self, playerUid, login, timeOrScore):
        pass

    def on_map_list_modified(self, currMapIndex, nextMapIndex, isListModified):
        pass

    def on_player_info_changed(self, playerInfo):
        with self.playersLock:
            if playerInfo['Login'] not in self.players:
                self.players.append(playerInfo['Login'])
            self.playersCache[playerInfo['Login']] = playerInfo
    
    def getChat(self):
        chatLines = []
        with self.chatLock:
            for msg in self.chat:
                chatLines.append({'name': msg['nickname'], 'msg': msg['message']})
        return chatLines
    
    def getPlayerByLogin(self, login):
        with self.playersCacheLock:
            if login in self.playersCache:
                return self.playersCache[login]
        
        return None
    
    def getMatchStart(self):
        with self.matchStartLock:
            return self.matchStart
    
    def getPlayerCount(self):
        with self.playersLock:
            return len(self.players)
    
    def getPlayers(self):
        players = []
        with self.playersLock:
            for player in self.players:
                with self.playersCacheLock:
                    if player in self.playersCache:
                        players.append(self.playersCache[player])
                    else:
                        players.append({'Login': player})
        
        return players
