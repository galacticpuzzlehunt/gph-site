import hashlib
import markdown
import os
import re

from django import template
from django.template.base import NodeList
from django.template.loader_tags import BlockNode
from django.utils import timezone
from django.utils import formats
from django.utils.translation import gettext as _
from django.utils.html import strip_spaces_between_tags
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def format_duration(secs):
    if secs is None:
        return ''
    secs = max(int(secs), 0)
    hours = int(secs / (60 * 60))
    secs -= hours * 60 * 60
    mins = int(secs / 60)
    secs -= mins * 60
    if hours > 0:
        return _('{}h{}m').format(hours, mins)
    elif mins > 0:
        return _('{}m{}s').format(mins, secs)
    else:
        return _('{}s').format(secs)

@register.simple_tag
def format_time_since(timestamp, now):
    text = format_duration((now - timestamp).total_seconds())
    return mark_safe('<time datetime="%s" data-format="%s">%s</time>'
        % (timestamp.isoformat(), formats.get_format('DATE_AT_TIME'), text))

@register.simple_tag
def days_between(before, after):
    return round((after - before).total_seconds() / 60 / 60 / 24, 1)

@register.filter
def unix_time(timestamp):
    return timestamp.timestamp() if timestamp else ''

@register.simple_tag
def format_time(timestamp, format='DATE_TIME'):
    if not timestamp:
        return ''
    timestamp2 = timestamp.astimezone(timezone.get_default_timezone())
    text = formats.date_format(timestamp2, format=format)
    return mark_safe('<time datetime="%s" data-format="%s">%s</time>'
        % (timestamp.isoformat(), formats.get_format(format), text))

@register.simple_tag
def percentage(a, b):
    return '' if b == 0 else '%s%%' % (100 * a // b)

@register.filter
def hash(obj):
    return hashlib.md5(str(obj).encode('utf8')).hexdigest()

@register.tag
class puzzleblock(template.Node):
    def __init__(self, parser, token):
        args = token.contents.split()
        if len(args) not in (2, 3):
            raise template.TemplateSyntaxError('Usage: {% puzzleblock block-name [variant] %}')
        self.name = args[1]
        self.variant = args[2] if len(args) > 2 else None

    def render_actual(self, context, name):
        return BlockNode(name, NodeList()).render_annotated(context)

    def render_real(self, context):
        html = self.render_actual(context, self.name + '-html')
        if html:
            return html
        md = self.render_actual(context, self.name + '-md')
        if md:
            return markdown.markdown(strip_spaces_between_tags(md), extensions=['extra'])
        return ''

    def render(self, context):
        ident = self.name.replace('-', '_')
        if self.variant:
            context['variant'] = self.variant
            ident += '_' + self.variant
        context[ident] = mark_safe(self.render_real(context))
        return ''

@register.tag
def spacelesser(parser, token):
    nodelist = parser.parse(('endspacelesser',))
    parser.delete_first_token()
    return SpacelesserNode(nodelist)

class SpacelesserNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def replace(self, match):
        if match.start() == 0 or match.string[match.start() - 1] == '>':
            return ''
        if match.end() == len(match.string) or match.string[match.end()] == '<':
            return ''
        return ' '

    def render(self, context):
        return re.sub(r'\s+', self.replace, self.nodelist.render(context))
