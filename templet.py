"""
A lightweight python templating engine.  Templet version 3.3

Lightweight templating idiom using @templet.

Each template function is marked with the attribute @templet.
Template functions will be rewritten to expand their document
string as a template and return the string result.
For example:

    from templet import templet

    @templet
    def myTemplate(animal, body):
        "the $animal jumped over the $body."

    print(myTemplate('cow', 'moon'))

The template language understands the following forms:

    $myvar - inserts the value of the variable 'myvar'
    ${...} - evaluates the expression and inserts the result
    ${[...]} - evaluates the list comprehension and inserts all the results
    ${{...}} - executes enclosed code; use 'out.append(text)' to insert text

In addition the following special codes are recognized:

    $$ - an escape for a single $
    $ (at the end of the line) - a line continuation
    $( $. - translates directly to $( and $. so jquery does not need escaping
    $/ $' $" - also passed through so the end of a regex does not need escaping

Template functions are compiled into code that accumulates a list of
strings in a local variable 'out', and then returns the concatenation
of them.  If you want to do complicated computation, you can append
to the 'out' variable directly inside a ${{...}} block, for example:

    @templet
    def myrow(name, values):
        '''
        <tr><td>$name</td><td>${{
             for val in values:
                 out.append(string(val))
        }}</td></tr>
        '''

Generated code is arranged so that error line numbers are reported as
accurately as possible.

Templet is by David Bau and was inspired by Tomer Filiba's Templite class.
For details, see http://davidbau.com/templet

Templet is posted by David Bau under BSD-license terms.

Copyright (c) 2012, David Bau
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
         this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
         notice, this list of conditions and the following disclaimer in the
         documentation and/or other materials provided with the distribution.

    3. Neither the name of Templet nor the names of its contributors may
         be used to endorse or promote products derived from this software
         without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import inspect
import re
import sys

__all__ = ['templet']


if sys.version_info.major == 2:
    def func_code(func):
        return func.func_code
else:
    def func_code(func):
        return func.__code__


RE_DIRECTIVE = re.compile(
    """
        [$]                             # Directives begin with a $
          (?![.(/'"])                   # Except $. $( $/ $' $" !!!
        (
          [$]                         | # $$ is an escape for $
          WHITESPACE-TO-EOL           | # $\\n is a line continuation
          [_a-z][_a-z0-9]*            | # $simple Python identifier
          [{]    (?![[{])[^}]*    [}] | # ${...} expression to eval
          [{][[] .*?           []][}] | # ${[...]} list comprehension to eval
          [{][{] .*?           [}][}] | # ${{...}} multiline code to exec
        )
        (
          (?<=[}][}])                   # after }}
          WHITESPACE-TO-EOL             #   eat trailing newline
          |                             #   if any
        )
    """
    .replace("WHITESPACE-TO-EOL", r"[^\S\n]*\n"),
    re.IGNORECASE | re.VERBOSE | re.DOTALL)


def reindent(str, spaces=''):
    """
        Removes any leading empty columns of spaces
    """
    lines = str.splitlines()
    lspace = [len(l) - len(l.lstrip()) for l in lines if l.lstrip()]
    margin = len(lspace) and min(lspace)
    return '\n'.join((spaces + l[margin:]) for l in lines)


def DEF(func):
    return 'def %s%s:' % (
        func.__name__,
        inspect.formatargspec(*inspect.getargspec(func)))


def CODE_BLOCK(block):
    return reindent(block, ' ')

START = ' out = []'
CONSTANT = ' out.append({!r})'.format
LIST_COMPREHENSION = ' out.extend(map("".__class__, [{}]))'.format
EVAL = ' out.append("".__class__({}))'.format
FINISH = ' return "".join(out)'


class _TemplateBuilder:

    def __addcode(self, line, simple=True):
        offset = self.lineno - self.extralines - len(self.code)
        if offset <= 0 and simple and self.simple and self.code:
            self.code[-1] += ';' + line
        else:
            self.code.append('\n' * (offset - 1) + line)
            self.extralines += max(0, offset - 1)
        self.extralines += line.count('\n')
        self.simple = simple

    def build(self, func, filename, lineno, docline):
        template = func.__doc__
        self.code = [
            '\n' * (lineno - 1) +
            DEF(func),
            START]
        self.extralines = max(0, lineno - 1)
        self.simple = True
        self.lineno = lineno + docline
        add_code = self.__addcode
        #
        for i, part in enumerate(RE_DIRECTIVE.split(reindent(template))):
            #
            if i % 3 == 0 and part:
                add_code(CONSTANT(part))
            elif i % 3 == 1:
                if not part:
                    raise SyntaxError(
                        'Unescaped $ in %s:%d' % (filename, self.lineno))
                elif part == '$':
                    add_code(CONSTANT('$'))
                elif part.startswith('{{'):
                    add_code(CODE_BLOCK(part[2:-2]), simple=False)
                elif part.startswith('{['):
                    add_code(LIST_COMPREHENSION(part[2:-2]))
                elif part.startswith('{'):
                    add_code(EVAL(part[1:-1]))
                elif not part.endswith('\n'):
                    add_code(EVAL(part))
            self.lineno += part.count('\n')
        self.code.append(FINISH)
        return '\n'.join(self.code)


def templet(func):
    """
        Decorator for template functions

        @templet
        def jumped(animal, body):
            "the $animal jumped over the $body."

        print(jumped('cow', 'moon'))

    """
    filename = func_code(func).co_filename
    lineno = func_code(func).co_firstlineno
    #
    if func.__doc__ is None:
        raise SyntaxError('No template string at %s:%d' % (filename, lineno))
    # scan source code to find the docstring line number (2 if not found)
    try:
        docline = 2
        (source, _) = inspect.getsourcelines(func)
        for lno, line in enumerate(source):
            if re.match('(?:|[^#]*:)\\s*[ru]?[\'"]', line):
                docline = lno
                break
    except:
        docline = 2
    #
    code_str = _TemplateBuilder().build(func, filename, lineno, docline)
    code = compile(code_str, filename, 'exec')
    #
    globals = sys.modules[func.__module__].__dict__
    locals = {}
    exec(code, globals, locals)
    return locals[func.__name__]
