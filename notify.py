import datetime
from gzlogging import write_log
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request, urllib.parse, urllib.error
import smtplib

class NotifyService:
	def __init__(self, name, id, public_url):
		self.servicetype = 'none'
		self.id = id
		self.name = name
		self.public_url = public_url

	def _process_text(self, text, remind_acc):
		# Look for keywords in text and replace.
		if('[TIME]' in text):
			now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
			text = text.replace('[TIME]', now)
		if('[URL]' in text):
			text = text.replace('[URL]', self.public_url)
		if('[REMIND]' in text):
			text = text.replace('[REMIND]', str(remind_acc))
		return text

	def send(self, title, message):
		pass
	
	def __repr__(self):
		return self.name  # Sends string 'name' back to identify object

class ProtoService(NotifyService):
	def __init__(self, name, id, public_url):
		super().__init__(name, id, public_url)
		self.servicetype = 'proto'

	def send(self, title, message, remind_acc=0):
		title = self._process_text(title, remind_acc)
		message = self._process_text(message, remind_acc)
		print('=======[  Proto Notify  ]=======')
		print(f'Title: {title}')
		print(f'Message: \n {message}')
		print('================================')
		write_log(title,logtype="NOTIFY")

class EmailService(NotifyService):
	def __init__(self, name, id, public_url, to_email, from_email, smtpserver, smtpport, username, password, tls):
		super().__init__(name, id, public_url)
		self.servicetype = 'email'
		self.to_email = to_email
		self.from_email = from_email
		self.smtpserver = smtpserver
		self.smtpport = smtpport
		self.username = username
		self.password = password
		self.tls = tls 

	def send(self, title, message, remind_acc=0):
		title = self._process_text(title, remind_acc)
		message = self._process_text(message, remind_acc)

		try:
			toaddrlist = [addr.strip() for addr in self.to_email.split(',')] # split on commas and strip out any spaces
			msg = MIMEMultipart()
			msg['From'] = self.from_email
			msg['To'] = ', '.join(toaddrlist)
			msg['Subject'] = title
			body = message
			msg.attach(MIMEText(body, 'plain'))
			
			server = smtplib.SMTP(self.smtpserver, self.smtpport)
			if self.tls:
				server.starttls()
			if self.username:
				server.login(self.username, self.password)
			text = msg.as_string()
			server.sendmail(self.from_email, toaddrlist, text)
			server.quit()

			for addr in toaddrlist:
				event = title + ". E-mail notification sent to: " + addr
				write_log(event, logtype='NOTIFY')

		except smtplib.SMTPException as e:
			event = "E-mail notification failed. SMTPLib general exception: %s" % e
			write_log(event, logtype='ERROR')
		except Exception as e:
			event = "E-mail notification failed, with exception: %s" % e
			write_log(event, logtype='ERROR')
		return()

class PushoverService(NotifyService):
	def __init__(self, name, id, public_url, apikey, userkey):
		super().__init__(name, id, public_url)
		self.servicetype = 'pushover'
		self.userkey = userkey
		self.apikey = apikey 

	def send(self, title, message, remind_acc=0):
		title = self._process_text(title, remind_acc)
		message = self._process_text(message, remind_acc)

		url = 'https://api.pushover.net/1/messages.json'
		for user in self.userkey.split(','):
			try:
				r = requests.post(url, data={
					"token": self.apikey,
					"user": user.strip(),
					"message": message,
					"title": title,
					"url": self.public_url
					})
				event = title + ". Pushover notification sent to: " + user.strip() + ' - Pushover Response: ' + r.text
				write_log(event, logtype='NOTIFY')

			except Exception as e:
				event = 'Pushover Notification to %s failed: %s' % (user, e)
				write_log(event, logtype='ERROR')
			except:
				event = 'Pushover Notification to %s failed for unknown reason.' % (user)
				write_log(event, logtype='ERROR')

class IFTTTService(NotifyService):
	def __init__(self, name, id, public_url, apikey, iftttevent):
		super().__init__(name, id, public_url)
		self.servicetype = 'ifttt'
		self.apikey = apikey
		self.iftttevent = iftttevent

	def send(self, title, message, remind_acc=0):
		title = self._process_text(title, remind_acc)
		message = self._process_text(message, remind_acc)

		url = 'https://maker.ifttt.com/trigger/' + self.iftttevent + '/with/key/' + self.apikey

		query_args = { "value1" : title + " " + message}

		try:
			r = requests.post(url, data=query_args)
			event = "IFTTT Notification Success: " + r.text
			write_log(event, logtype='NOTIFY')
		except:
			event = "IFTTT Notification Failed: " + r.text
			write_log(event, logtype='ERROR')

class PushBulletService(NotifyService): 
	def __init__(self, name, id, public_url, apikey):
		super().__init__(name, id, public_url)
		from pushbullet import Pushbullet
		self.servicetype = 'pushbullet'
		self.apikey = apikey
		self.pb = Pushbullet(self.apikey) 

	def send(self, title, message, remind_acc=0):
		title = self._process_text(title, remind_acc)
		message = self._process_text(message, remind_acc)
		
		try:
			push = self.pb.push_link(title, self.public_url, message)
			event = "Pushbullet Notification Success: " + title
			write_log(event, logtype='NOTIFY')
		except:
			event = "Pushbullet Notification Failed: " + title
			write_log(event, logtype='ERROR')