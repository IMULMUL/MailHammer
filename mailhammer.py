#!python
# -*- coding: utf-8 -*-

from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import argparse
import base64
import configparser
import os.path
import re
import smtplib
import socket
import sys
import io

def get_mail_list_from_file(file):
    try:
        with open(file, "r") as emails_file:
            result = list()

            for email in emails_file.readlines():
                email = email.strip("\n")
                if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    print >> sys.stderr, "[WARN] Non-correct E-Mail: " + email
                    continue
                result.append(email)

    except IOError:
        print >> sys.stderr, "[ERROR] Non-existent path to emails file."
        exit(1)

    if not result:
        print >> sys.stderr, "[ERROR] E-Mail list is empty."
        exit(1)

    return result

def create_message(message, subject, from_header, attach="", track="", mail=""):
    if not attach:
        msg = MIMEText('html')
        msg.set_type('text/html')
    else:
        msg = MIMEMultipart()

    if re.match(r'[а-яА-ЯёЁ]', from_header):
        pos = from_header.find('<')
        if pos != -1:
            msg['From'] = str(Header(from_header[:pos].strip(), 'utf-8')) + ' ' + from_header[pos:]
        else:
            msg['From'] = Header(from_header.strip(), 'utf-8')
    else:
        msg['From'] = Header(from_header)

    msg['To'] = Header(mail)
    msg['Subject'] = Header(subject, 'utf-8')

    with io.open(message, 'r', encoding='utf8') as file:
        message = file.read()


    if track:
        track = '<img alt="" src="%s?u=%s" width="1" height="1" border="0" />' % (track, base64.b64encode(mail))

        if message.find('</body>') != -1:
            message = message[:message.find('</body>')] + track + message[message.find('</body>'):]
        else:
            message += track

    if not attach:
        msg.set_payload(message, 'utf-8')
    else:
        msg.attach(MIMEText(message, 'html', 'utf-8'))

        with open(attach, 'r') as file:
            part = MIMEApplication(file.read(), Name=os.path.basename(attach))
            part['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(attach)
            msg.attach(part)

    result = msg.as_string()

    return result

def main():

    argparser = argparse.ArgumentParser(prog="MailHammer", description="Interface for sending E-Mails", epilog="")
    argparser.add_argument("-c", "--config", type=str,  help="Path to config file", required=True, metavar="FILE")
    argparser.add_argument("-v", "--verbose", action="count", help="Turn on verbose mode")

    args = argparser.parse_args()

    config_path = os.path.abspath(args.config) # Переменная с абсолютным путем к конфигу
    if not os.path.exists(config_path):
        # Check if file path exists
        print >> sys.stderr, "[ERROR] Non-existent path to config file."
        exit(1)

    config = configparser.RawConfigParser()
    config.read(config_path)

    try:
        server      = config.get('Server', 'server')
        port        = config.getint('Server', 'port')
        auth_required = config.getboolean('Server', 'auth_required')
        username    = config.get('Server', 'username')
        password    = config.get('Server', 'password')
        message_file = os.path.abspath(config.get('Message', 'message'))
        from_header = config.get('Message', 'from_header')
        subject     = config.get('Message', 'subject')
        attachment  = config.get('Message', 'attachment')
        emails      = get_mail_list_from_file(config.get('Message', 'emails'))
        track       = config.get('Message', 'tracking_handler')
    except configparser.NoOptionError as e:
        print >> sys.stderr, "[ERROR] In config file " + str(e.message)
        exit(1)

    if attachment:
        attachment = os.path.abspath(attachment)

    if not from_header:
        from_header = username

    # Try connect to server
    if port == 465:
        smtpClient = smtplib.SMTP_SSL(server, port)
    elif port == 587:
        smtpClient = smtplib.SMTP(server, port)
        smtpClient.starttls()
    else:
        smtpClient = smtplib.SMTP(server, port)

    smtpClient.ehlo("npktrans.ru")

    if args.verbose > 1:
        smtpClient.set_debuglevel(1)

    print >> sys.stdout, "[INFO] Here is your configuration:\nServer: %s\nPort: %s\nUsername: %s\n" % (server, port, username)

    # Trying to login to the server in case authorization is required
    if auth_required:
        try:
            smtpClient.login(username, password)
            print >> sys.stdout, "[INFO] Logged to mail server"
        except smtplib.SMTPAuthenticationError as Ex:
            print >> sys.stderr, "[ERROR] Can't login to mail server"
            print >> sys.stderr, Ex

    print >> sys.stdout, "[INFO] Count of E-Mails: %s" % len(emails)

    # Sending email messages to list of addresses one by one
    email_counter = 0
    for email in emails:
        email_counter += 1
        print >> sys.stdout , "[INFO] Sending message to: %s [ %s / %s ] " % (email, email_counter, len(emails))
                                            # message, subject, from_header, attach="", track="", mail=""
        message = create_message(message_file, subject, from_header, attachment, track, email)

        if args.verbose and email_counter==1:
            print >> sys.stdout, "[INFO] The first created message body:\n" + message

        try:
            smtpClient.sendmail(username, email, message,mail_options=['BODY=8BITMIME', 'SMTPUTF8'])
        except (socket.error, smtplib.SMTPException) as Exception:
            print >> sys.stderr, "[ERROR] Can't send message."
            print >> sys.stderr, Exception
            exit(1)

    smtpClient.close()
    print >> sys.stdout, "[INFO] Success."

if __name__ == "__main__":
    main()