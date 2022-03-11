import json
import logging
import requests
import traceback

from disco.api.client import APIClient
from disco.types.message import MessageEmbed

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer

from django.conf import settings
from django.contrib import messages
from django.core.mail.message import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from puzzles.context import Context
from puzzles.hunt_config import (
    HUNT_TITLE,
    HUNT_ORGANIZERS,
    CONTACT_EMAIL,
    MESSAGING_SENDER_EMAIL,
)

logger = logging.getLogger('puzzles.messaging')


# Usernames that the bot will send messages to Discord with when various things
# happen. It's really not important that these are different. It's just for
# flavor.
ALERT_DISCORD_USERNAME = 'FIXME PH AlertBot'
CORRECT_SUBMISSION_DISCORD_USERNAME = 'FIXME PH WinBot'
INCORRECT_SUBMISSION_DISCORD_USERNAME = 'FIXME PH FailBot'
FREE_ANSWER_DISCORD_USERNAME = 'FIXME PH HelpBot'
VICTORY_DISCORD_USERNAME = 'FIXME PH CongratBot'

# Should be Discord webhook URLs that look like
# https://discordapp.com/api/webhooks/(numbers)/(letters)
# From a channel you can create them under Integrations > Webhooks.
# They can be the same webhook if you don't care about keeping them in separate
# channels.
ALERT_WEBHOOK_URL = 'FIXME'
SUBMISSION_WEBHOOK_URL = 'FIXME'
FREE_ANSWER_WEBHOOK_URL = 'FIXME'
VICTORY_WEBHOOK_URL = 'FIXME'

# Assuming you want messages on a messaging platform that's not Discord but
# supports at least a vaguely similar API, change the following code
# accordingly:
def dispatch_discord_alert(webhook, content, username):
    content = '[{}] {}'.format(timezone.localtime().strftime('%H:%M:%S'), content)
    if len(content) >= 2000:
        content = content[:1996] + '...'
    if settings.IS_TEST:
        logger.info(_('(Test) Discord alert:\n') + content)
        return
    logger.info(_('(Real) Discord alert:\n') + content)
    requests.post(webhook, data={'username': username, 'content': content})

def dispatch_general_alert(content):
    dispatch_discord_alert(ALERT_WEBHOOK_URL, content, ALERT_DISCORD_USERNAME)

def dispatch_submission_alert(content, correct):
    username = CORRECT_SUBMISSION_DISCORD_USERNAME if correct else INCORRECT_SUBMISSION_DISCORD_USERNAME
    dispatch_discord_alert(SUBMISSION_WEBHOOK_URL, content, username)

def dispatch_free_answer_alert(content):
    dispatch_discord_alert(FREE_ANSWER_WEBHOOK_URL, content, FREE_ANSWER_DISCORD_USERNAME)

def dispatch_victory_alert(content):
    dispatch_discord_alert(VICTORY_WEBHOOK_URL, content, VICTORY_DISCORD_USERNAME)


puzzle_logger = logging.getLogger('puzzles.puzzle')
def log_puzzle_info(puzzle, team, content):
    puzzle_logger.info('{}\t{}\t{}'.format(puzzle, team, content))

request_logger = logging.getLogger('puzzles.request')
def log_request_middleware(get_response):
    def middleware(request):
        request_logger.info('{} {}'.format(request.get_full_path(), request.user))
        return get_response(request)
    return middleware


# NOTE: we don't have a request available, so this doesn't render with a
# RequestContext, so the magic from our context processor is not available! (We
# maybe could sometimes provide a request, but I don't want to add that
# coupling right now.)
def send_mail_wrapper(subject, template, context, recipients):
    if not recipients:
        return
    # Manually plug in some template variables we know we want
    context['hunt_title'] = HUNT_TITLE
    context['hunt_organizers'] = HUNT_ORGANIZERS
    subject = settings.EMAIL_SUBJECT_PREFIX + subject
    body = render_to_string(template + '.txt', context)
    if settings.IS_TEST:
        logger.info(_('Sending mail <{}> to <{}>:\n{}').format(
            subject, ', '.join(recipients), body))
        return
    mail = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=MESSAGING_SENDER_EMAIL,
        to=recipients,
        alternatives=[(render_to_string(template + '.html', context), 'text/html')],
        reply_to=[CONTACT_EMAIL])
    try:
        if mail.send() != 1:
            raise RuntimeError(_('Unknown failure???'))
    except Exception:
        dispatch_general_alert(_('Could not send mail <{}> to <{}>:\n{}').format(
            subject, ', '.join(recipients), traceback.format_exc()))


# Set to this to delete an embed from a message. (None doesn't work; that's
# interpreted as "don't change the embed". MessageEmbed() does not work; you
# get a small, ugly embed with nothing in it.)
class EmptyEmbed:
    def to_dict(self):
        return {}

class DiscordInterface:
    TOKEN = None # FIXME a long token from Discord

    # the next two should be big decimal numbers; in Discord, you can right
    # click and Copy ID to get them
    GUILD = 'FIXME'
    HINT_CHANNEL = 'FIXME'

    # You also need to enable the "Server Members Intent" under the "Privileged
    # Gateway Intents" section of the "Bot" page of your application from the
    # Discord Developer Portal. Or you can comment out the code that
    # initializes `self.avatars` below.

    def __init__(self):
        self.client = None
        self.avatars = None
        if self.TOKEN and not settings.IS_TEST:
            self.client = APIClient(self.TOKEN)

    def get_avatars(self):
        if self.avatars is None:
            self.avatars = {}
            if self.client is not None:
                members = self.client.guilds_members_list(self.GUILD).values()
                for member in members:
                    self.avatars[member.user.username] = member.user.avatar_url
                for member in members:
                    self.avatars[member.name] = member.user.avatar_url
        return self.avatars

    # If you get an error code 50001 when trying to create a message, even
    # though you're sure your bot has all the permissions, it might be because
    # you need to "connect to and identify with a gateway at least once"??
    # https://discord.com/developers/docs/resources/channel#create-message

    # I spent like four hours trying to find weird asynchronous ways to do this
    # right before each time I send a message, but it seems maybe you actually
    # just need to do this once and your bot can create messages forever?
    # disco.py's Client (not APIClient) wraps an APIClient and a GatewayClient,
    # the latter of which does this. So I believe you can fix this by running a
    # script like the following *once* on your local machine (it will, as
    # advertised, run forever; just kill it after a few seconds)?

    # from gevent import monkey
    # monkey.patch_all()
    # from disco.client import Client, ClientConfig
    # Client(ClientConfig({'token': TOKEN})).run_forever()

    def update_hint(self, hint):
        HintsConsumer.send_to_all(json.dumps({'id': hint.id,
            'content': render_to_string('hint_list_entry.html', {
                'hint': hint, 'now': timezone.localtime()})}))
        embed = MessageEmbed()
        embed.author.url = hint.full_url()
        if hint.claimed_datetime:
            embed.color = 0xdddddd
            embed.timestamp = hint.claimed_datetime.isoformat()
            embed.author.name = _('Claimed by {}').format(hint.claimer)
            if hint.claimer in self.get_avatars():
                embed.author.icon_url = self.get_avatars()[hint.claimer]
            debug = _('claimed by {}').format(hint.claimer)
        else:
            embed.color = 0xff00ff
            embed.author.name = _('U N C L A I M E D')
            claim_url = hint.full_url(claim=True)
            embed.title = _('Claim: ') + claim_url
            embed.url = claim_url
            debug = 'unclaimed'

        if self.client is None:
            message = hint.long_discord_message()
            logger.info(_('Hint, {}: {}\n{}').format(debug, hint, message))
            logger.info(_('Embed: {}').format(embed.to_dict()))
        elif hint.discord_id:
            try:
                self.client.channels_messages_modify(
                    self.HINT_CHANNEL, hint.discord_id, embed=embed)
            except Exception:
                dispatch_general_alert(_('Discord API failure: modify\n{}').format(
                    traceback.format_exc()))
        else:
            message = hint.long_discord_message()
            try:
                discord_id = self.client.channels_messages_create(
                    self.HINT_CHANNEL, message, embed=embed).id
            except Exception:
                dispatch_general_alert(_('Discord API failure: create\n{}').format(
                    traceback.format_exc()))
                return
            hint.discord_id = discord_id
            hint.save(update_fields=('discord_id',))

    def clear_hint(self, hint):
        HintsConsumer.send_to_all(json.dumps({'id': hint.id}))
        if self.client is None:
            logger.info(_('Hint done: {}').format(hint))
        elif hint.discord_id:
            # try:
            #     self.client.channels_messages_delete(
            #         self.HINT_CHANNEL, hint.discord_id)
            # except Exception:
            #     dispatch_general_alert(_('Discord API failure: delete\n{}').format(
            #         traceback.format_exc()))
            # hint.discord_id = ''
            # hint.save(update_fields=('discord_id',))

            # what DPPH did instead of deleting messages:
            # (nb. I tried to make these colors color-blind friendly)

            embed = MessageEmbed()
            if hint.status == hint.ANSWERED:
                embed.color = 0xaaffaa
            elif hint.status == hint.REFUNDED:
                embed.color = 0xcc6600
            # nothing for obsolete

            embed.author.name = _('{} by {}').format(dict(hint.STATUSES)[hint.status], hint.claimer)
            embed.author.url = hint.full_url()
            embed.description = hint.response[:250]
            if hint.claimer in self.get_avatars():
                embed.author.icon_url = self.get_avatars()[hint.claimer]
            debug = _('claimed by {}').format(hint.claimer)
            try:
                self.client.channels_messages_modify(
                    self.HINT_CHANNEL, hint.discord_id, content=hint.short_discord_message(), embed=embed)
            except Exception:
                dispatch_general_alert(_('Discord API failure: modify\n{}').format(
                    traceback.format_exc()))

discord_interface = DiscordInterface()


# A WebsocketConsumer subclass that can exchange messages with a single
# browser tab.
class IndividualWebsocketConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

    def get_context(self):
        # We don't have a request, but we do have a user...
        context = Context(None)
        context.request_user = self.scope['user']
        return context

    # Use the following inherited methods:
    # def receive(self, text_data):
    # def send(self, text_data):

# A WebsocketConsumer subclass that can broadcast messages to a set of users.
class BroadcastWebsocketConsumer(WebsocketConsumer):
    def connect(self):
        if not self.is_ok(): return
        self.group = self.get_group()
        async_to_sync(self.channel_layer.group_add)(self.group, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if not self.is_ok(): return
        async_to_sync(self.channel_layer.group_discard)(self.group, self.channel_name)

    def channel_receive_broadcast(self, event):
        try:
            self.send(text_data=event['data'])
        except Exception:
            pass

class TeamWebsocketConsumer(BroadcastWebsocketConsumer):
    group_id = None

    def is_ok(self):
        return self.scope['user'].is_authenticated

    def get_group(self):
        assert self.group_id
        return '%s-%d' % (self.group_id, self.scope['user'].id)

    @classmethod
    def send_to_team(cls, team, text_data):
        async_to_sync(get_channel_layer().group_send)(
            '%s-%d' % (cls.group_id, team.user_id),
            {'type': 'channel.receive_broadcast', 'data': text_data})

class TeamNotificationsConsumer(TeamWebsocketConsumer):
    group_id = 'team'

class AdminWebsocketConsumer(BroadcastWebsocketConsumer):
    group_id = None

    def is_ok(self):
        return self.scope['user'].is_superuser

    def get_group(self):
        assert self.group_id
        return self.group_id

    @classmethod
    def send_to_all(cls, text_data):
        async_to_sync(get_channel_layer().group_send)(
            cls.group_id,
            {'type': 'channel.receive_broadcast', 'data': text_data})

class HintsConsumer(AdminWebsocketConsumer):
    group_id = 'hints'

def show_unlock_notification(context, unlock):
    data = json.dumps({
        'title': str(unlock.puzzle),
        'text': _('You’ve unlocked a new puzzle!'),
        'link': reverse('puzzle', args=(unlock.puzzle.slug,)),
    })
    # There's an awkward edge case where the person/browser tab that actually
    # triggered the notif is navigating between pages, so they don't have a
    # websocket to send to... use messages.info to put it into the next page.
    messages.info(context.request, data)
    TeamNotificationsConsumer.send_to_team(unlock.team, data)

def show_solve_notification(submission):
    if not submission.puzzle.is_meta:
        return
    data = json.dumps({
        'title': str(submission.puzzle),
        'text': _('You’ve solved a meta!'),
        'link': reverse('puzzle', args=(submission.puzzle.slug,)),
    })
    # No need to worry here since whoever triggered this is already getting a
    # [ANSWER is correct!] notification.
    TeamNotificationsConsumer.send_to_team(submission.team, data)

def show_hint_notification(hint):
    data = json.dumps({
        'title': str(hint.puzzle),
        'text': _('Hint answered!'),
        'link': reverse('hints', args=(hint.puzzle.slug,)),
    })
    TeamNotificationsConsumer.send_to_team(hint.team, data)
