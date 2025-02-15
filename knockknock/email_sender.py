import os
from typing import *
import datetime
import traceback
import functools
import socket
import yagmail

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_yag_sender(recipient_emails: List[str], sender_email: Optional[str] = None):
    if sender_email is None and len(recipient_emails) > 0:
        sender_email = recipient_emails[0]
    return yagmail.SMTP(sender_email)


def send_email(yag_sender: yagmail.SMTP, recipient_emails: List[str], *args, **kwargs):
    for i in range(len(recipient_emails)):
        current_recipient = recipient_emails[i]
        yag_sender.send(current_recipient, *args, **kwargs)


def email_sender(recipient_emails: list, sender_email: str = None):
    """
    Email sender wrapper: execute func, send an email with the end status
    (sucessfully finished or crashed) at the end. Also send an email before
    executing func.

    `recipient_emails`: list[str]
        A list of email addresses to notify.
    `sender_email`: str (default=None)
        The email adress to send the messages. If None, use the same
        address as the first recipient email in `recipient_emails`
        if length of `recipient_emails` is more than 0.
    """
    yag_sender = create_yag_sender(recipient_emails, sender_email)

    def decorator_sender(func):
        @functools.wraps(func)
        def wrapper_sender(*args, **kwargs):

            start_time = datetime.datetime.now()
            host_name = socket.gethostname()
            func_name = func.__name__

            # Handling distributed training edge case.
            # In PyTorch, the launch of `torch.distributed.launch` sets up a RANK environment variable for each process.
            # This can be used to detect the master process.
            # See https://github.com/pytorch/pytorch/blob/master/torch/distributed/launch.py#L211
            # Except for errors, only the master process will send notifications.
            if 'RANK' in os.environ:
                master_process = (int(os.environ['RANK']) == 0)
                host_name += ' - RANK: %s' % os.environ['RANK']
            else:
                master_process = True

            if master_process:
                contents = ['Your training has started.',
                            'Machine name: %s' % host_name,
                            'Main call: %s' % func_name,
                            'Starting date: %s' % start_time.strftime(DATE_FORMAT)]
                send_email(yag_sender, recipient_emails, 'Training has started 🎬', contents)
            try:
                value = func(*args, **kwargs)

                if master_process:
                    end_time = datetime.datetime.now()
                    elapsed_time = end_time - start_time
                    contents = ["Your training is complete.",
                                'Machine name: %s' % host_name,
                                'Main call: %s' % func_name,
                                'Starting date: %s' % start_time.strftime(DATE_FORMAT),
                                'End date: %s' % end_time.strftime(DATE_FORMAT),
                                'Training duration: %s' % str(elapsed_time)]

                    try:
                        str_value = str(value)
                        contents.append('Main call returned value: %s'% str_value)
                    except:
                        contents.append('Main call returned value: %s'% "ERROR - Couldn't str the returned value.")

                    send_email(yag_sender, recipient_emails, 'Training has successfully finished 🎉', contents)

                return value

            except Exception as ex:
                end_time = datetime.datetime.now()
                elapsed_time = end_time - start_time
                contents = ["Your training has crashed.",
                            'Machine name: %s' % host_name,
                            'Main call: %s' % func_name,
                            'Starting date: %s' % start_time.strftime(DATE_FORMAT),
                            'Crash date: %s' % end_time.strftime(DATE_FORMAT),
                            'Crashed training duration: %s\n\n' % str(elapsed_time),
                            "Here's the error:",
                            '%s\n\n' % ex,
                            "Traceback:",
                            '%s' % traceback.format_exc()]
                for i in range(len(recipient_emails)):
                    current_recipient = recipient_emails[i]
                    yag_sender.send(current_recipient, 'Training has crashed ☠️', contents)
                raise ex

        return wrapper_sender

    return decorator_sender
