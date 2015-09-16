# -*- coding: utf-8 -*-

import requests
import sys
from threading import Timer
from xml.dom import minidom

class FPVCAJAX:
		
	refreshInterval = 2.0 # in seconds
	lastID = 0
		
	def __init__(self, core):
		self.core = core
		self.nick = core.ajaxNick
		self.actualNick = False
		self.endpoint = core.ajaxEndpoint
		self.firstRefresh = False
		self.login()
		
	def login(self):
		self.core.killed = False
		
		self.core.printLog('Logging into AJAX chat')
		self.users = []
		
		loginData = {
			'ajax': 'true',
			'do': 'login',
			'userName': self.nick,
			'channelName': self.core.ajaxChan,
			'lang': 'de'
		}
		r = requests.post(self.endpoint, data = loginData)
		if r.status_code != 200:
			self.core.printLog("Could not login to AJAX!")
			quit()
		self.cookies = r.cookies
		
		self.firstRefresh = True
		
		# start refresh loop
		self.core.printLog("Starting AJAX refresh timer")
		self.timer = Timer(FPVCAJAX.refreshInterval, self.refresh, [1])
		self.timer.start()
		
	def logout(self):
		self.core.printLog("Logging out of AJAX")
		data = {
			'logout': 'true'
		}
		r = requests.get(self.endpoint, params = data, cookies = self.cookies)
		if r.status_code != 200:
			self.core.printLog("Could not get data from AJAX!")
			quit()
			
	def getUserList(self):
		return sorted(self.users)
	
	def formatUserList(self):
		if len(self.getUserList()) == 0:
			return 'noone'
		else:
			return ', '.join(self.getUserList())
			
	def postMessage(self, msg):
		data = {
			'ajax': 'true',
			'lastID': FPVCAJAX.lastID,
			'text': msg
		}
		r = requests.post(self.endpoint, data = data, cookies = self.cookies)
		if r.status_code != 200:
			self.core.printLog("Could not get data from AJAX!")
			quit()
		self._parseData(r.text)	
		
	def _parseData(self, data):
		if self.core.killed:
			return # prevent accidental immortality
	
		self.users = []
		dom = minidom.parseString(data.encode('utf-8', 'ignore'))
		
		for info in dom.getElementsByTagName('info'):
			self._parseInfo(info)
			
		for userDOM in dom.getElementsByTagName('user'):
			user = userDOM._get_firstChild().data
			if (not user == self.actualNick) and (not user.endswith('@irc)')):
				self.users.append(user)
			
		for msg in dom.getElementsByTagName('message'):
			self._parseMessage(msg)
				
	def _parseMessage(self, msgDOM):
		# take apart message DOM
		msgID = int(msgDOM.attributes['id'].value)
		if msgID > FPVCAJAX.lastID:
			FPVCAJAX.lastID = msgID
		else:
			return
						
		msg = msgDOM.getElementsByTagName('text')[0]._get_firstChild().data
		username = msgDOM.getElementsByTagName('username')[0]._get_firstChild().data
	
		if self.firstRefresh:
			print 'Skipping evaluation on first refresh'
			return
			
		if username == self.actualNick:
			print 'Not forwarding my own messages'
			return
	
		# check if this is a command
		if msg.startswith(self.actualNick + ': '):
			command = msg.split(': ', 1)[1]
			if username == self.core.ajaxOp:
				response = self.core.runCommand(command)
				if response:
					self.postMessage(u'' + username.decode('utf-8', 'ignore') + ': ' + response.decode('utf-8', 'ignore'))
			else:
				self.postMessage('%s: ##fpvc @ freenode. Alle Fragen an Olex.' % username)
		# check if this is a ChatBot message
		elif username == u'ChatBot':
			if msg.startswith(u'/logout '):
				user = msg.replace(u'/logout ', '').replace(u' Timeout', '').replace(u' IP', '')
				if user == self.actualNick:
					return # don't act on your own messages
				if user.endswith('@irc)'):
					return # don't show our fakes
				self.core.transportMessage('ajax', '', '%s left AJAX chat. Remaining: %s' % (user, self.formatUserList()))
				self.core.ajaxUserLoggedOut(user);
			if msg.startswith(u'/login '):
				user = msg.replace(u'/login ', '').replace(u' Timeout', '')
				if user == self.actualNick:
					return # don't act on your own messages
				if user.endswith('@irc)'):
					return # don't show our fakes
				self.core.transportMessage('ajax', '', '%s joined AJAX chat. Users: %s' % (user, self.formatUserList()))
		# ignore messages from our own fakes
		elif username.endswith('@irc)'):
			return
		else:
			self.core.transportMessage('ajax', username, msg)
				
	def _parseInfo(self, infoDOM):
		key = infoDOM.attributes['type'].value
		value = infoDOM._get_firstChild().data
		
		self.core.printLog("Got info: %s = %s" % (key, value))
		if key == 'userName':
			self.actualNick = value		
			
		if key == 'logout':
			self.core.killed = True
			self.timer = Timer(10.0, self.login, [])
			self.timer.start()
			
	def transportMessage(self, username, msg):
		try:
			if username:
				sendstring = '[b]<%s>[/b] %s' % (username.decode('utf-8', 'ignore'), msg.decode('utf-8', 'ignore'))
			else:
				sendstring = msg.decode('utf-8', 'ignore')
			self.postMessage(sendstring)
		except UnicodeError as err:
			self.postMessage('[i]Transportfehler: fehlerhafte Sonderzeichen[/i]')
		
	def refresh(self, keep_going = 1):
		#self.core.printLog("Refreshing AJAX data, lastID = %s" % self.lastID)
		loadData = {
			'ajax': 'true',
			'lastID': self.lastID
		}
		if not self.actualNick:
			loadData['getInfos'] = 'userName'
		
		try:			
			r = requests.post(self.endpoint, data = loadData, cookies = self.cookies)
			if r.status_code != 200:
				self.core.printLog("Could not get data from AJAX!")
				quit()
			self._parseData(r.text)	
			
			self.firstRefresh = False
		except:
			self.core.printLog("Refresh failed on watchdog, retrying")
		
		sys.stdout.flush()
		sys.stderr.flush()
		
		if keep_going == 1 and not self.core.killed:
			self.timer = Timer(FPVCAJAX.refreshInterval, self.refresh, [1])
			self.timer.start()
		
		