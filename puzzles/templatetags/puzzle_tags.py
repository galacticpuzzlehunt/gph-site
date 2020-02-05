import markdown
import os
import re

from django import template
from django.conf import settings
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def ga_code():
    return mark_safe(settings.GA_CODE)

@register.simple_tag
def format_duration(secs):
    if secs is None:
        return ''
    secs = max(float(secs), 0)
    hours = int(secs / (60 * 60))
    secs -= hours * 60 * 60
    mins = int(secs / 60)
    secs -= mins * 60
    if hours > 0:
        return '{}h{}m'.format(hours, mins)
    elif mins > 0:
        return '{}m{:.0f}s'.format(mins, secs)
    elif secs > 0:
        return '{:.1f}s'.format(secs)
    else:
        return '0s'

@register.simple_tag
def duration_between(before, after):
    return format_duration((after - before).total_seconds())

@register.simple_tag
def days_between(before, after):
    return round((after - before).total_seconds() / 60 / 60 / 24, 1)

@register.filter
def unix_time(timestamp):
    return timestamp.strftime('%s') if timestamp else ''

@register.simple_tag
def format_time(timestamp, format='%b %-d, %H:%M'):
    return timestamp.astimezone(timezone.get_default_timezone()).strftime(format) if timestamp else ''

@register.simple_tag
def percentage(a, b):
    return '' if b == 0 else '%s%%' % (100 * a // b)

@register.tag
def captureas(parser, token):
    try:
        tag_name, args = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError('`captureas` node requires a variable name.')
    nodelist = parser.parse(('endcaptureas',))
    parser.delete_first_token()
    return CaptureasNode(nodelist, args)

class CaptureasNode(template.Node):
    def __init__(self, nodelist, varname):
        self.nodelist = nodelist
        self.varname = varname

    def render(self, context):
        output = self.nodelist.render(context)
        context[self.varname] = mark_safe(markdown.markdown(output, extensions=['extra']))
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
