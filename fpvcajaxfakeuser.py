import requests
import sys
from threading import Timer
from xml.dom import minidom

from fpvcajax import FPVCAJAX

class FPVCAJAXFakeUser:
		
	refreshInterval = 5.0 # in seconds
	lastID = 0
		
	def __init__(self, core, nick):
		self.core = core
		self.nick = nick
		self.actualNick = False
		self.endpoint = core.ajaxEndpoint
		self.firstRefresh = False
		self.lastPMID = 0
		self.session = False
		self.login()
		
	def login(self):
		self.killed = False
		
		self.core.printLog('Logging %s into AJAX chat' % self.nick)
		
		loginData = {
			'ajax': 'true',
			'do': 'login',
			'userName': self.core.generateAjaxName(self.nick),
			'channelName': self.core.ajaxChan,
			'lang': 'de'
		}
		
		if not self.session:
			self.session = requests.Session()
		r = self.session.post(self.endpoint, data = loginData)
		if r.status_code != 200:
			self.core.printLog("Could not login to AJAX!")
			quit()
		
		self.firstRefresh = True
		self.refresh()
		
	def logout(self):
		self.killed = True
		self.core.printLog('Logging %s out of AJAX chat' % self.nick)
		data = {
			'logout': 'true'
		}
		r = self.session.get(self.endpoint, params = data)
		if r.status_code != 200:
			self.core.printLog("Could not get data from AJAX!")
			quit()
						
	def postMessage(self, msg):
		data = {
			'ajax': 'true',
			'lastID': FPVCAJAX.lastID,
			'text': msg
		}
		if not self.actualNick:
			data['getInfos'] = 'userName'
		r = self.session.post(self.endpoint, data = data)
		if r.status_code != 200:
			self.core.printLog("Could not get data from AJAX!")
			quit()
		self._parseData(r.text)	
		
	def rename(self, newnick):
		# save new irc nick
		self.nick = newnick
		# remove all mentions of old ajax nick
		del self.core.fakeAjaxUsernames[self.actualNick]
		self.actualNick = False
		# request rename from ajax server
		self.postMessage('/nick ' + self.nick[:10] + '@irc')
		
	def _parseData(self, data):
		if self.core.killed or self.killed:
			return # prevent accidental immortality
	
		dom = minidom.parseString(data.encode('utf-8', 'ignore'))
		for info in dom.getElementsByTagName('info'):
			self._parseInfo(info)
			
		for msg in dom.getElementsByTagName('message'):
			self._parseMessage(msg)

	def _parseMessage(self, msgDOM):
		# take apart message DOM
		msg = msgDOM.getElementsByTagName('text')[0]._get_firstChild().data
		username = msgDOM.getElementsByTagName('username')[0]._get_firstChild().data
	
		if self.firstRefresh or username == self.actualNick:
			return
		
		if not msg.startswith('/privmsg '):
			return
			
		msgID = int(msgDOM.attributes['id'].value)
		if msgID <= self.lastPMID:
			return
		
		self.lastPMID = msgID
		self.core.transportPmFromAjax(username, self.nick, msg[9:])
				
	def _parseInfo(self, infoDOM):
		key = infoDOM.attributes['type'].value
		value = infoDOM._get_firstChild().data
		
		self.core.printLog("Got info: %s = %s" % (key, value))
		if key == 'userName':
			self.actualNick = value	
			self.core.setAjaxFakeActualNick(self.nick, self.actualNick)
			
		if key == 'logout':
			self.killed = True
			self.core.sendTimeoutMessage(self.login)
			self.timer = Timer(10.0, self.login, [])
			self.timer.start()
			
	def transportMessage(self, msg):
		try:
			sendstring = msg.decode('utf-8', 'ignore')
			self.postMessage(sendstring)
		except UnicodeError as err:
			self.postMessage('[i]Transportfehler: fehlerhafte Sonderzeichen[/i]')
		
	def refresh(self, keep_going = 1):
		if self.core.killed or self.killed:
			return
	
		#self.core.printLog("Refreshing AJAX data, lastID = %s" % self.lastID)
		loadData = {
			'ajax': 'true',
			'lastID': self.lastID
		}
		if not self.actualNick:
			loadData['getInfos'] = 'userName'
		try:
			r = self.session.post(self.endpoint, data = loadData)
			if r.status_code != 200:
				self.core.printLog("Could not get data from AJAX!")
				quit()
			self._parseData(r.text)	
			
			self.firstRefresh = False
		except:
			self.core.printLog("Refresh failed on fakeuser %s, retrying" % self.nick)
			
		sys.stdout.flush()
		sys.stderr.flush()
		
		if keep_going == 1 and not self.core.killed and not self.killed:
			self.timer = Timer(FPVCAJAXFakeUser.refreshInterval, self.refresh, [1])
			self.timer.start()