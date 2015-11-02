#!/usr/bin/env python
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import re
import sys
import unittest


import templet as m

templet = m.templet
func_code = m.func_code


class Template:

    @templet
    def hello(self, name):
        r"Hello $name."

    @templet
    def add(self, a, b):
        r"$a + $b = ${a + b}"

    @templet
    def hello_list(self, a):
        r"""${[self.hello(x) for x in a]}"""

    @templet
    def repeat(self, a, count=5): """\
        ${{ if count == 0: return '' }}
        $a${self.repeat(a, count - 1)}"""

    @templet
    def black_stars(self, count=4): """\
        ${{ if not count: return '' }}
        \N{BLACK STAR}${self.black_stars(count - 1)}"""

    @staticmethod
    @templet
    def quotes():
        """($$ $.$($/$'$")"""

    @templet
    def html_cell_concat_values(self, name, values):
        '''\
        <tr><td>$name</td><td>${{
             for val in values:
                 out.append(str(val))
        }}</td></tr>
        '''

    @templet
    def multiline_countdown(self, n):
        '''\
        $n
        ${{
        if n > 1:
            out.append(self.multiline_countdown(n - 1))
        }}'''


class Test(unittest.TestCase):

    @property
    def template(self):
        return Template()

    def test_variable(self):
        self.assertEqual("Hello Henry.", self.template.hello('Henry'))

    def test_expr(self):
        self.assertEqual("1 + 2 = 3", self.template.add(1, 2))

    def test_recursion(self):
        self.assertEqual("foofoofoofoofoo", self.template.repeat('foo'))
        self.assertEqual("foofoo", self.template.repeat('foo', 2))

    def test_quotes(self):
        self.assertEqual("""($ $.$($/$'$")""", self.template.quotes())

    def test_unicode(self):
        # print(self.template.black_stars())
        self.assertEqual(
            "\N{BLACK STAR}" * 10,
            self.template.black_stars(count=10))

    def test_list_comprehension(self):
        self.assertEqual(
            "Hello David.Hello Kevin.",
            self.template.hello_list(['David', 'Kevin']))

    def test_code_block(self):
        self.assertEqual(
            "<tr><td>prices</td><td>123</td></tr>\n",
            self.template.html_cell_concat_values('prices', [1, 2, 3]))

    def test_multiline_code_block(self):
        self.assertEqual('4\n3\n2\n1\n', self.template.multiline_countdown(4))

    def test_syntax_error(self):
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
        self.assertEqual(
            str(func_code(dummy_for_line).co_firstlineno + 8),
            got_exception)

    def test_runtime_error(self):
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
            self.assertEqual(
                func_code(dummy_for_line2).co_firstlineno + 2,
                func_code(testruntimeerror).co_firstlineno)
            testruntimeerror('hello')
        except NameError:
            import traceback
            _, got_line, _, _ = traceback.extract_tb(sys.exc_info()[2], 10)[-1]
        self.assertEqual(
            func_code(dummy_for_line2).co_firstlineno + 10,
            got_line)

    def test_nosource(self):
        l = {}
        exec(
            """if True:
            @templet
            def testnosource(a):
                "${[c for c in reversed(a)]} is '$a' backwards."
            """, globals(), l)
        self.assertEqual(
            "olleh is 'hello' backwards.",
            eval('testnosource("hello")', globals(), l))

    def test_error_line(self):
        error_line = None
        try:
            exec("""if True:
                @templet
                def testnosource_error(a):
                    "${[c for c in reversed a]} is '$a' backwards."
                """, globals(), {})
        except SyntaxError as e:
            error_line = re.search('line [0-9]*', str(e)).group(0)
        self.assertEqual('line 4', error_line)


def main():
    for python in ('python2', 'python3', 'pypy'):
        cmd = python + ' -m unittest test_templet'
        print(cmd)
        if os.system(cmd):
            sys.exit(1)


if __name__ == '__main__':
    main()
