# -*- coding: utf-8 -*-

from __future__ import absolute_import
from threading import Timer

import fpvcajax, fpvcirc, fpvcajaxfakeuser
import datetime

from config import ircbot_config

class CoreTransport:
	ircNick = ircbot_config['ircNick']
	ircNickservPw = ircbot_config['ircNickservPw']
	ircChan = ircbot_config['ircChan']
	ircServer = ircbot_config['ircServer']
	ircOp = ircbot_config['ircOp']
	
	admins = ircbot_config['admins']
	
	ajaxNick = ircbot_config['ajaxNick']
	ajaxEndpoint = ircbot_config['ajaxEndpoint']
	ajaxChan = ircbot_config['ajaxChan']
	ajaxOp = ircbot_config['ajaxOp']
			
	killed = False
		
	def printLog(self, msg):
		print datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + ' ' + msg
	
	def __init__(self):
		self.fakeAjaxUsers = {}
		self.fakeAjaxUsernames = {}
		
		self.pmPartnerMap = { }
		
		# initialize IRC connection
		self.irc = fpvcirc.FPVCIRC(self)
								
		# initialite AJAX connection
		self.ajax = fpvcajax.FPVCAJAX(self)
								
	def ajaxUserLoggedOut(self, user):
		for ircNick in self.pmPartnerMap:
			if self.pmPartnerMap[ircNick] == user:
				self.irc.transportPrivateMessage(False, ircNick, u'Private Unterhaltung mit <%s> beendet (Nutzer hat den Webchat verlassen)' % user)
				del self.pmPartnerMap[ircNick]
					
	def transportMessage(self, source, username, msg):
		try:
			self.printLog('Transporting message: from %s, user %s, message: %s' % (source, username, msg))
		except UnicodeError as err:
			self.printLog('Transporting message with unprintable chars')
			
		if source == 'ajax':
			self.irc.transportMessage(username, msg)
		if source == 'irc':
			if username in self.fakeAjaxUsers:
				self.fakeAjaxUsers[username].transportMessage(msg)
			else:
				self.printLog('Transporting message failed: %s not in fake ajax user list' % username)
			
	def transportPmFromIRC(self, sender, msg):
		if not sender in self.fakeAjaxUsers:
			self.printLog('Transporting private message failed: %s not in fake ajax user list' % sender)
			return
			
		commands = ['list', 'stop', 'quit']
		
		if msg in commands:
			if msg == 'list':
				self.irc.transportPrivateMessage(False, sender, u'Nutzer im AJAX Chat: ' + self.ajax.formatUserList())
				return	   
			if msg == 'stop' and sender in self.pmPartnerMap:
				self.irc.transportPrivateMessage(False, sender, u'Private Unterhaltung mit <%s> beendet.' % self.pmPartnerMap[sender])
				del self.pmPartnerMap[sender]
				return
			if msg == 'quit':
				if not sender in self.irc._channels[self.ircChan.upper()]['ops']:
					self.irc.transportPrivateMessage(False, sender, u'Keine Berechtigung.')
					return
				self.timer = Timer(1.0, self.quit)
				self.timer.start()
				return
		elif sender in self.pmPartnerMap:
			receiver = self.pmPartnerMap[sender]
			parts = msg.split(': ', 1)
			if parts[0] in self.ajax.users:
				receiver = parts[0]
				msg = parts[1]
				self.startPmSession(sender, receiver)
		else:
			parts = msg.split(': ', 1)
			if len(parts) == 1:
				self.irc.transportPrivateMessage(False, sender, u'Um jemanden im FPV-Community.de Chat anzuflüstern, mich wie folgt anschreiben: "<Empfänger im WebChat>: <Nachricht>"')
				self.irc.transportPrivateMessage(False, sender, u'Sonstige Befehle: list')
				return
			receiver = parts[0]
			msg = parts[1]
			if receiver not in self.ajax.users:
				if sender in self.pmPartnerMap:
					del self.pmPartnerMap[sender]
				self.irc.transportPrivateMessage(False, sender, u'Kann <%s> nicht anflüstern: Empfänger unbekannt. Nickname richtig geschrieben?' % receiver)
				return
			self.startPmSession(sender, receiver)
			
		self.fakeAjaxUsers[sender].transportMessage('/msg %s %s' % (receiver, msg))
		
	def startPmSession(self, ircUser, ajaxUser):
		self.pmPartnerMap[ircUser] = ajaxUser
		self.irc.transportPrivateMessage(False, ircUser, u'Private Unterhaltung mit <%s> gestartet. Queries an mich werden direkt as PNs an <%s> im Chat weitergeleitet.' % (ajaxUser, ajaxUser))
		self.irc.transportPrivateMessage(False, ircUser, u'Unterhaltung wird beendet wenn <%s> den Webchat verlässt, wenn du IRC verlässt, oder mit dem "stop" Befehl an mich.' % ajaxUser)
		   
	def transportPmFromAjax(self, sender, receiver, msg):
		if receiver in self.irc.getUserList():
			self.irc.transportPrivateMessage(sender, receiver, msg)
		else:
			self.printLog('Transporting private message failed: %s not in IRC user list' % receiver)
			self.fakeAjaxUsers[sender].transportMessage('/msg %s Privatnachricht konnte nicht zugestellt werden.' % sender)
			
	def sendTimeoutMessage(self, ajax_nick):
		for admin in self.admins:
			self.irc.transportPrivateMessage('', admin, 'Transport account timed out of FPVC webchat: %s' % ajax_nick)
			
	def addFakeAjaxUser(self, nick):
		if not nick in self.fakeAjaxUsers:
			self.fakeAjaxUsers[nick] = fpvcajaxfakeuser.FPVCAJAXFakeUser(self, nick)
		
	def removeFakeAjaxUser(self, nick):
		if nick in self.fakeAjaxUsers:
			if self.fakeAjaxUsers[nick].actualNick in self.fakeAjaxUsernames:
				del self.fakeAjaxUsernames[self.fakeAjaxUsers[nick].actualNick]
			self.fakeAjaxUsers[nick].logout()
			del self.fakeAjaxUsers[nick]
			
	def generateAjaxName(self, desiredNick):
		nickOk = False
		count = 0
		name = desiredNick[:10]
		while not nickOk:
			fullName = '(' + name + '@irc' + ')'
			nickOk = fullName not in self.fakeAjaxUsernames
			if not nickOk:
				count += 1
				name = name[:-len(str(count))] + str(count)
		return name + '@irc'
			
	def setAjaxFakeActualNick(self, nick, actualNick):
		self.fakeAjaxUsernames[actualNick] = nick
		
	def changeAjaxFakeNick(self, oldnick, newnick):
		# move ajax transport to new irc nick
		self.fakeAjaxUsers[newnick] = self.fakeAjaxUsers[oldnick]
		self.fakeAjaxUsers[oldnick] = False
		del self.fakeAjaxUsers[oldnick]
		# call for a rename in ajax
		self.fakeAjaxUsers[newnick].rename(newnick)
			
	def wait(self):
		self.irc.waitForDisconnect()
		
	def quit(self):
		self.killed = True
		for admin in self.admins:
			self.irc.transportPrivateMessage('', admin, 'Quit command received. AJAX accounts logging off...')
	
		for fake in self.fakeAjaxUsers:
			self.fakeAjaxUsers[fake].logout()
		self.ajax.logout()
		
		for admin in self.admins:
			self.irc.transportPrivateMessage('', admin, 'Logged everybody out of AJAX chat, shutting down.')
		
		self.irc.disconnect()
		quit()
		
def main():
	transport = CoreTransport()
	transport.wait()
	
if __name__ == "__main__":
	main()
