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

import sys, re, inspect


if sys.version_info.major == 2:
    def func_code(func):
        return func.func_code
else:
    def func_code(func):
        return func.__code__
    unicode = u''.__class__


SIMPLE, NOT_SIMPLE = True, False


class _TemplateBuilder(object):
    __pattern = re.compile(
        """
            [$]                         # Directives begin with a $
                (?![.(/'"])             # Except $. $( $/ $' $" !!!
            (
                [$]                   | # $$ is an escape for $
                WHITESPACE-TO-EOL     | # $\\n is a line continuation
                [_a-z][_a-z0-9]*      | # $simple Python identifier
                [{](?![[{]) [^}]* [}] | # ${...} expression to eval
                [{][[] .*? []][}]     | # ${[...]} list comprehension to eval
                [{][{] .*? [}][}]     | # ${{...}} multiline code to exec
            )
            (
                (?<=[}][}])             # after }}
                WHITESPACE-TO-EOL       #   eat trailing newline
                |                       #   if any
            )
        """
        .replace("WHITESPACE-TO-EOL", r"[^\S\n]*\n"),
        re.IGNORECASE | re.VERBOSE | re.DOTALL)

    def __init__(self, func):
        self.defn = 'def %s%s:' % (
            func.__name__,
            inspect.formatargspec(*inspect.getargspec(func)))
        self.start = ' out = []'
        self.constpat = ' out.append(%s)'
        self.emitpat = ' out.append(unicode(%s))'
        self.listpat = ' out.extend(map(unicode, [%s]))'
        self.finish = ' return "".join(out)'

    def __realign(self, str, spaces=''):
        """
            Removes any leading empty columns of spaces and an initial empty line
        """
        lines = str.splitlines()
        if lines and not lines[0].strip():
            del lines[0]
        lspace = [len(l) - len(l.lstrip()) for l in lines if l.lstrip()]
        margin = len(lspace) and min(lspace)
        return '\n'.join((spaces + l[margin:]) for l in lines)

    def __addcode(self, line, lineno, simple):
        offset = lineno - self.extralines - len(self.code)
        if offset <= 0 and simple and self.simple and self.code:
            self.code[-1] += ';' + line
        else:
            self.code.append('\n' * (offset - 1) + line);
            self.extralines += max(0, offset - 1)
        self.extralines += line.count('\n')
        self.simple = simple

    def build(self, template, filename, lineno, docline):
        self.code = ['\n' * (lineno - 1) + self.defn, self.start]
        self.extralines = max(0, lineno - 1)
        self.simple = SIMPLE
        add_code = self.__addcode
        lineno += docline + (1 if re.match(r'\s*\n', template) else 0)
        for i, part in enumerate(self.__pattern.split(self.__realign(template))):
            if i % 3 == 0 and part:
                add_code(self.constpat % repr(part), lineno, SIMPLE)
            elif i % 3 == 1:
                if not part:
                    raise SyntaxError(
                        'Unescaped $ in %s:%d' % (filename, lineno))
                elif part == '$':
                    add_code(
                        self.constpat % '"%s"' % part, lineno, SIMPLE)
                elif part.startswith('{{'):
                    add_code(
                        self.__realign(part[2:-2], ' '),
                        lineno + (1 if re.match(r'\{\{\s*\n', part) else 0),
                        NOT_SIMPLE)
                elif part.startswith('{['):
                    add_code(self.listpat % part[2:-2], lineno, SIMPLE)
                elif part.startswith('{'):
                    add_code(self.emitpat % part[1:-1], lineno, SIMPLE)
                elif not part.endswith('\n'):
                    add_code(self.emitpat % part, lineno, SIMPLE)
            lineno += part.count('\n')
        self.code.append(self.finish)
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
    builder = _TemplateBuilder(func)
    code_str = builder.build(func.__doc__, filename, lineno, docline)
    code = compile(code_str, filename, 'exec')
    #
    globals =  sys.modules[func.__module__].__dict__
    locals = {}
    exec(code, globals, locals)
    return locals[func.__name__]


##############################################################################
# When executed as a script, run some testing code.
if __name__ == '__main__':
    ok = True
    def expect(actual, expected):
        global ok
        if expected != actual:
            print("error - expect: %s, got:\n%s" % (repr(expected), repr(actual)))
            ok = False
        assert ok
    @templet
    def testBasic(name):
        "Hello $name."
    expect(testBasic('Henry'), "Hello Henry.")
    @templet
    def testReps(a, count=5): r"""
        ${{ if count == 0: return '' }}
        $a${testReps(a, count - 1)}"""
    expect(
        testReps('foo'),
        "foofoofoofoofoo")
    @templet
    def testList(a): r"""
        ${[testBasic(x) for x in a]}"""
    expect(
        testList(['David', 'Kevin']),
        "Hello David.Hello Kevin.")
    @templet
    def testRecursion(count=4): """
        ${{ if not count: return '' }}
        \N{BLACK STAR}${testRecursion(count - 1)}"""
    expect(
        testRecursion(count=10),
        "\N{BLACK STAR}" * 10)
    @templet
    def testmyrow(name, values):
        '''
        <tr><td>$name</td><td>${{
             for val in values:
                 out.append(str(val))
        }}</td></tr>
        '''
    expect(
         testmyrow('prices', [1, 2, 3]),
         "<tr><td>prices</td><td>123</td></tr>\n")
    try:
        got_exception = ''
        def dummy_for_line(): pass
        @templet
        def testsyntaxerror():
            # extra line here
            # another extra line here
            '''
            some text
            $a$<'''
    except SyntaxError as e:
        got_exception = str(e).split(':')[-1]
    expect(got_exception, str(func_code(dummy_for_line).co_firstlineno + 7))
    try:
        got_line = 0
        def dummy_for_line2(): pass
        @templet
        def testruntimeerror(a):
            '''
            some $a text
            ${{
                out.append(a) # just using up more lines
            }}
            some more text
            $b text $a again'''
        expect(func_code(testruntimeerror).co_firstlineno,
                     func_code(dummy_for_line2).co_firstlineno + 1)
        testruntimeerror('hello')
    except NameError as e:
        import traceback
        _, got_line, _, _ = traceback.extract_tb(sys.exc_info()[2], 10)[-1]
    expect(got_line, func_code(dummy_for_line2).co_firstlineno + 9)
    exec("""if True:
        @templet
        def testnosource(a):
            "${[c for c in reversed(a)]} is '$a' backwards."
        """)
    expect(testnosource("hello"), "olleh is 'hello' backwards.")
    error_line = None
    try:
        exec("""if True:
            @templet
            def testnosource_error(a):
                "${[c for c in reversed a]} is '$a' backwards."
            """)
    except SyntaxError as e:
        error_line = re.search('line [0-9]*', str(e)).group(0)
    expect(error_line, 'line 4')
    print("OK" if ok else "FAIL")
