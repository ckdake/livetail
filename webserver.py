import string,cgi,time,Queue,threading,socket,sys, httplib,re,urllib,time
from os import curdir, sep
from os import popen
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class LiveTail(object): #Live tails the log file into a Queue and provides access to it
	
	def __init__(self, quitlock):
		self.livetail = Queue.Queue()
		self.quitlock = quitlock
		self.thread = threading.Thread(target=self.run)
		self.thread.name = "a live tail"
		self.thread.start()

	def run(self):
		logfile = popen('tail -f /var/log/remote_httpd/error_log 2>/dev/null')
		while not self.quitlock.locked():
			self.livetail.put(logfile.readline())
			if (self.livetail.qsize() > 100): #queue size limited to 100 for now
				self.livetail.get();	

	def get(self):
		return self.livetail.get()

	def empty(self):
		return self.livetail.empty()

class UserHTTPServer(HTTPServer): #wrapps HTTPServer and runs the LiveTail process
	
	def __init__(self, server_address, RequestHandlerClass):
		self.thread = threading.Thread(target=self.serve_forever)
		self.quitlock = threading.Lock()
		self.livetail = LiveTail(self.quitlock)
		self.addr,self.port = server_address
		self.thread.name = "http server (%d)" % self.port
		print "starting client webserver on %d" % self.port
		self.timestamp = time.time()
		
		HTTPServer.__init__(self, server_address, RequestHandlerClass)

	def start(self):
		self.thread.start()

	def serve_forever(self):
		while not self.quitlock.locked():
			self.handle_request()

	def quit(self):
		self.finish()
		conn = httplib.HTTPConnection("localhost:%d" % self.port)
		conn.request("QUIT", "/")
		conn.getresponse()

	def finish(self):
		print "trying to close client webserver on %d" % self.port
		if not self.quitlock.locked():
			self.quitlock.acquire()
		self.server_close()
		#TODO: remove from userservers disctionary
		HTTPServer.server_close(self)

class UserRequestHandler(BaseHTTPRequestHandler): #handles HTTP requests specific to a particular client

    def in_cluster(self, line, cluster):
	if cluster == "od2":
		return not line.find("10.13.20") == -1
	if cluster == "demo":
		return not line.find("10.13.18") == -1
	if cluster == "eval":
		return not line.find("10.13.17") == -1
	if cluster == "online":
		return not line.find("10.13.10") == -1
	if cluster == "si":
		return not line.find("10.13.16") == -1
	if cluster == "loadtest":
		return not line.find("10.13.21") == -1
	if cluster == "lhr":
		return not line.find("172.30.0") == -1
	return 1

    def do_QUIT(self):
	self.send_response(200)
        self.end_headers()

    def do_GET(self):
	
	self.server.timestamp = time.time()
	
	if self.path.startswith("/records"):
		self.send_response(200)
                self.send_header('Content-type',        'text/html')
                self.end_headers()

		cluster = ''
		filter = re.compile('.*')

		p = re.compile('\/records\?([a-z0-9]*)\/(.*)').match(self.path)
		if p:
			cluster = p.group(1)
			filter = re.compile('.*?' + urllib.unquote_plus(p.group(2)) + '.*?')

		lines = []
		while not self.server.livetail.empty():
			line = self.server.livetail.get()
			if self.in_cluster(line, cluster) and filter.match(line):
				lines.append(line)
		lines.reverse()
		for line in lines:
			self.wfile.write(line + "<br />")
		self.wfile.write('')
		return

	if self.path == "/":
		f = open(curdir + sep + "livetail.html")
		self.send_response(200)
		self.send_header('Content-type',        'text/html')
		self.end_headers()
		self.wfile.write(f.read())
		f.close()
		return	
	if self.path == "/jquery-1.3.2.min.js":
		f = open(curdir + sep + "jquery-1.3.2.min.js")
                self.send_response(200)
                self.send_header('Content-type',        'text/html')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return
	if self.path == "/livetools.js":
		f = open(curdir + sep + "livetools.js")
                self.send_response(200)
                self.send_header('Content-type',        'text/html')
                self.end_headers()
                self.wfile.write(f.read())
                f.close()
                return
	if self.path == "/ping": # just keep this thing from getting killed off
		self.send_response(200)
		self.send_header('Content-type',        'text/html')
		self.end_headers()
		self.wfile.write('pong')
		return
	
class BaseHTTPServer(HTTPServer): #wrapps HTTPServer and runs the LiveTail process
	
	def __init__(self, server_address, RequestHandlerClass):
		self.baseport = 8100
		self.curport = self.baseport
		self.maxport = 8199
		self.userservers = dict()
		self.runsubs = 1
		self.killerthread  = threading.Thread(target=self.serverkiller)
		self.killerthread.name = "thread killer"
		self.killerthread.start()
		HTTPServer.__init__(self, server_address, RequestHandlerClass)

	def serverkiller(self): #kill off idle works longer than 10 minutes
		while self.runsubs:
			for userserver in self.userservers.values():
				if userserver.timestamp < (time.time() - 600):
					try:
						userserver.finish()
		                                conn = httplib.HTTPConnection("localhost:%d" % userserver.port)
		                                conn.request("QUIT", "/")
		                                conn.getresponse()	
						del self.userservers[userserver.port]
					except :
						pass
			time.sleep(5)

	def server_close(self):
		self.runsubs=0
		for userserver in self.userservers.values():
			try:
				userserver.finish()
				conn = httplib.HTTPConnection("localhost:%d" % userserver.port)
				conn.request("QUIT", "/")
				conn.getresponse()
				del self.userservers[userserver.port]
			except :
				pass
		HTTPServer.server_close(self)

class BaseRequestHandler(BaseHTTPRequestHandler): #handles HTTP requests for the base application

	def do_GET(self):
		
		self.send_response(200)
                self.send_header('Content-type',        'text/html')
		self.port = 0

		if (self.headers.getheaders('Cookie')):
			cookie = str(self.headers.getheaders('Cookie'))
			self.port = int(cookie[7:-2])
	
		else: # new client, setting up and giving it's own port
			self.port = self.server.curport
			while self.port in self.server.userservers:
				self.port = self.port + 1
				if self.port > self.server.maxport:
					self.port = self.server.baseport
			self.server.curport = self.port

		if self.port not in self.server.userservers:
			userserver = UserHTTPServer(('', self.port), UserRequestHandler)
			userserver.start()
			self.server.userservers[self.port] = userserver 

		self.send_header("Set-cookie", "port=%d" % self.port);
                self.end_headers()
		
		self.wfile.write("<html><body><title>Logsearch2</title><iframe src=\"http://10.13.1.120:%d/\" frameborder=\"0\" width=\"100%%\" height=\"100%%\"></iframe></body></html>" % self.port)
		self.wfile.write('')
		return


def debug_print_threads():
	print "----------------------------------"
	for thread in threading.enumerate():
		try:
			print "THREAD: %s" % thread.name
		except :
			print "THREAD: (unnamed) %s" % thread
	print "----------------------------------"
	t = threading.Timer(5.0, print_threads)
	t.name = "thread printer"
	t.start()

def main():
#    t = threading.Timer(5.0, debug_print_threads)
#    t.name = "thread printer"
#    t.start()
    try:
	server = BaseHTTPServer(('', 8081), BaseRequestHandler)
        print 'starting master httpserver on 8081...'
	server.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down server on 8081'
	print 'waiting for all threads to exit...'
	server.server_close()

if __name__ == '__main__':
    main()

