from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import re
import sys
import templet as m

templet = m.templet
func_code = m.func_code


##############################################################################
# When executed as a script, run some testing code.
if __name__ == '__main__':
    ok = True

    def expect(actual, expected):
        global ok
        if expected != actual:
            print(
                "error - expect: %s, got:\n%s"
                % (repr(expected), repr(actual)))
            ok = False
        assert ok

    @templet
    def testBasic(name):
        "Hello $name."
    expect(testBasic('Henry'), "Hello Henry.")

    @templet
    def testQuoteDollar(name):
        "Hello $name$$."
    expect(testQuoteDollar('Henry'), "Hello Henry$.")

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
    expect(got_exception, str(func_code(dummy_for_line).co_firstlineno + 8))

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
        expect(
            func_code(testruntimeerror).co_firstlineno,
            func_code(dummy_for_line2).co_firstlineno + 2)
        testruntimeerror('hello')
    except NameError as e:
        import traceback
        _, got_line, _, _ = traceback.extract_tb(sys.exc_info()[2], 10)[-1]
    expect(got_line, func_code(dummy_for_line2).co_firstlineno + 10)

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
