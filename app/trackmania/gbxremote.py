import xmlrpc.client
import xml.parsers.expat

import socket
import logging
import threading
import struct
import time

logger = logging.getLogger('clifga')

class DedicatedRemote:
    def __init__(self, host, port, username, password, apiVersion='2013-04-16', connRetries=3, resultTimeout=5):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.connRetries = connRetries
        self.resultTimeout = resultTimeout

        self.apiVersion = apiVersion
        self.validHeaders = ['GBXRemote 2']
        
        self.socket = None
        self.socketlock = threading.RLock()

        self.connalive = False
        self.connalivelock = threading.RLock()

        self.handlers = dict()
        self.handlerslock = threading.RLock()

        self.callbacks = dict()
        self.callbacksLock = threading.RLock()

        self._recv_loop_t = None
        self._curr_handler = 0x80000000
    
    def __reset(self):
        with self.connalivelock:
            self.connalive = False
        
        self.socket = None
        self.handlers = dict()
        self._curr_handler = 0x80000000
        self._recv_loop_t = None
    
    def __recv_header(self):
        self.socket.setblocking(True)
        self.socket.settimeout(3)

        # get header length
        hlendata = self.socket.recv(4)
        hlen = struct.unpack('<I', hlendata)[0]

        # get header string
        headerdata = self.socket.recv(hlen)
        return headerdata.decode()
    
    def __build_packet(self, handler, method, args):
        handlerbytes = handler.to_bytes(4, 'little')
        callbytes = xmlrpc.client.dumps(args, method, allow_none=True).encode()

        packetlen = len(callbytes)
        packetlenbytes = packetlen.to_bytes(4, 'little')

        return packetlenbytes + handlerbytes + callbytes
    
    def __internal_reconnect(self):
        logger.debug('Internal reconnect started.')

        while True:
            with self.connalivelock:
                if self.connalive:
                    return

            logger.info('Attempting to reconnect callback loop.')

            if self.connect():
                return
            
            logger.error('Failed to connect callback loop, trying again soon ...')
            time.sleep(1)

    def _next_handler(self):
        nexthandler = self._curr_handler

        if nexthandler == 0xffffffff:
            self._curr_handler = 0x80000000
        else:
            self._curr_handler += 1

        return nexthandler
    
    def _authenticate(self):
        success = self.call('Authenticate', self.username, self.password)
        
        if type(success) is xmlrpc.client.Fault:
            logger.error('Authentication failed: %s' % str(success.faultString))
            return False

        if success:
            return True
        
        return False
    
    def _attempt_connection(self):
        try:
            # create and connect to socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            resolved = socket.gethostbyname(self.host)
            self.socket.connect((resolved, int(self.port)))

            # get gbx header and verify it
            header = self.__recv_header()
            if header not in self.validHeaders:
                logger.error('Remote returned an invalid header: %s' % str(header))
                return False
            
            self.socket.setblocking(False)
            self.socket.settimeout(0)

            return True
        except socket.gaierror:
            logger.error('Failed to resolve host %s.' % str(self.host))
        except socket.error as e:
            logger.error('Connection failed to %s:%d: %s' % (str(self.host), int(self.port), str(e)))
        except Exception as e:
            logger.error('Connection failed due to unknown error: %s' % str(e), exc_info=e)
        
        return False
    
    def _notify_result(self, handler, result):
        with self.handlerslock:
            if handler in self.handlers:
                self.handlers[handler]['result'] = result
                self.handlers[handler]['event'].set()
    
    def __perform_callback(self, cb, method, args):
        if cb['async']:
            logger.debug('Calling callback for (async): %s' % method)
            t = threading.Thread(target=cb['function'], args=args)
            t.start()
        else:
            logger.debug('Calling callback for (sync): %s' % method)
            cb['function'](*args)

    def _handle_result(self, handler, method, data):
        logger.debug('Handling result: %s ~ %s' % (str(method), str(data)))

        if method is None:
            # this is a normal method call
            logger.debug('Handling method call result ...')

            if data is not None and type(data) is tuple and len(data) == 1:
                data = data[0]
            
            self._notify_result(handler, data)
            return
        
        # we have a callback
        logger.debug('Handling callback result ...')
        try:
            with self.callbacksLock:
                # callbacks specifically registered for this method
                if method in self.callbacks:
                    for cb in self.callbacks[method]:
                        self.__perform_callback(cb, method, data)
                
                # callbacks for any method
                if '*' in self.callbacks:
                    data = (method,) + data
                    for cb in self.callbacks['*']:
                        self.__perform_callback(cb, method, data)
        except Exception as e:
            logger.error('Failed handling callback: %s' % str(e), exc_info=e)

    def _handle_fault(self, handler, fault):
        logger.debug('Handling fault: ' + str(fault))
        self._notify_result(handler, fault)
    
    def _handle_error(self, handler, e):
        logger.debug('Handling error: ' + str(e))
        self._notify_result(handler, False)
    
    def _result_loop(self):
        connectionreset = False

        while True:
            with self.connalivelock:
                if not self.connalive:
                    break
            
            try:
                self.socketlock.acquire()

                # recieve packets
                headerdata = self.socket.recv(8)

                self.socket.setblocking(True)

                size, handler = struct.unpack('<IL', headerdata)
                packetdata = self.socket.recv(size)

                data = None
                method = None

                # determine packet handling
                try:
                    data, method = xmlrpc.client.loads(packetdata, use_builtin_types=True)
                    self._handle_result(handler, method, data)
                except xmlrpc.client.Fault as e:
                    self._handle_fault(handler, e)
                except xml.parsers.expat.ExpatError as e:
                    self._handle_error(handler, e)
                except Exception as e:
                    self._handle_error(handler, e)

            except (ConnectionResetError, BrokenPipeError) as e:
                logger.error(e, exc_info=e)
                
                with self.connalivelock:
                    self.connalive = False
                
                connectionreset = True
                break
            except Exception as e:
                pass
                #logger.error('Failed to recieve.', exc_info=e)
            finally:
                self.socket.setblocking(False)
                self.socketlock.release()
        
        if connectionreset:
            # atempt re-connection
            threading.Thread(target=self.__internal_reconnect).start()
            pass

        logger.debug('Recieve loop as ended.')

    def connect(self, maxretries=-1, attemptcb=None):
        # wait for recv loop to end
        if self._recv_loop_t is not None:
            logger.debug('Waiting for recv loop to end ...')
            with self.connalivelock:
                self.connalive = False
            self._recv_loop_t.join()
    
        # reset important vars
        self.__reset()

        retries = 1

        # attempt to reconnect, retrying n times
        while True:
            if not attemptcb is None and callable(attemptcb):
                attemptcb(retries, maxretries)

            if self._attempt_connection():
                logger.debug('Connected to TM2 dedicated server %s%d' % (str(self.host), int(self.port)))
                with self.connalivelock:
                    self.connalive = True

                # start recieve loop
                self._recv_loop_t = threading.Thread(target=self._result_loop)
                self._recv_loop_t.start()

                # authenticate
                logger.debug('Authenticating ...')
                if not self._authenticate():
                    logger.error('Authentication failed.')
                    
                    with self.connalivelock:
                        self.connalive = False
                    
                    return False
                
                # set api version for the callbacks
                self.call('SetApiVersion', self.apiVersion)
                
                # enable callbacks
                logger.debug('Enabling callbacks ...')
                self.call('EnableCallbacks', True)

                return True
            
            logger.error('TM2 Dedicated Server Connection Failed, re-try %d of %d ...' % (int(retries), int(maxretries)))

            if maxretries >= 0 and retries >= maxretries:
                break

            retries += 1
            time.sleep(1)
        
        return False
    
    def stop(self):
        """Kill the connection and quit all threads.
        """
        # wait for recv loop to end
        if self._recv_loop_t is not None:
            logger.debug('Waiting for recv loop to end ...')
            with self.connalivelock:
                self.connalive = False
            self._recv_loop_t.join()
    
    def call(self, method, *args, retryConnection=True, asynchronous=False):
        """Call a XML-RPC method on the remote server.

        Args:
            method (string): XML-RPC method to call.
            retryConnection (bool, optional): Whether to re-try connection if its detected to be lost.. Defaults to True.
            asynchronous (bool, optional): If true, the function returns a thread event instead of waiting for the result. Defaults to False.

        Raises:
            Exception: If there is no connection.
            Exception: If it failed to recieve data from the XML-RPC call.
            e: If re-connection failed.
            e: Raised on an unknown error.

        Returns:
            object: If asynchronous=True then it returns a thread-event otherwise the result of the XML-RPC call.
        """
        try:
            # check connection
            with self.connalivelock:
                if not self.connalive:
                    raise Exception('No connection to remote server.')

            # setup handler and send the packet
            handler = self._next_handler()
            resultEvent = threading.Event()
            with self.handlerslock:
                self.handlers[handler] = {
                    'event': resultEvent,
                    'result': None
                }

            logger.debug("Calling method '%s', args: %s" % (str(method), str(args)))
            
            packet = self.__build_packet(handler, method, args)
            with self.socketlock:
                self.socket.send(packet)
            
            # wait for result
            if not asynchronous:
                if resultEvent.wait(self.resultTimeout):
                    with self.handlerslock:
                        return self.handlers[handler]['result']
                
                raise Exception('Failed to recieve data from XMLRPC call.')
            
            # async call, return event instead
            return resultEvent
        except (ConnectionResetError, socket.error, BrokenPipeError) as e:
            logger.error('Connection to TM2 Dedicated server has been lost: %s' % str(e))

            if retryConnection:
                logger.info('Will attempt to re-connect.')
                
                if self.connect(self.connRetries):
                    return self.call(method, *args, retryConnection=False)
                
                logger.error('Re-connection failed.')
                raise e
        
        except Exception as e:
            logger.error('Unknown error during XMLRPC call attempt: %s' % str(e), exc_info=e)
            raise e
    
    def multicall(self, *methodCalls):
        """Send multiple calls to some XML-RPC methods at once.

        Returns:
            list: List of results for each XML-RPC call corresponding to the same order as they were given.
        """
        calls = []
        for call in methodCalls:
            calls.append({'methodName': call[0], 'params': [x for x in call[1:]]})
        
        return self.call('system.multicall', calls)
    
    def registerCallback(self, method, cb, obj=None, threadAsync=False):
        with self.callbacksLock:
            if method not in self.callbacks:
                self.callbacks[method] = []

            self.callbacks[method].append({
                'async': threadAsync,
                'function': cb,
                'object': obj
            })

            logger.debug('Registered XML-RPC callback: %s' % method)
