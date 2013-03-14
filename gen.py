#-*- coding: utf-8 -*-
from __future__ import print_function

import yaml
import re
import sys
from django.template import Template, Context

sample = """
- head:
    - meta[charset="utf-8"]
    - title: Presentation
    - script[type=text/javascript, src=js/bootstrap.min.js]:
    - script[type=text/javascript, src=js/jquery.min.js]:
    - link[]:
        - rel: stylesheet
        - href: css/master.css
- body:
    - div.page.cover:
        - h1: Title of Presentation
        - table.table.table-striped
        - p:
            Hello, you.
        - pre:

            #inlcude
            for (){
                ijk
            }
"""
# print(yaml.load(sample))

class Head:
    Pattern = re.compile(
        """
        (?P<tag>
            (\w|[-_$])+
            )
        (\#(?P<id>
            (\w|[-_$])+)
            )?
        (?P<class>
            (\.(\w|[-_$])+)+
            )?
        (\[                                       # parse attrs, note this cannot 
                                                  # handle something like: [data="x,y=z"]
            (?P<attrs>
                ((\w|[-_$])+  \s*=\s* (.)+?
                    (\s*,\s* (\w|[-_$])+  \s*=\s* (.)+?)*
                    )?
                )
            \])? 
        """, re.VERBOSE)
    def __init__(self, cssSelector):
        """
        @cssSelector: something like "div#main.page.red[data-x=3, data-y=4]"
                allow:

                    * id, lead by '#'
                    * classes separate with '.'
                    * attributes, separate with ','
        """
        m = self.Pattern.match(cssSelector)
        self.classes = []
        self.inline = False
        self.attrs = {}
        self.id = None
        if not m:
            self.tag = cssSelector
        else:
            self.tag = m.group('tag')
            self.id = m.group('id')
            if m.group('class'):
                for c in m.group('class').split('.'):
                    c = c.strip()
                    if c:
                        self.classes.append(c)
            attrs = m.group('attrs')
            if attrs == '':
                self.inline = True
            elif attrs:
                for attr in attrs.split(','):
                    key, val = map(str.strip, attr.split('='))
                    self.attrs[key] = val

    def __repr__(self):
        return "tag:{self.tag}, id:{self.id}, class:{self.classes}, attrs:{self.attrs}, inline:{self.inline}".format(
                self=self)

class YamlSyntaxError(Exception):
    def __init__(self, head, child, msg=''):
        self.head = head
        self.child = child
        msg = msg or child.message
        Exception.__init__(self, msg)

    def traceback(self):
        if isinstance(self.child, YamlSyntaxError):
            return self.head.tag + ' > ' + self.child.traceback()
        else:
            return self.head.tag

def smart_quote(s):
    if s and (s[0] == '"' and s[-1] == '"'):
        return s
    else:
        return '"' + s + '"'

class Node:
    def __init__(self, head, text, childs):
        self.head = head
        self.text = text
        self.childs = childs

    def to_html(self, pretty=True):
        lines = []
        self._to_html_lines(0, lines)
        return '\n'.join(lines)

    def _to_html_lines(self, indent, lines):
        head = self.head
        attrs = []
        for k, v in head.attrs.iteritems():
            attrs.append((k, v))
        if head.inline:
            for c in self.childs:
                attrs.append((c.head.tag, c.text))
        if attrs:
            attrs = ' ' + ' '.join('{}={}'.format(k, smart_quote(v)) for k, v in attrs)
        else:
            attrs = ''
        indentStr = '    '*indent
        # construct the line
        line = u"""{indent}<{tag}{classes}{attrs}{close}""".format(
                indent=indentStr, 
                tag=head.tag,
                attrs=attrs,
                classes=' class="{}"'.format(' '.join(head.classes)) if head.classes else '',
                close=' />' if head.inline else '>',
                )
        lines.append(line)
        if not head.inline:
            if self.text is not None:
                if self.head.tag not in ['code', 'pre']:
                    if self.text:
                        text = self._indent_text(indentStr, self.text)
                        lines.append(text)
                else:
                    text = self.text
                    lines.append(text)
            else:
                for child in self.childs:
                    child._to_html_lines(indent+1, lines)
            lines.append('{}</{}>'.format(indentStr, head.tag))

    def _indent_text(self, indentStr, text):
        lines = []
        for line in text.split('\n'):
            lines.append(indentStr + line)
        return '\n'.join(lines)

def parse_data(data):
    """
    @return: A node.
    """
    if isinstance(data, dict):
    # data is a dict with only one key which is the tag.
        keys = data.keys()
        if len(keys) != 1:
            raise YamlSyntaxError(head, None, "Tag not unique")
        head = Head(keys[0])
        subDataList = data[keys[0]]
        if isinstance(subDataList, (str, unicode)):
            text = subDataList
            node = Node(head, text, [])
        elif subDataList is None:
            node = Node(head, '', [])
        else:
            childs = []
            for subData in subDataList:
                try:
                    child = parse_data(subData)
                except YamlSyntaxError as err:
                    raise YamlSyntaxError(head, err)
                # except Exception as err:
                #     import traceback
                #     traceback.print_stack()
                #     raise YamlSyntaxError(head, err)
                childs.append(child)
            node = Node(head, None, childs)
    else:
        head = Head(data)
        head.inline = True
        node = Node(head, None, [])
    return node

def from_yaml_string(s):
    """
    @return: A node.
    """
    yamlData = yaml.load(s)
    childs = []
    for elemData in yamlData:
        childs.append(parse_data(elemData))
    root = Node(Head('html'), None, childs)
    return root

def test_tag():
    def test_single(cssSelector):
        print('css:', cssSelector)
        print('tag:', Head(cssSelector))
    test_single("div#main.page.red[data-x=3, data-y=4]")
    test_single("div#main[data-x=3, data-y=4]")
    test_single("script[]")

# print(from_yaml_string(sample).to_html())
if __name__ == '__main__':
    src = sys.argv[1]
    with open(src) as infile:
        yamlStr = infile.read().decode('utf-8')
        try:
            root = from_yaml_string(yamlStr)
            print(root.to_html().encode('utf-8'))
        except YamlSyntaxError as err:
            print('YamlSyntaxError: {}\n  position: {}'.format(err.message, err.traceback()))
