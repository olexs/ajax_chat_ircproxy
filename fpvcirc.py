# -*- coding: utf-8 -*-

import pythonircbot
import HTMLParser
import re

class FPVCIRC(pythonircbot.Bot):
	
	def __init__(self, core):
		super(FPVCIRC, self).__init__(core.ircNick)
		self.core = core;
		self.core.printLog('Logging into IRC')
		self.connect(core.ircServer, verbose=False)
		self.joinChannel(core.ircChan)
		self.addMsgHandler(self.ircMessage)
		self.sendMsg('NickServ', 'IDENTIFY %s' % self.core.ircNickservPw)
		self.htmlparser = HTMLParser.HTMLParser()
		
	def getUserList(self):
		if 'names' not in self._channels[self.core.ircChan.upper()]:
			self._channels[self.core.ircChan.upper()]['names'] = set()
			
		users = list(self._channels[self.core.ircChan.upper()]['names'])
		if self.core.ircNick in users:
			users.remove(self.core.ircNick)
		return sorted(users)
		
	def formatUserList(self):
		if len(self.getUserList()) == 0:
			return 'niemand'
		else:
			return ', '.join(self.getUserList())
			
	def _userModeSet(self, channel, nick, mode):
		pythonircbot.Bot._userModeSet(self, channel, nick, mode)
		if nick == self.core.ircNick and mode == 'o': # given op in irc on login; log fake users into ajax now
			for admin in self.core.admins:
				self.transportPrivateMessage('', admin, 'FPVC-IRC transport started. Logging into AJAX chat...')
			users = self.getUserList()
			for user in users:
				self.core.addFakeAjaxUser(user)		
			for admin in self.core.admins:
				self.transportPrivateMessage('', admin, 'AJAX users logged in, transport online.')
				
	def _joinedChannel(self, nick, channel):
		pythonircbot.Bot._joinedChannel(self, nick, channel)
		if not nick == self.core.ircNick:
			self.core.addFakeAjaxUser(nick)
			
	def _partedChannel(self, nick, channel):
		pythonircbot.Bot._partedChannel(self, nick, channel)
		if not nick == self.core.ircNick:
			self.core.removeFakeAjaxUser(nick)
			
	def _changedNick(self, oldnick, newnick):
		self.core.printLog("IRC nickchange: %s to %s" % (oldnick, newnick))
		pythonircbot.Bot._changedNick(self, oldnick, newnick)
		self.core.changeAjaxFakeNick(oldnick, newnick)
						
	def ircMessage(self, msg, channel, nick, client, msgMatch):	
		if nick == self.core.ircNick:
			return # skip my own messages
		if msg.startswith(self.core.ircNick + ': '):
			if nick == self.core.ircOp:
				response = self.core.runCommand(msg.split(': ', 1)[1])
				if response:
					self.sendMsg(channel, '%s: %s' % (nick, response))
			else:
				self.sendMsg(nick, "Nutzer im AJAX Chat: " + self.core.ajax.formatUserList())
			return # commands
		if nick == channel: # private message in IRC
			self.core.transportPmFromIRC(nick, msg)
		if channel == self.core.ircChan:
			self.core.transportMessage('irc', nick, msg)
		
	def transportFilter(self, msg):
		msg = self.htmlparser.unescape(msg)
		replacements = {
			"[img]": "",
			"[/img]": "",
			"[IMG]": "",
			"[/IMG]": "",
			"[url]": "",
			"[/url]": "",
			"[URL]": "",
			"[/URL]": "",
			"[/color]": "",
			"[/COLOR]": ""
		}
		msg = reduce(lambda x, y: x.replace(y, replacements[y]), replacements, msg)
		
		# replace ajax usernames with IRC ones
		msg = reduce(lambda x, y: x.replace(y, self.core.fakeAjaxUsernames[y]), self.core.fakeAjaxUsernames, msg)
		
		# replace color and url bbcodes
		msg = re.sub(r"\[color\=[\#0-9a-zA-Z]+\]", "", msg)
		
		return msg
		
	def transportPrivateMessage(self, sender, receiver, msg):
		self.transportMessage(sender, msg, receiver)
					
	def transportMessage(self, username, msg, private = False):
		lines = msg.strip().splitlines()
		if len(lines) > 1:
			for line in lines:
				self.transportMessage(username, line, private)
		else:
			msg = self.transportFilter(msg)
			channel = private if private else self.core.ircChan
			if msg.strip() == "":
				return
			try:
				if username:
					sendstring = u'<' + username + '> ' + msg
				else:
					sendstring = msg
					
				if private and username and private not in self.core.pmPartnerMap:
					self.core.startPmSession(private, username)
							
				self.sendMsg(channel, sendstring.encode('utf-8', errors = 'ignore'))
			except UnicodeError as err:
				self.sendMsg(channel, 'AJAX transport error: broken special characters')